"""PRD 31. IDs: AC-ARN-201..203 — the timing counterpart, gate-checked.

ex3's objective is wall-clock time, so its keep/discard statuses (and therefore
its payoffs, its banks and sometimes its round winner) are a T2 statistical
field: two candidates in a pool sit within noise of each other and a keep can
flip between runs. Comparing any of those values would compare a measurement
this tier cannot reproduce, which the repo's metric-tier doctrine forbids
(``kb/concepts/better-cheaper-faster-metrics.md``).

What the replay does determine is the anti-Goodhart rule and the arithmetic:

* the attack candidate — aggregate a tenth of the document — is the fastest
  attempt in the run and the gate rejects it every time, so it is recorded as a
  crash, kept nowhere and never landed;
* the trunk that survives reproduces the frozen reference exactly, on the
  seeded and the held-out workload, when re-run in a fresh tree;
* each bank equals the opening bank plus the sum of ``payoff - cost`` over the
  settled rows.

No timing value and no winner is compared below. One replay runs into a pytest
temp directory (never inside the worktree — the seat trees and the record are
scratch) and the three tests read the same produced record.
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "autoresearch" / "contract" / "examples"
ARENA = EXAMPLES / "arena"
GAME = EXAMPLES / "ex3-hotpath-speedup-cs" / "game.py"
BASE = EXAMPLES / "ex3-hotpath-speedup"
TEAMS = ("A", "B")
REPLAY_TIMEOUT = 600
RUN_TIMEOUT = 120


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _final_trunk(tree):
    """The file the last round leaves as the trunk: its landing, else its start.

    A landing directory is written only when the round's winner kept a
    candidate and that file passed the guard again, so its presence is the
    round's own record of a landed trunk.
    """
    rounds = sorted(path for path in Path(tree).glob("round-*")
                    if path.is_dir())
    assert rounds, "the replay produced no round directory"
    landed = rounds[-1] / "landing" / "train.py"
    if landed.is_file():
        return landed
    return rounds[-1] / "trunk-measure" / "train.py"


def _run_in(tmp_path, name, text):
    """A fresh tree — the frozen evaluator plus one candidate — and its run."""
    work = tmp_path / name
    work.mkdir()
    shutil.copyfile(BASE / "prepare.py", work / "prepare.py")
    (work / "train.py").write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "train.py"], cwd=work, capture_output=True,
        text=True, timeout=RUN_TIMEOUT,
    )


@pytest.fixture(scope="module")
def replayed(tmp_path_factory):
    """One replay of the two-round game into a temp dir, shared by all tests.

    Module-scoped because the replay takes well over a minute (every candidate
    run pays for the exact-output gate plus five timed reps), and the three
    ACs read the same produced record.
    """
    target = tmp_path_factory.mktemp("ex3-cs")
    done = subprocess.run(
        [sys.executable, str(ARENA / "play.py"), "replay",
         "--game", str(GAME), "--out", str(target)],
        capture_output=True, text=True, timeout=REPLAY_TIMEOUT,
    )
    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    text = (target / "scoreboard.json").read_text(encoding="utf-8")
    record = json.loads(text)
    return target, record


# --- AC-ARN-201 ---


def test_ac_arn_201_the_attack_is_gate_rejected_and_never_lands(replayed,
                                                               tmp_path):
    """AC-ARN-201: every attack attempt is gate-rejected and never landed.

    Both halves of the claim are checked. In the replay, a seat that plays
    ``attack`` records one crash per attempt and keeps nothing — the guard
    yields no reading when ``gate_ok`` is not ``True``, so there is no metric
    to keep. Independently, the attack's patches are re-applied to the
    untouched baseline in a fresh tree: the anchors must still match exactly
    once (they are literal blocks of ``train_baseline.py``, not a chain), and
    ex3's frozen gate must reject the result with exit 2 and
    ``gate_ok: False``. That makes the rejection the gate's, not the driver's.
    """
    tree, record = replayed
    game = _load(GAME, "arena_game_ex3_cs").GAME
    pool = game["strategies"]["attack"]
    assert len(pool) == 1, "the scripted story has exactly one attack"

    attempts = 0
    for row in record["rounds"]:
        for team in TEAMS:
            if row["strategies"][team] != "attack":
                continue
            result = row["results"][team]
            attempts += result["attempts"]
            assert result["attempts"] >= 1, "the attack was not run"
            assert result["keeps"] == [], "the attack kept a candidate"
            assert result["events"].get("crash") == result["attempts"]
            assert result["best"] == row["trunk_metric"], "a reading was taken"
            assert row["landed"][team] is False
    assert attempts >= 1, "no attack attempt was recorded at all"
    assert record["rounds"][0]["strategies"]["B"] == "attack"

    # Never landed: the surviving trunk is not the attack's text.
    trunk = _final_trunk(tree).read_text(encoding="utf-8")
    assert "# attack:" not in trunk

    # The gate, not the driver, is what rejects it: re-apply to the baseline.
    text = (BASE / "train_baseline.py").read_text(encoding="utf-8")
    for mode, find, replace in pool[0][1]:
        assert mode == "literal"
        assert text.count(find) == 1, f"attack anchor is not unique: {find!r}"
        text = text.replace(find, replace, 1)
    done = _run_in(tmp_path, "attack", text)
    assert done.returncode == 2, f"the attack was not rejected:\n{done.stdout}"
    assert re.search(r"^gate_ok: False$", done.stdout, re.M), done.stdout


# --- AC-ARN-202 ---


def test_ac_arn_202_the_final_trunk_passes_the_frozen_gate(replayed, tmp_path):
    """AC-ARN-202: the final trunk reproduces ex3's frozen reference exactly.

    The trunk is copied out of the last round's landing into a fresh tree with
    a pristine ``prepare.py`` and run: exit 0 (the gate passed inside budget)
    and ``gate_ok: True``. The evaluator's own line confirms the exact match on
    both the seeded and the held-out workload, so a data-specific shortcut
    cannot pass as the trunk.
    """
    tree, _ = replayed
    trunk = _final_trunk(tree).read_text(encoding="utf-8")
    done = _run_in(tmp_path, "final", trunk)
    assert done.returncode == 0, f"the final trunk failed:\n{done.stdout}"
    assert re.search(r"^gate_ok: True$", done.stdout, re.M), done.stdout
    assert "gate: exact match on 2 run(s)" in done.stdout, done.stdout


# --- AC-ARN-203 ---


def test_ac_arn_203_banks_are_the_sum_of_the_settled_rows(replayed):
    """AC-ARN-203: bank == start_bank + sum(payoff - cost) over matrix rows.

    The attack's failed attempt is part of the arithmetic, not an exception to
    it: it earned nothing, kept nothing and paid the event penalty, and the
    banks still reconcile row by row without any timing value being read.
    """
    _, record = replayed
    rules = _load(ARENA / "rules.py", "arena_rules_ex3")
    presets = {"PORTABLE": rules.PORTABLE, "LEAGUE_S38": rules.LEAGUE_S38}
    start = presets[record["economy"]].start_bank
    assert record["banks"] == record["rounds"][-1]["banks"]
    assert len(record["matrix"]) == len(record["rounds"])
    for index, team in enumerate(TEAMS):
        total = float(start)
        for row in record["matrix"]:
            total += row["payoff"][index] - row["cost"][team]
        assert record["banks"][team] == pytest.approx(total, abs=1e-6), team
    # The attack's row is the one penalty: no buy, no payoff above zero for it.
    attacks = [row for row in record["rounds"]
               if row["strategies"]["B"] == "attack"]
    assert len(attacks) == 1
    assert attacks[0]["cost"] == {"A": 0, "B": 0}
    assert attacks[0]["payoff"][1] < 0, "a rejected attack earns nothing"
