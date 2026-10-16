"""PRD 11 worked examples — ledger honesty + replay. IDs: AC-EXA-00N.

Every replay copies an example OUT of the repo into ``tmp_path`` and runs it
there: the drivers commit and ``git reset --hard``, so they must never run
inside the worktree (they would rewrite tracked ``train.py``).

Timing columns (``seconds`` / ``median_seconds``) are T2 statistical fields and
are never compared — a re-run measures its own wall clock. ex1/ex2 are compared
on metric/status/description; ex3 (integration tier) on gate and description
only, because its keep/discard statuses are timing-sensitive.
"""
import importlib.util
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contract" / "examples"
EXAMPLE_DIRS = ("ex1-music-abc", "ex2-iris-knn", "ex3-hotpath-speedup")
TIMING_HEADER = ("commit", "val_bpb", "accuracy", "median_seconds")


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _driver_header(example):
    """The HEADER constant the example's own driver writes into results.tsv."""
    src = _read(EXAMPLES / example / "loop_driver.py")
    m = re.search(r'^HEADER = "(.*)"$', src, re.M)
    assert m, f"{example}/loop_driver.py has no HEADER constant"
    return m.group(1).replace("\\t", "\t")


def _rows(path):
    """Ledger rows below the header, tab-split."""
    lines = [ln for ln in _read(path).splitlines() if ln.strip()]
    return [ln.split("\t") for ln in lines[1:]]


def _scratch_copy(example, tmp_path):
    """Copy example/ into tmp_path and make it a git repo with an identity.

    The drivers shell out to ``git commit``; without a repo-local identity those
    commits fail silently and every row collapses onto the initial commit, which
    would make the replay compare garbage. This is why the copy is never run in
    the worktree.
    """
    dst = tmp_path / example
    shutil.copytree(EXAMPLES / example, dst)
    for name in ("results.tsv", "run.log"):
        (dst / name).unlink(missing_ok=True)

    def run(*args):
        return subprocess.run(args, cwd=dst, capture_output=True, text=True)

    run("git", "init", "-q")
    run("git", "config", "user.name", "worked-example-test")
    run("git", "config", "user.email", "worked-example-test@example.invalid")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "contract: baseline")
    return dst


def _run_driver(dst, timeout=120):
    return subprocess.run(
        [sys.executable, "loop_driver.py", "--from-baseline"],
        cwd=dst, capture_output=True, text=True, timeout=timeout,
    )


def _ledger_key(row, cols=(1, 3, 4)):
    return tuple(row[i] for i in cols)


@pytest.mark.parametrize("example,ac_id", [("ex1-music-abc", "AC-EXA-001"),
                                          ("ex2-iris-knn", "AC-EXA-002")])
def test_replay_reproduces_vendored_ledger(example, ac_id, tmp_path):
    """AC-EXA-001 (ex1) / AC-EXA-002 (ex2): a fresh scratch replay of the
    driver — started from the tracked baseline via --from-baseline — reproduces
    the vendored ledger's metric/status/description columns row for row."""
    dst = _scratch_copy(example, tmp_path)
    proc = _run_driver(dst)
    assert proc.returncode == 0, f"{ac_id} driver failed:\n{proc.stdout}\n{proc.stderr}"
    produced = [_ledger_key(r) for r in _rows(dst / "results.tsv")]
    vendored = [_ledger_key(r) for r in _rows(EXAMPLES / example / "results.tsv")]
    assert produced == vendored


def test_dashboard_numbers_equal_vendored_ledgers():
    """AC-EXA-003: dashboard.html hand-transcribes the ledgers inline; every
    (value, status) pair must equal the vendored results.tsv it claims to chart."""
    html = _read(EXAMPLES / "dashboard.html")
    starts = [m.start() for m in re.finditer(r'name: "ex\d', html)]
    assert len(starts) == 3, "dashboard.html must carry three runs"
    chunks = [html[starts[i]:(starts[i + 1] if i + 1 < len(starts) else len(html))]
              for i in range(len(starts))]
    for chunk, example in zip(chunks, EXAMPLE_DIRS):
        dash = [(float(v), status)
                for _, v, status in re.findall(r'\["([^"]*)", ([0-9.]+), "(\w+)"\]', chunk)]
        tsv = [(float(r[1]), r[3]) for r in _rows(EXAMPLES / example / "results.tsv")]
        assert dash == tsv, f"dashboard.html numbers drift from {example}/results.tsv"


def test_every_ledger_has_its_driver_header():
    """AC-EXA-004: each vendored results.tsv starts with the header its own
    driver writes (no headerless ledger), and is five columns wide."""
    for example in EXAMPLE_DIRS:
        expected = _driver_header(example)
        first = _read(EXAMPLES / example / "results.tsv").splitlines()[0]
        assert first == expected, f"{example}/results.tsv is missing its header row"
        assert len(first.split("\t")) == 5
        assert first.split("\t")[0] == "commit"


