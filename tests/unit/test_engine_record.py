"""PRD 22 — the run record and its honest-verdict checks. IDs: AC-REC-001..012."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from autoresearch import config as config_mod
from autoresearch import record as record_mod

from test_engine_support import (
    DECREMENT,
    head,
    init_args,
    init_run,
    make_target,
    read_events,
    run_args,
    run_cli,
    write_agent,
)

STATE = ".autoresearch"


def served(tmp_path, *, name="repo", value=10, iterations=2, extra_init=(), extra_run=()):
    """A real run that keeps every step: value 10 -> 8 -> 6."""
    repo = make_target(tmp_path, value=value, name=name)
    script = write_agent(tmp_path, DECREMENT.format(step=2), name=f"agent-{name}.py")
    assert init_run(repo, extra=list(extra_init)) == 0
    assert run_cli(
        run_args(
            repo, script,
            extra=["--max-iterations", str(iterations), *extra_run],
        )
    ) == 0
    return repo


def write_record(repo):
    """Run ``report --record`` and return the parsed close record."""
    assert run_cli(["report", "--repo", str(repo), "--record"]) == 0
    path = Path(repo) / STATE / "record.json"
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_commit(repo):
    return next(e["commit"] for e in read_events(repo) if e["type"] == "baseline")


# ─── shape ───────────────────────────────────────────────────────────────────


def test_a_closed_run_leaves_a_comparable_record(tmp_path):
    """AC-REC-001: two commits, one reading per measured leg, keeps, review, floors."""
    repo = served(tmp_path)
    record = write_record(repo)
    assert record["version"] == 1
    assert record["pending"] is False
    assert record["parent_commit"] == baseline_commit(repo)
    assert record["close_commit"] == record["keeps"][-1]["commit"]
    assert [keep["round"] for keep in record["keeps"]] == [1, 2]
    assert record["baselines"]["value"]["commit"] == record["parent_commit"]
    assert record["baselines"]["value"]["value"] == 10.0
    assert record["readings"][0]["before"] == 10.0
    assert record["readings"][0]["after"] == 6.0
    assert record["floor_before"] == record["floor_after"] == 0.01
    assert record["state_dir"] == STATE
    assert record["provenance"]["engine_version"]
    assert "2 keep(s) of 2 trial(s)" in record["review"]["reason"]
    assert record["review"]["weights"] == {"value": 1.0}


def test_a_reading_keeps_the_evaluator_line_not_a_paraphrase(tmp_path):
    """AC-REC-002: ``raw`` is the line the metric came from and reproduces its value."""
    repo = served(tmp_path)
    record = write_record(repo)
    row = record["readings"][0]
    assert row["verdict"] == "improved"
    assert row["lower_is_better"] is True
    assert row["raw"] == "METRIC value=6"
    assert row["note"] and "beyond the 0.01 floor" in row["note"]
    assert record_mod.check(record, repo) == []


def test_the_verdict_enum_is_closed_and_a_relocation_owes_a_note(tmp_path):
    """AC-REC-003: improved / held / displaced only, and a relocation needs its note."""
    record = write_record(served(tmp_path))
    displaced = copy.deepcopy(record)
    displaced["readings"][0].update({"verdict": "displaced", "note": "the tier shrank"})
    assert record_mod.check(displaced) == []
    silent = copy.deepcopy(displaced)
    silent["readings"][0]["note"] = ""
    assert "is displaced with no note" in " | ".join(record_mod.check(silent))
    invented = copy.deepcopy(record)
    invented["readings"][0]["verdict"] = "play"
    assert "not one of improved/held/displaced" in " | ".join(
        record_mod.check(invented)
    )


def test_a_jittery_metric_records_the_median_repeats_own_line(tmp_path):
    """AC-REC-002: with repeats, the record's raw line is the median repeat's.

    The shipped registry measures at ``repeats: 3``, so a verify printing 6, 6, 7
    must record ``after 6.0`` beside the line that printed 6 — the last repeat's 7
    is not the reading.
    """
    counter = tmp_path / "jitter.count"
    score = (
        "import pathlib\n"
        f"counter = pathlib.Path({str(counter)!r})\n"
        "seen = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(seen + 1))\n"
        "value = int(pathlib.Path('src/value.txt').read_text().strip())\n"
        "print(f'METRIC value={value + [0, 0, 1][seen % 3]}')\n"
    )
    repo = make_target(tmp_path, value=6, name="jitter", score_body=score)
    assert init_run(repo, repeats=3) == 0
    script = write_agent(tmp_path, DECREMENT.format(step=1), name="agent-jitter.py")
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    record = write_record(repo)
    row = record["readings"][0]
    assert row["after"] == 6.0
    assert row["raw"] == "METRIC value=6"
    assert row["values"] == [6.0, 6.0, 7.0]
    assert record_mod.check(record, repo) == []
    assert run_cli(["report", "--repo", str(repo), "--check"]) == 0

    swapped = copy.deepcopy(record)
    swapped["readings"][0]["raw"] = "METRIC value=7"
    assert "median repeat" in " | ".join(record_mod.check(swapped))
    # A point estimate that is not the repeats' median is refused too.
    skewed = copy.deepcopy(record)
    skewed["readings"][0]["after"] = 6.5
    assert "not the one recorded" in " | ".join(record_mod.check(skewed))


def test_an_even_repeat_count_records_the_lower_middle_line(tmp_path):
    """AC-REC-002: an even median is an average, so the series is carried beside it."""
    counter = tmp_path / "even.count"
    score = (
        "import pathlib\n"
        f"counter = pathlib.Path({str(counter)!r})\n"
        "seen = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(seen + 1))\n"
        "print('METRIC value=' + str([6, 7][seen % 2]))\n"
    )
    repo = make_target(tmp_path, value=10, name="even", score_body=score)
    assert init_run(repo, repeats=2) == 0
    script = write_agent(tmp_path, DECREMENT.format(step=2), name="agent-even.py")
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    record = write_record(repo)
    row = record["readings"][0]
    assert row["after"] == 6.5
    assert row["raw"] == "METRIC value=6"
    assert record_mod.check(record, repo) == []


# ─── the artefacts ───────────────────────────────────────────────────────────


def test_record_writes_both_artefacts_into_the_state_directory(tmp_path):
    """AC-REC-004: record.json and record.md land beside the report, wherever state is."""
    repo = served(tmp_path, name="default")
    write_record(repo)
    assert (repo / STATE / "record.json").is_file()
    assert (repo / STATE / "record.md").is_file()

    state = tmp_path / "moved-state"
    moved = served(
        tmp_path,
        name="moved",
        iterations=1,
        extra_init=["--state-dir", str(state)],
        extra_run=["--state-dir", str(state)],
    )
    assert run_cli(
        ["report", "--repo", str(moved), "--state-dir", str(state), "--record"]
    ) == 0
    assert (state / "record.json").is_file()
    assert (state / "record.md").is_file()
    assert not (moved / STATE).exists()
    # A record travels with the harness: it names the state by label, never by host path.
    moved_record = json.loads((state / "record.json").read_text(encoding="utf-8"))
    assert moved_record["state_dir"] == "moved-state"
    assert str(tmp_path) not in (state / "record.md").read_text(encoding="utf-8")


def test_check_is_byte_identical_and_catches_a_one_character_drift(tmp_path):
    """AC-REC-005: --check exits 0 only on identity, 2 on any drift."""
    repo = served(tmp_path)
    write_record(repo)
    assert run_cli(["report", "--repo", str(repo), "--check"]) == 0
    md = repo / STATE / "record.md"
    md.write_text(md.read_text(encoding="utf-8") + "x", encoding="utf-8")
    assert run_cli(["report", "--repo", str(repo), "--check"]) == 2
    assert run_cli(["report", "--repo", str(repo), "--record"]) == 0
    assert run_cli(["report", "--repo", str(repo), "--check"]) == 0


def test_a_missing_record_and_a_pending_run_are_both_refused(tmp_path, capsys):
    """AC-REC-006: exit 2 before rendering — no guess, no half-record."""
    repo = make_target(tmp_path, value=10)
    assert init_run(repo) == 0
    assert run_cli(["report", "--repo", str(repo), "--check"]) == 2
    assert "run `report --record` first" in capsys.readouterr().err
    assert run_cli(["report", "--repo", str(repo), "--record"]) == 2
    assert "pending" in capsys.readouterr().err
    assert not (repo / STATE / "record.json").exists()


# ─── the honest-verdict gate ─────────────────────────────────────────────────


def test_a_baseline_read_at_two_commits_is_refused(tmp_path):
    """AC-REC-007: two legs measured at two commits are not comparable."""
    record = write_record(served(tmp_path))
    record["baselines"]["speed"] = {
        "commit": "f" * 40, "value": 4.0, "pinned": None,
        "declared": None, "credited": None, "uncovered": None,
    }
    problems = " | ".join(record_mod.check(record))
    assert "baseline commits differ across legs" in problems
    assert "speed@" in problems


def test_a_keep_off_the_close_tree_is_refused(tmp_path):
    """AC-REC-008: a keep the close commit does not carry is not a keep."""
    repo = served(tmp_path)
    record = write_record(repo)
    record["close_commit"] = record["parent_commit"]
    assert "is not an ancestor of close" in " | ".join(record_mod.check(record, repo))


def test_a_held_or_displaced_reading_without_a_note_is_refused(tmp_path):
    """AC-REC-009: the note is where the cause is named, so it is mandatory."""
    record = write_record(served(tmp_path, iterations=1))
    held = copy.deepcopy(record)
    held["readings"][0].update({"verdict": "held", "note": ""})
    assert "is held with no note" in " | ".join(record_mod.check(held))


def test_a_missing_raw_line_fails_and_so_does_one_that_disagrees(tmp_path, capsys):
    """AC-REC-010: the evaluator's own line is required evidence, not decoration."""
    repo = served(tmp_path)
    record = write_record(repo)
    stripped = copy.deepcopy(record)
    del stripped["readings"][0]["raw"]
    assert "has no raw" in " | ".join(record_mod.check(stripped))
    wrong = copy.deepcopy(record)
    wrong["readings"][0]["raw"] = "METRIC value=999"
    assert "raw line says 999" in " | ".join(record_mod.check(wrong))

    events = read_events(repo)
    for event in events:
        event.pop("raw", None)
    path = repo / STATE / "events.jsonl"
    path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
                    encoding="utf-8")
    assert run_cli(["report", "--repo", str(repo), "--record"]) == 2
    assert "no raw line" in capsys.readouterr().err


