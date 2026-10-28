"""Ledger append + replay validation. IDs: AC-ENG-020..025."""
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import json

from autoresearch import ledger as ledger_mod

OUTCOME_OK = dict(description="a change", direction="lower", noise_floor=0.01, commit="c0ffee")


def baseline(metric=10.0, seq=1, commit="base0"):
    return {
        "type": "baseline",
        "seq": seq,
        "metric": metric,
        "commit": commit,
        "direction": "lower",
        "noise_floor": 0.01,
    }


def trial(seq, iteration, outcome, metric, guard=None, commit="cand0"):
    event = {"type": "trial", "seq": seq, "iteration": iteration, "outcome": outcome,
             "metric": metric, **OUTCOME_OK, "commit": commit}
    if guard is not None:
        event["guard"] = guard
    return event


def stop(seq, reason="target"):
    return {"type": "stop", "seq": seq, "reason": reason, "iteration": 1}


def resume(seq, iteration=1):
    return {"type": "resume", "seq": seq, "iteration": iteration}


def test_valid_ledger_has_no_violations():
    """AC-ENG-020: a faithful ledger replays cleanly — including a keep that is
    better and a discard that is not."""
    events = [
        baseline(10.0),
        trial(2, 1, "keep", 8.0, guard="pass"),
        trial(3, 2, "discard", 9.5, guard="pass"),
        trial(4, 3, "no_change", None),
        stop(5),
    ]
    assert ledger_mod.validate(events) == []


def test_keep_that_did_not_beat_the_incumbent_is_a_violation():
    """AC-ENG-021: a keep must be re-decidable — 9.95 is inside the 1% floor
    around 10, so it could never have been kept."""
    events = [baseline(10.0), trial(2, 1, "keep", 9.95, guard="pass"), stop(3)]
    problems = ledger_mod.validate(events)
    assert any("not better than the incumbent" in p for p in problems)


def test_keep_with_a_failing_guard_is_a_violation():
    """AC-ENG-021b: a candidate that broke behaviour cannot be recorded as kept."""
    events = [baseline(10.0), trial(2, 1, "keep", 8.0, guard="fail"), stop(3)]
    assert any("must be 'pass'" in p for p in ledger_mod.validate(events))


def test_keep_toward_zero_on_a_negative_metric_is_a_violation():
    """AC-ENG-021c: a negative metric's keeps are re-decided with the floor's
    magnitude, so a candidate that merely moved toward zero cannot replay."""
    baseline_negative = {
        "type": "baseline",
        "seq": 1,
        "metric": -5.0,
        "commit": "base0",
        "direction": "lower",
        "noise_floor": 0.01,
    }
    worse = [baseline_negative, trial(2, 1, "keep", -4.97, guard="pass"), stop(3)]
    assert any("not better than the incumbent" in p for p in ledger_mod.validate(worse))

    better = [baseline_negative, trial(2, 1, "keep", -5.5, guard="pass"), stop(3)]
    assert ledger_mod.validate(better) == []


def test_sequence_must_be_contiguous_from_one():
    """AC-ENG-022: a gap or a reordering breaks replay, so it is reported."""
    events = [baseline(10.0, seq=1), trial(3, 1, "keep", 8.0, guard="pass")]
    assert any("sequence must be contiguous" in p for p in ledger_mod.validate(events))

    reordered = [baseline(10.0, seq=2), trial(1, 1, "keep", 8.0, guard="pass")]
    assert any("contiguous" in p for p in ledger_mod.validate(reordered))


def test_unknown_outcome_is_a_violation():
    """AC-ENG-023: the outcome vocabulary is closed."""
    events = [baseline(10.0), trial(2, 1, "improved", 8.0, guard="pass")]
    assert any("unknown outcome 'improved'" in p for p in ledger_mod.validate(events))


def test_stop_must_be_last_and_unique():
    """AC-ENG-024: a stop that is not last means the run kept going after
    stopping, so the history is not a history."""
    events = [baseline(10.0), stop(2), trial(3, 1, "keep", 8.0, guard="pass")]
    problems = ledger_mod.validate(events)
    assert any("stop event must be the last event" in p for p in problems)

    twice = [baseline(10.0), stop(2), stop(3)]
    assert any("at most one stop" in p for p in ledger_mod.validate(twice))


