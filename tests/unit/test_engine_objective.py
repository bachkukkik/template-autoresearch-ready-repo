"""PRD 22 — the objective record. IDs: AC-OBJ-001..016.

Hermetic: each case builds its own record under ``tmp_path`` or a throwaway git
repo. The validator is a pure function, so most cases need no filesystem at all.
"""

from __future__ import annotations

import copy
import json
import shlex
import sys
from pathlib import Path

import pytest

from autoresearch import objective

from test_engine_support import init_run, make_target, run_cli

LEG = {
    "name": "value",
    "direction": "lower",
    "unit": "points",
    "command": f"{sys.executable} score.py",
    "repeats": 1,
    "noise_floor": 0.01,
    "guard": f"{sys.executable} guard.py",
}


def record(**overrides) -> dict:
    """A record with one active objective; every key present unless overridden."""
    obj = {
        "id": "g0",
        "parent": None,
        "status": "active",
        "legs": [copy.deepcopy(LEG)],
        "weights": {"value": 1.0},
        "seasons": [],
        "rounds": [],
        "reason": "the root objective",
    }
    obj.update(overrides)
    return {"objectives": [obj]}


def write_record(tmp_path, data, name="objective.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def joined(problems) -> str:
    return " | ".join(problems)


# ─── the clean case ──────────────────────────────────────────────────────────


def test_one_leg_at_weight_one_is_a_valid_record():
    """AC-OBJ-001: the single-metric degenerate case validates and resolves."""
    data = record()
    assert objective.validate(data) == []
    leg = objective.resolve_leg(data)
    assert leg["objective_id"] == "g0"
    assert leg["name"] == "value"
    assert leg["direction"] == "lower"
    assert leg["command"] == LEG["command"]
    assert leg["repeats"] == 1
    assert leg["noise_floor"] == 0.01
    assert leg["weight"] == 1.0
    shipped = objective.load(objective.DEFAULT_RECORD)
    assert objective.validate(shipped) == []


def test_the_weight_clamp_boundaries_are_inclusive():
    """AC-OBJ-001/AC-OBJ-006: 0.5 and 3.0 are inside the clamp, 0.4 and 3.5 are not."""
    assert objective.validate(record(weights={"value": 0.5})) == []
    assert objective.validate(record(weights={"value": 3.0})) == []
    low = objective.validate(record(weights={"value": 0.4}))
    high = objective.validate(record(weights={"value": 3.5}))
    assert "outside [0.5, 3]" in joined(low)
    assert "outside [0.5, 3]" in joined(high)


# ─── one rule per refusal ────────────────────────────────────────────────────


def test_a_duplicate_leg_name_is_refused():
    """AC-OBJ-002: a leg is a lookup key, so two entries for one name are refused."""
    data = record()
    data["objectives"][0]["legs"].append(copy.deepcopy(LEG))
    problems = objective.validate(data)
    assert "leg 'value' of objective 'g0' is declared 2 times" in joined(problems)


def test_a_leg_field_and_an_objective_field_are_both_reported():
    """AC-OBJ-003: a missing field names itself, and one pass reports both halves."""
    data = record()
    del data["objectives"][0]["legs"][0]["unit"]
    del data["objectives"][0]["status"]
    problems = joined(objective.validate(data))
    assert "has no unit" in problems
    assert "has no status" in problems


def test_a_direction_is_refused_never_defaulted():
    """AC-OBJ-004: 'not lower' is not 'higher'; a default would invert the leg."""
    data = record()
    data["objectives"][0]["legs"][0]["direction"] = "sideways"
    problems = joined(objective.validate(data))
    assert "declares direction 'sideways', not one of lower/higher" in problems


def test_a_weight_must_name_a_leg_and_every_leg_needs_one():
    """AC-OBJ-005: an unknown key prices nothing, an unweighted leg is not priced."""
    ghost = record(weights={"value": 1.0, "ghost": 1.0})
    assert "weight 'ghost' of objective 'g0' names no declared leg" in joined(
        objective.validate(ghost)
    )
    unweighted = record(weights={})
    assert "leg 'value' of objective 'g0' has no weight" in joined(
        objective.validate(unweighted)
    )


def test_two_active_objectives_are_refused_and_both_are_named():
    """AC-OBJ-007: two weights for one run and no way to say which settled it."""
    data = record()
    second = copy.deepcopy(data["objectives"][0])
    second["id"] = "g1"
    second["parent"] = "g0"
    second["reason"] = "forked"
    data["objectives"].append(second)
    problems = objective.validate(data)
    assert any("2 objectives are active" in item and "'g0'" in item and "'g1'" in item
               for item in problems)
    with pytest.raises(objective.ObjectiveError, match="are active"):
        objective.resolve_leg(data)


def test_a_period_owned_twice_is_refused_for_seasons_and_rounds():
    """AC-OBJ-008: a period listed twice has two accounts of the same numbers."""
    data = record()
    data["objectives"][0].update({"seasons": [18], "rounds": [61], "status": "archived"})
    second = copy.deepcopy(data["objectives"][0])
    second.update({"id": "g1", "parent": "g0", "status": "active", "reason": "forked"})
    second["weights"] = {"value": 1.0}
    data["objectives"].append(second)
    problems = joined(objective.validate(data))
    assert "season 18 is listed by both 'g0' and 'g1'" in problems
    assert "round 61 is listed by both 'g0' and 'g1'" in problems


def test_a_dangling_parent_and_a_cyclic_chain_are_refused():
    """AC-OBJ-009: a fork's reason is written against a parent that exists and ends."""
    dangling = record()
    dangling["objectives"][0]["parent"] = "absent"
    # A root has no reason to explain, so the dangling parent is the only defect.
    dangling["objectives"][0]["reason"] = ""
    assert "names parent 'absent', which is no objective" in joined(
        objective.validate(dangling)
    )
    cycle = record()
    cycle["objectives"][0].update({"parent": "g1", "reason": "forked"})
    loop = copy.deepcopy(cycle["objectives"][0])
    loop.update({"id": "g1", "parent": "g0"})
    cycle["objectives"].append(loop)
    assert "is a cycle" in joined(objective.validate(cycle))


def test_an_active_objective_with_no_legs_is_refused():
    """AC-OBJ-010: an active objective with no legs pays nothing at all."""
    data = record(legs=[], weights={})
    assert "active objective 'g0' has no legs" in joined(objective.validate(data))


def test_a_leg_at_its_floor_must_leave_the_rotation():
    """AC-OBJ-011: a scheduled leg nobody can move hands a free zero to its owner."""
    data = record()
    data["objectives"][0]["legs"] = [
        {**copy.deepcopy(LEG), "name": "value", "best": 0, "floor": 0},
        {**copy.deepcopy(LEG), "name": "speed", "best": 40, "floor": 10},
    ]
    data["objectives"][0]["weights"] = {"value": 1.0, "speed": 1.0}
    data["objectives"][0]["rotation"] = ["value", "speed"]
    problems = joined(objective.validate(data))
    assert "leg 'value' of objective 'g0' is at its floor" in problems
    assert "is scheduled" in problems


def test_the_rotation_is_exactly_as_long_as_the_playable_legs():
    """AC-OBJ-011: a longer rotation gives one tick a second shot by construction."""
    data = record()
    data["objectives"][0]["legs"] = [
        {**copy.deepcopy(LEG), "name": "value"},
        {**copy.deepcopy(LEG), "name": "speed"},
    ]
    data["objectives"][0]["weights"] = {"value": 1.0, "speed": 1.0}
    data["objectives"][0]["rotation"] = ["value"]
    problems = joined(objective.validate(data))
    assert "has 1 leg(s) but 2 is playable" in problems
    assert "drops playable leg 'speed'" in problems
    data["objectives"][0]["rotation"] = ["value", "speed"]
    assert objective.validate(data) == []


def test_a_fork_and_a_retirement_owe_a_reason():
    """AC-OBJ-015: a fork with no floor evidence is a rewrite, not a fork."""
    fork = record(parent="g-parent", reason="")
    assert "fork of 'g-parent' into 'g0' has no reason" in joined(objective.validate(fork))
    retired = record(status="retired", reason="")
    assert "retired objective 'g0' has no reason" in joined(objective.validate(retired))


def test_a_pinned_baseline_is_declared_and_validated(tmp_path):
    """AC-OBJ-002/011: the leg's ``baseline`` is a declared schema, not a free object.

    The trio is what the record's denominator gate compares, so an objective that
    carries one is refused when it is unknown, partial, unreadable or does not add up.
    """
    pinned = record()
    pinned["objectives"][0]["legs"][0]["baseline"] = {
        "commit": "a" * 40, "declared": 10, "credited": 6, "uncovered": 4,
    }
    assert objective.validate(pinned) == []

    unknown = copy.deepcopy(pinned)
    unknown["objectives"][0]["legs"][0]["baseline"]["denominator"] = 10
    assert "declares baseline key 'denominator'" in joined(objective.validate(unknown))

    partial = copy.deepcopy(pinned)
    del partial["objectives"][0]["legs"][0]["baseline"]["credited"]
    assert "records 2 of declared/credited/uncovered" in joined(objective.validate(partial))

    summed = copy.deepcopy(pinned)
    summed["objectives"][0]["legs"][0]["baseline"]["uncovered"] = 5
    assert "the denominator does not add up" in joined(objective.validate(summed))

    unreadable = copy.deepcopy(pinned)
    unreadable["objectives"][0]["legs"][0]["baseline"]["declared"] = "1,027"
    assert "records baseline declared '1,027', not a number" in joined(
        objective.validate(unreadable)
    )

    unshaped = copy.deepcopy(pinned)
    unshaped["objectives"][0]["legs"][0]["baseline"] = [10, 6, 4]
    assert "has a 'baseline' value that is not an object" in joined(
        objective.validate(unshaped)
    )


def test_every_problem_is_listed_in_one_pass():
    """AC-OBJ-012: three or more simultaneous defects, all reported at once."""
    data = record(weights={"value": 9.0, "ghost": 1.0})
    data["objectives"][0]["legs"].append({**copy.deepcopy(LEG), "direction": "up"})
    data["objectives"][0]["status"] = "active"
    second = copy.deepcopy(data["objectives"][0])
    second.update({"id": "g1", "parent": "absent"})
    data["objectives"].append(second)
    problems = objective.validate(data)
    text = joined(problems)
    assert len(problems) >= 4
    assert "is declared 2 times" in text
    assert "declares direction 'up'" in text
    assert "outside [0.5, 3]" in text
    assert "weight 'ghost'" in text
    assert "2 objectives are active" in text
    assert "names parent 'absent'" in text


# ─── resolution ──────────────────────────────────────────────────────────────


def test_a_multi_leg_objective_needs_the_leg_named():
    """AC-OBJ-013: choosing a leg silently would substitute one half for another."""
    data = record()
    data["objectives"][0]["legs"].append({**copy.deepcopy(LEG), "name": "speed"})
    data["objectives"][0]["weights"] = {"value": 1.0, "speed": 0.5}
    with pytest.raises(objective.ObjectiveError, match="2 playable leg"):
        objective.resolve_leg(data)
    assert objective.resolve_leg(data, leg="speed")["weight"] == 0.5
    with pytest.raises(objective.ObjectiveError, match="not declared"):
        objective.resolve_leg(data, leg="absent")


def test_a_leg_at_its_floor_is_not_resolved():
    """AC-OBJ-013: the only leg cannot pay, so the record owes a fork — not a run."""
    data = record()
    data["objectives"][0]["legs"][0].update({"best": 0, "floor": 0})
    with pytest.raises(objective.ObjectiveError, match="0 playable leg"):
        objective.resolve_leg(data)


# ─── the CLI ─────────────────────────────────────────────────────────────────


def test_cli_validate_exits_1_and_lists_every_problem(tmp_path, capsys):
    """AC-OBJ-014: a dry validator an operator can run by hand, every problem at once."""
    data = record(weights={"value": 9.0})
    data["objectives"][0]["legs"][0]["direction"] = "sideways"
    data["objectives"][0]["legs"].append(copy.deepcopy(LEG))
    path = write_record(tmp_path, data)
    assert run_cli(["objective", "validate", "--file", str(path)]) == 1
    stderr = capsys.readouterr().err
    assert "is invalid" in stderr
    assert stderr.count("\n  - ") >= 3
    valid = write_record(tmp_path, record(), name="valid.json")
    assert run_cli(["objective", "validate", "--file", str(valid)]) == 0


def test_cli_validate_distinguishes_a_bad_path_from_a_bad_record(tmp_path, capsys):
    """AC-OBJ-014: an unreadable file is operator error (exit 2), content is exit 1.

    ``init`` already answers a missing file with exit 2; ``validate`` used to call
    it an invalid record, which reads as "the schema is wrong" to a wrapper script.
    """
    missing = tmp_path / "absent.json"
    assert run_cli(["objective", "validate", "--file", str(missing)]) == 2
    assert "cannot read" in capsys.readouterr().err

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert run_cli(["objective", "validate", "--file", str(broken)]) == 1
    assert "not valid JSON" in capsys.readouterr().err

    invalid = write_record(tmp_path, record(weights={"value": 9.0}), name="invalid.json")
    assert run_cli(["objective", "validate", "--file", str(invalid)]) == 1

    assert run_cli(["objective", "resolve", "--file", str(missing)]) == 2
    capsys.readouterr()


def test_cli_resolve_prints_the_init_arguments(tmp_path, capsys):
    """AC-OBJ-014: resolve emits plain argv, never shell text that is then run."""
    path = write_record(tmp_path, record())
    assert run_cli(["objective", "resolve", "--file", str(path)]) == 0
    argv = shlex.split(capsys.readouterr().out.strip())
    assert argv[argv.index("--metric-name") + 1] == "value"
    assert argv[argv.index("--direction") + 1] == "lower"
    assert argv[argv.index("--verify") + 1] == LEG["command"]
    assert argv[argv.index("--repeats") + 1] == "1"


# ─── init / report wiring ────────────────────────────────────────────────────


def test_init_from_an_objective_stores_the_reference_and_derives_the_metric(tmp_path):
    """AC-OBJ-016: the record feeds RunConfig; nothing is measured twice."""
    repo = make_target(tmp_path, value=10)
    path = write_record(tmp_path, record())
    assert run_cli(
        ["init", "--repo", str(repo), "--scope", "src", "--objective", str(path)]
    ) == 0
    cfg = json.loads((repo / ".autoresearch" / "run.json").read_text(encoding="utf-8"))
    assert cfg["objective_id"] == "g0"
    assert cfg["objective_leg"] == "value"
    assert cfg["objective_unit"] == "points"
    assert cfg["objective"] == str(path.resolve())
    assert cfg["metric_name"] == "value"
    assert cfg["direction"] == "lower"
    assert cfg["verify"] == LEG["command"]
    assert cfg["guard"] == LEG["guard"]
    assert cfg["repeats"] == 1
    assert cfg["protected"]


def test_explicit_flags_that_contradict_the_leg_are_refused(tmp_path, capsys):
    """AC-OBJ-016: an objective run cannot measure something its leg does not say.

    Deriving is a default; a contradiction is a different measurement wearing the
    objective's name, so a record built from it would disagree with its own record.
    Restating an equal value stays legal.
    """
    repo = make_target(tmp_path, value=10)
    path = write_record(tmp_path, record())
    assert run_cli(
        [
            "init", "--repo", str(repo), "--scope", "src",
            "--objective", str(path),
            "--metric-name", "value", "--direction", "higher",
            "--repeats", "2", "--verify", f"{sys.executable} score.py",
        ]
    ) == 2
    err = capsys.readouterr().err
    assert "contradict the leg" in err
    assert "--direction 'higher'" in err and "--repeats 2" in err

    assert run_cli(
        [
            "init", "--repo", str(repo), "--scope", "src",
            "--objective", str(path),
            "--metric-name", "value", "--direction", "lower",
            "--repeats", "1", "--noise-floor", "0.01",
            "--verify", LEG["command"], "--guard", LEG["guard"],
        ]
    ) == 0
    cfg = json.loads((repo / ".autoresearch" / "run.json").read_text(encoding="utf-8"))
    assert cfg["direction"] == "lower"
    assert cfg["repeats"] == 1
    assert cfg["objective_id"] == "g0"


def test_report_names_the_objective_and_an_old_run_is_unchanged(tmp_path):
    """AC-OBJ-016/AC-REC-012: the id is named when one exists; old runs stay byte-stable."""
    repo = make_target(tmp_path, value=10)
    path = write_record(tmp_path, record())
    assert run_cli(
        ["init", "--repo", str(repo), "--scope", "src", "--objective", str(path)]
    ) == 0
    assert run_cli(["report", "--repo", str(repo)]) == 0
    report = (repo / ".autoresearch" / "report.md").read_text(encoding="utf-8")
    assert "- objective: `g0` (leg `value`)" in report

    legacy = make_target(tmp_path, value=10, name="legacy")
    assert init_run(legacy) == 0
    assert run_cli(["report", "--repo", str(legacy)]) == 0
    old = (legacy / ".autoresearch" / "report.md").read_text(encoding="utf-8")
    assert "- objective:" not in old
    cfg = json.loads((legacy / ".autoresearch" / "run.json").read_text(encoding="utf-8"))
    assert cfg["objective"] is None and cfg["objective_id"] is None