@pytest.mark.parametrize("example", EXAMPLE_DIRS)
def test_provenance_says_scripted_reference_run(example):
    """AC-EXA-005: provenance is 'scripted reference run' — the candidate list is
    a fixed list replayed deterministically; no file may claim an LLM chose it."""
    banned = ("LLM-driven", "mutation operator")
    for path in sorted((EXAMPLES / example).glob("*")):
        if path.suffix not in (".py", ".md"):
            continue
        text = _read(path)
        for phrase in banned:
            assert phrase not in text, f"{example}/{path.name} claims {phrase!r}"
    assert "scripted reference run" in _read(EXAMPLES / example / "loop_driver.py")


def _grid_accuracy(train, test, k, metric, normalize, weighted):
    """ex2's kNN, re-implemented here so the grid claim is checked, not trusted."""
    if normalize:
        dim = len(train[0][0])
        n = len(train)
        mu = [sum(r[0][j] for r in train) / n for j in range(dim)]
        sd = []
        for j in range(dim):
            var = sum((r[0][j] - mu[j]) ** 2 for r in train) / n
            sd.append(math.sqrt(var) or 1.0)
        norm = lambda x: [(x[j] - mu[j]) / sd[j] for j in range(dim)]
        tr = [(norm(f), lab) for f, lab in train]
    else:
        norm = lambda x: x
        tr = train
    classes = sorted({lab for _, lab in train})
    correct = 0
    for feats, label in test:
        x = norm(feats)
        if metric == "manhattan":
            dists = [(sum(abs(a - b) for a, b in zip(x, tf)), tl) for tf, tl in tr]
        else:
            dists = [(math.sqrt(sum((a - b) ** 2 for a, b in zip(x, tf))), tl)
                     for tf, tl in tr]
        neighbours = sorted(dists, key=lambda t: t[0])[:k]
        votes = {}
        for dist, lab in neighbours:
            votes[lab] = votes.get(lab, 0.0) + (1.0 / (dist + 1e-12) if weighted else 1)
        if max(classes, key=lambda c: votes.get(c, 0.0)) == label:
            correct += 1
    return correct / len(test)


def _load_ex2_prepare():
    spec = importlib.util.spec_from_file_location(
        "ex2_prepare_probe", EXAMPLES / "ex2-iris-knn" / "prepare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _grid_max(prepare_module, seed):
    train, test = prepare_module._split(prepare_module.ROWS, seed=seed)
    return max(
        _grid_accuracy(train, test, k, metric, normalize, weighted)
        for k in (1, 3, 5, 7, 9)
        for metric in ("euclidean", "manhattan")
        for normalize in (False, True)
        for weighted in (False, True)
    )


def test_ex2_seed_note_claims_no_headroom_is_false():
    """AC-EXA-006: ex2's note may not claim the seed-42 split had no headroom.
    The grid is recomputed here: on seed 42 the 1-NN raw baseline scores
    0.977778 and the kNN grid still reaches 1.000000, so headroom exists."""
    mod = _load_ex2_prepare()
    train42, test42 = mod._split(mod.ROWS, seed=42)
    baseline42 = _grid_accuracy(train42, test42, 1, "euclidean", False, False)
    assert baseline42 == pytest.approx(44 / 45)          # 0.977778
    assert _grid_max(mod, 42) == pytest.approx(1.0)      # > baseline42: headroom
    assert _grid_max(mod, 42) > baseline42


def test_ex2_frozen_split_still_has_the_ledger_delta():
    """AC-EXA-007: the frozen split the ledger was produced on is seed 23, its
    1-NN raw baseline is 0.933333, and the grid reaches 1.000000 — i.e. the
    vendored ex2 ledger is a real measurement on a real split."""
    mod = _load_ex2_prepare()
    assert mod.SPLIT_SEED == 23
    train23, test23 = mod._split(mod.ROWS, seed=23)
    assert _grid_accuracy(train23, test23, 1, "euclidean", False, False) == pytest.approx(
        42 / 45)                                          # 0.933333
    assert _grid_max(mod, 23) == pytest.approx(1.0)


def test_ex2_seed_note_discloses_the_tuning():
    """AC-EXA-008: the seed choice is disclosed as evaluator-input tuning (a
    Goodhart risk), not hidden behind a headroom claim."""
    text = _read(EXAMPLES / "ex2-iris-knn" / "prepare.py")
    assert "no headroom" not in text.lower()
    assert "goodhart" in text.lower()
    assert "seed 42" in text.lower()


def test_examples_ship_a_tracked_baseline():
    """AC-EXA-009: each example ships train_baseline.py (the reconstructed
    baseline) and its driver accepts --from-baseline, which is what makes the
    replay possible from a fresh clone of the tracked state."""
    for example in EXAMPLE_DIRS:
        assert (EXAMPLES / example / "train_baseline.py").is_file()
        driver = _read(EXAMPLES / example / "loop_driver.py")
        assert '"--from-baseline"' in driver
        assert "train_baseline.py" in driver


def test_time_budget_is_described_as_a_ceiling():
    """AC-EXA-010: every program.md frames TIME_BUDGET as a ceiling, never as a
    target the run is expected to fill."""
    for example in EXAMPLE_DIRS:
        text = _read(EXAMPLES / example / "program.md")
        assert "TIME_BUDGET" in text
        assert "ceiling" in text.lower()