def test_resume_supersedes_a_stop_and_opens_a_new_segment():
    """AC-ENG-024c: a resumed run is legal — one stop per segment, a stop only
    followed by a resume, and the incumbent chain continues across the seam."""
    events = [
        baseline(10.0),
        trial(2, 1, "keep", 8.0, guard="pass"),
        stop(3, "max_iterations"),
        resume(4, 2),
        trial(5, 2, "keep", 6.0, guard="pass"),
        stop(6),
    ]
    assert ledger_mod.validate(events) == []


def test_two_stops_without_a_resume_are_still_a_violation():
    """AC-ENG-024d: the resume is the only thing that may follow a stop, so a
    plain second stop is still rejected."""
    events = [baseline(10.0), trial(2, 1, "keep", 8.0, guard="pass"), stop(3), stop(4)]
    problems = ledger_mod.validate(events)
    assert any("at most one stop" in p for p in problems)
    assert not any("'resume' must follow" in p for p in problems)


def test_resume_without_a_stop_is_a_violation():
    """AC-ENG-024e: a resume is a claim that a stop happened, so it needs one."""
    events = [baseline(10.0), resume(2), trial(3, 1, "keep", 8.0, guard="pass"), stop(4)]
    assert any("'resume' must follow a 'stop'" in p for p in ledger_mod.validate(events))


def test_baseline_must_come_first_and_exactly_once():
    """AC-ENG-024b: the incumbent chain has to start somewhere."""
    assert any("exactly one baseline" in p for p in ledger_mod.validate([trial(1, 1, "discard", 9.0)]))
    events = [baseline(10.0), baseline(10.0, seq=2)]
    assert any("exactly one baseline" in p for p in ledger_mod.validate(events))


def test_append_assigns_seq_and_ts_and_survives_a_reread(tmp_path):
    """AC-ENG-025: every append is durable, monotonic and timestamped UTC."""
    path = tmp_path / "events.jsonl"
    ledger = ledger_mod.Ledger(path)
    first = ledger.append({"type": "baseline", "metric": 1.0, "commit": "abc"})
    second = ledger.append({"type": "trial", "outcome": "discard", "iteration": 1})

    assert (first["seq"], second["seq"]) == (1, 2)
    assert first["ts"].endswith("Z") and "T" in first["ts"]

    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [e["seq"] for e in lines] == [1, 2]

    # A second writer object resumes the sequence instead of restarting it.
    assert ledger_mod.Ledger(path).append({"type": "stop"})["seq"] == 3


def test_tampered_json_line_is_reported_not_crashed_on(tmp_path):
    """AC-ENG-025b: a corrupt ledger is an error the CLI can map to exit 3.

    A bad line in the middle is tampering, not a torn append — the events that
    follow it would be read against a history that is already wrong.
    """
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"type": "baseline", "seq": 1}\nnot json\n'
        '{"type": "stop", "seq": 3, "reason": "target"}\n',
        encoding="utf-8",
    )
    events, problems = ledger_mod.load(path)
    assert events == []
    assert problems and "not valid JSON" in problems[0]


# ─── a torn final line (AC-ENG-025c) ─────────────────────────────────────────


def test_a_torn_final_line_is_reported_and_skipped(tmp_path, capsys):
    """AC-ENG-025c: a crash mid-append leaves half a line at the end. Refusing
    to read the ledger at all wedged the run forever; the torn line is dropped
    with a warning and the events before it still validate."""
    path = tmp_path / "events.jsonl"
    good = [baseline(), trial(2, 1, "discard", 11.0), stop(3, "plateau")]
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in good)
        + '{"type": "trial", "seq": 4, "iter',
        encoding="utf-8",
    )

    ledger = ledger_mod.Ledger(path)
    events = ledger.read()

    assert [event["type"] for event in events] == ["baseline", "trial", "stop"]
    assert ledger_mod.validate(events) == []
    assert "truncated" in capsys.readouterr().err


def test_a_bad_line_before_the_end_is_still_fatal(tmp_path):
    """AC-ENG-025d: tolerance is only for the *last* line — a corrupt line with
    events after it is a real ledger error, not a torn append."""
    import pytest

    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(baseline()) + "\n{oops\n" + json.dumps(stop(3)) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ledger_mod.LedgerError):
        ledger_mod.Ledger(path).read()