def test_the_denominator_trio_is_recorded_together_and_adds_up(tmp_path):
    """AC-REC-011: declared / credited / uncovered, one number hides which half moved."""
    record = write_record(served(tmp_path, iterations=1))
    base = record["baselines"]["value"]
    base.update({"declared": 10, "credited": 6, "uncovered": 3})
    assert "does not add up" in " | ".join(record_mod.check(record))
    base.update({"uncovered": 4})
    assert record_mod.check(record) == []
    del base["credited"]
    assert "records 2 of declared/credited/uncovered" in " | ".join(
        record_mod.check(record)
    )


def test_a_non_numeric_denominator_is_refused_not_coerced(tmp_path):
    """AC-REC-011: '1,027' is a label, and a gate that coerces it to 0.0 lies.

    The old comparison ran ``float(_number(x) or 0.0)``, so '1,027' against
    0 + 0 passed the sum rule with an empty check list.
    """
    record = write_record(served(tmp_path, iterations=1))
    base = record["baselines"]["value"]
    base.update({"declared": "1,027", "credited": 0, "uncovered": 0})
    problems = " | ".join(record_mod.check(record))
    assert "not a number" in problems
    assert "1,027" in problems


def test_a_pinned_baseline_in_the_objective_reaches_the_record(tmp_path):
    """AC-REC-011: the leg's declared trio is validated in the objective, not the record.

    A record cannot be hand-patched into a pin: the objective declares it, the
    validator checks it, and the run carries it into ``baselines``.
    """
    repo = make_target(tmp_path, value=10, name="pinned")
    commit = head(repo)
    path = tmp_path / "objective-baseline.json"
    leg = {
        "name": "value", "direction": "lower", "unit": "points",
        "command": f"{sys.executable} score.py", "repeats": 1,
        "noise_floor": 0.01, "guard": f"{sys.executable} guard.py",
        "baseline": {"commit": commit, "declared": 10, "credited": 6, "uncovered": 4},
    }
    path.write_text(json.dumps({"objectives": [{
        "id": "g-pin", "parent": None, "status": "active", "legs": [leg],
        "weights": {"value": 1.0}, "rotation": ["value"],
        "reason": "a pinned denominator",
    }]}), encoding="utf-8")
    assert run_cli(
        ["init", "--repo", str(repo), "--scope", "src", "--objective", str(path)]
    ) == 0
    script = write_agent(tmp_path, DECREMENT.format(step=2), name="agent-pin.py")
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    record = write_record(repo)
    base = record["baselines"]["value"]
    assert base["pinned"] == commit
    assert (base["declared"], base["credited"], base["uncovered"]) == (10.0, 6.0, 4.0)
    assert record_mod.check(record, repo) == []


