"""PRD 11 — ex3 replay in a tmp git repo. IDs: AC-EXA-201, AC-EXA-202.

ex3's objective is wall-clock time, so its keep/discard statuses are a T2
statistical field: two candidates sit within a few percent of their incumbent
(the ``word_count`` reuse, row 2; the ``Counter`` counting step, row 7) and flip
between keep and discard as timing jitters. A flipped keep is not cosmetic — it
diverges the patch cascade:

  row 2 discarded  -> ``"word_count": len(clean.split())`` survives; candidate 8
                      (``re.findall`` tokenize) removes ``clean`` -> the next run
                      raises ``NameError: name 'clean' is not defined``;
  row 7 discarded  -> ``counts = count_words(words)`` survives; candidate 10
                      (``simplify``) deletes ``count_words`` -> ``NameError``.

A candidate that raises inside ``run()`` makes the frozen gate print
``gate_ok: False``, so the driver records the row as gate ``invalid`` (median
``inf``) — an *extra* rejection the vendored ledger does not have. That crashed
candidate is then reset, which strips the change the final ``attack:`` candidate
anchors on, so the driver aborts with ``PATCH MISS`` and the attack row is never
produced.

Comparing the ledger row for row therefore compares a statistical field, which
the repo's metric-tier doctrine forbids (``kb/concepts/better-cheaper-faster-metrics.md``:
statistical fields never gate). This tier instead asserts only what is
deterministic:

* (a) the driver starts from the tracked, reconstructed baseline and completes
  the baseline row;
* (b) the final kept ``train.py`` passes ex3's frozen exact-output gate inside
  budget — the replay's own HEAD when the cascade completed, else the vendored
  tracked artifact restored from the repo, which is the record;
* (c) the descriptions it produces before any divergence are a prefix of the
  vendored ledger (the baseline row at minimum), and a stopped replay stops only
  on a documented ``PATCH MISS``.

The ``median_seconds`` and ``status`` columns, and the gate column, are never
compared.

The replay runs in ``tmp_path``: the driver commits and ``git reset --hard``,
so it must never run inside the worktree.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EX3 = ROOT / "contract" / "examples" / "ex3-hotpath-speedup"
REPLAY_TIMEOUT = 480


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _rows(path):
    lines = [ln for ln in _read(path).splitlines() if ln.strip()]
    return [ln.split("\t") for ln in lines[1:]]


def _git(dst, *args):
    return subprocess.run(("git",) + args, cwd=dst, capture_output=True, text=True)


@pytest.fixture(scope="module")
def replayed(tmp_path_factory):
    """One scratch git copy of ex3, replayed from the tracked baseline.

    Module-scoped because a full replay takes ~1.5 minutes; the two tests below
    read the same produced ledger and the same scratch tree.
    """
    dst = tmp_path_factory.mktemp("ex3") / "ex3-hotpath-speedup"
    shutil.copytree(EX3, dst)
    for name in ("results.tsv", "run.log"):
        (dst / name).unlink(missing_ok=True)
    _git(dst, "init", "-q")
    _git(dst, "config", "user.name", "worked-example-test")
    _git(dst, "config", "user.email", "worked-example-test@example.invalid")
    _git(dst, "add", "-A")
    _git(dst, "commit", "-qm", "contract: baseline")
    proc = subprocess.run(
        [sys.executable, "loop_driver.py", "--from-baseline"],
        cwd=dst, capture_output=True, text=True, timeout=REPLAY_TIMEOUT,
    )
    return dst, proc


def test_ex3_replay_starts_from_baseline_and_keeps_the_description_prefix(replayed):
    """AC-EXA-201: the replay starts from the tracked baseline, completes the
    baseline row, and every description it produces before any timing-induced
    divergence is a prefix of the vendored ledger.

    Deterministic by construction: the candidate list is a fixed script, so the
    descriptions are assigned in order; only the keep/discard *status* is
    timing-sensitive. A status that flips (a T2 field) may end the cascade early
    on a documented ``PATCH MISS`` and may add a crash-induced ``invalid`` gate
    cell — the driver stops either way without inventing a description the
    vendored ledger does not have.
    """
    dst, proc = replayed
    out = proc.stdout + proc.stderr

    # (a) it started from the tracked, reconstructed baseline ...
    assert "--from-baseline: train.py <- train_baseline.py" in out, out
    produced = _rows(dst / "results.tsv")
    vendored = _rows(EX3 / "results.tsv")
    assert produced, f"ex3 replay produced no ledger rows:\n{out}"

    # ... and completed the baseline row (always row 0, never timing-gated).
    assert produced[0][4] == vendored[0][4], produced[0]
    assert "baseline" in produced[0][4]

    # (c) the descriptions are a deterministic prefix of the vendored ledger.
    produced_desc = [r[4] for r in produced]
    vendored_desc = [r[4] for r in vendored]
    assert produced_desc == vendored_desc[:len(produced_desc)], (
        "ex3 produced a description outside the vendored ledger prefix:\n"
        f"produced={produced_desc}")

    # A stopped replay stops ONLY on a documented anchor miss (the timing-induced
    # cascade divergence) -- never on some other error, and never silently.
    if proc.returncode != 0:
        assert "PATCH MISS" in out, (
            f"ex3 replay aborted for a reason other than a cascade divergence:\n{out}")

    # When the cascade ran to the end, the labeled attack is gate-rejected -- the
    # anti-Goodhart rule, which is deterministic for a candidate that IS reached.
    if produced_desc == vendored_desc:
        assert produced[-1][4] == vendored[-1][4]
        assert "attack" in produced[-1][4]
        assert produced[-1][2] == "invalid", produced[-1]


def test_ex3_final_artifact_passes_the_exact_output_gate(replayed):
    """AC-EXA-202: the final kept ``train.py`` reproduces the frozen reference
    result exactly — ``train.py`` exits 0, prints ``gate_ok: True`` and a median
    inside ``TIME_BUDGET``.

    If the replay's cascade completed, its own HEAD (the last keep) is checked;
    if a timing flip diverged the cascade, the vendored tracked ``train.py`` is
    restored and checked instead — the vendored artifact is the record, and it is
    deterministic.
    """
    dst, proc = replayed
    if proc.returncode != 0:                      # a timing flip diverged the cascade
        shutil.copyfile(EX3 / "train.py", dst / "train.py")
    proc = subprocess.run(
        [sys.executable, "train.py"], cwd=dst, capture_output=True, text=True,
        timeout=REPLAY_TIMEOUT,
    )
    assert proc.returncode == 0, f"final train.py failed the gate:\n{proc.stdout}\n{proc.stderr}"
    assert re.search(r"^gate_ok: True$", proc.stdout, re.M), proc.stdout
    median = float(re.search(r"^median_seconds: ([0-9.]+)$", proc.stdout, re.M).group(1))
    budget = float(re.search(r"^time_budget: ([0-9.]+)$", proc.stdout, re.M).group(1))
    assert median <= budget