def test_a_pinned_baseline_commit_must_be_the_one_measured(tmp_path):
    """AC-REC-011: a denominator pinned at another commit is an anecdote."""
    record = write_record(served(tmp_path, iterations=1))
    record["baselines"]["value"]["pinned"] = "a" * 40
    assert "is pinned to aaaaaaaaaaaa" in " | ".join(record_mod.check(record))


# ─── backward compatibility ──────────────────────────────────────────────────


def test_a_close_record_names_the_leg_the_run_measured_even_after_it_moves_to_its_floor(tmp_path):
    """AC-REC-001: the record is a historical statement, not a re-resolution."""
    repo = make_target(tmp_path, value=10, name="floor")
    path = tmp_path / "objective.json"
    leg = {
        "name": "value", "direction": "lower", "unit": "points",
        "command": f"{sys.executable} score.py", "repeats": 1,
        "noise_floor": 0.01, "guard": f"{sys.executable} guard.py",
    }

    def write(best=None):
        entry = dict(leg)
        rotation = ["value"]
        if best is not None:
            entry.update({"best": best, "floor": 8})
            rotation = []
        path.write_text(json.dumps({"objectives": [{
            "id": "g0", "parent": None, "status": "active", "legs": [entry],
            "weights": {"value": 1.0}, "rotation": rotation,
            "reason": "value closed at its floor" if best is not None else "root",
        }]}), encoding="utf-8")

    write()
    assert run_cli(
        ["init", "--repo", str(repo), "--scope", "src", "--objective", str(path)]
    ) == 0
    script = write_agent(tmp_path, DECREMENT.format(step=2), name="agent-floor.py")
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    write(best=8)
    record = write_record(repo)
    assert record["objective_id"] == "g0"
    assert record["readings"][0]["name"] == "value"
    assert record["readings"][0]["after"] == 8.0


def test_an_old_run_reports_exactly_as_before(tmp_path):
    """AC-REC-012: no --record means no new bytes; an old run.json still loads."""
    repo = served(tmp_path, iterations=1)
    cfg = config_mod.load(repo)
    assert cfg.objective_id is None and cfg.objective is None
    assert run_cli(["report", "--repo", str(repo)]) == 0
    report = (repo / STATE / "report.md").read_text(encoding="utf-8")
    assert "objective" not in report
    assert not (repo / STATE / "record.json").exists()
    assert run_cli(["status", "--repo", str(repo)]) == 0
