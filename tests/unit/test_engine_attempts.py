"""Attempts that never settled still leave a row. IDs: AC-MCV-010..013.

An iteration that dies — an unexpected failure, or a signal — writes one
``attempt`` event naming the stage it died in and what it had spent. It is an
event kind, not a verdict: every reader that switches on a verdict skips it, so
the counts it does not belong to do not move.
"""
import json
import sys
from pathlib import Path

import pytest

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

from test_engine_support import (  # noqa: E402
    DECREMENT,
    head,
    init_run,
    make_target,
    read_events,
    run_args,
    run_cli,
    value,
    write_agent,
)

from autoresearch import config as config_mod  # noqa: E402
from autoresearch import ledger as ledger_mod  # noqa: E402
from autoresearch import measure as measure_mod  # noqa: E402
from autoresearch import report as report_mod  # noqa: E402

STATE = ".autoresearch"


def _repo_with_run(tmp_path, value_at=10, name="repo"):
    repo = make_target(tmp_path, value=value_at, name=name)
    assert init_run(repo) == 0
    script = write_agent(tmp_path, DECREMENT.format(step=2), name=f"{name}-agent.py")
    return repo, script


def _die_on_the_candidate(monkeypatch, error):
    """Let the baseline measure, then make the candidate's verify raise."""
    calls = {"count": 0}

    def flaky(cfg, *, log=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return measure_mod.Measurement(10.0, [10.0], 0.01, True)
        raise error

    monkeypatch.setattr(measure_mod, "measure", flaky)


def _attempts(repo):
    return [e for e in read_events(repo) if e.get("type") == "attempt"]


# ─── a death leaves one row (AC-MCV-010) ─────────────────────────────────────


def test_an_unexpected_failure_records_one_attempt_and_no_trial(tmp_path, monkeypatch):
    """AC-MCV-010: a verify that raises settles nothing, so no trial event is
    written — and the iteration is not silently dropped either. One ``attempt``
    records the phase it died in, the agent's exit code and its cost, and the
    ledger still replays.
    """
    repo, script = _repo_with_run(tmp_path)
    _die_on_the_candidate(monkeypatch, RuntimeError("the referee exploded"))

    with pytest.raises(RuntimeError):
        run_cli(run_args(repo, script, extra=["--max-iterations", "1"]))

    events = read_events(repo)
    assert [e["type"] for e in events if e["type"] == "trial"] == []
    attempts = _attempts(repo)
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["phase"] == "measure"
    assert attempt["exit_code"] == 0          # the agent itself finished cleanly
    assert attempt["cost"]["tokens"] is None  # this agent reported no usage
    assert attempt["cost"]["wall_seconds"] >= 0
    assert ledger_mod.validate(events) == []


def test_a_death_in_the_guard_phase_is_named_as_the_guard(tmp_path, monkeypatch):
    """AC-MCV-010: the phase is the stage that was *running*, not a constant. A
    guard that raises is recorded as ``guard``; only those four names exist, so a
    reader can map a row back to the pipeline it died in.
    """
    assert set(ledger_mod.ATTEMPT_PHASES) == {
        "agent", "measure", "guard", "interrupted",
    }

    repo, script = _repo_with_run(tmp_path)
    real_guard = measure_mod.run_guard
    calls = {"count": 0}

    def flaky_guard(cfg):
        calls["count"] += 1
        if calls["count"] == 1:
            return real_guard(cfg)
        raise RuntimeError("the guard blew up")

    monkeypatch.setattr(measure_mod, "run_guard", flaky_guard)
    with pytest.raises(RuntimeError):
        run_cli(run_args(repo, script, extra=["--max-iterations", "1"]))

    attempt = _attempts(repo)[0]
    assert attempt["phase"] == "guard"
    assert attempt["exit_code"] == 0


# ─── an interrupt leaves one row (AC-MCV-011) ────────────────────────────────


def test_an_interrupted_iteration_records_an_attempt_and_still_exits_zero(
    tmp_path, monkeypatch
):
    """AC-MCV-011: Ctrl-C mid-iteration records ``interrupted``, restores the
    worktree and closes the segment — the run ends normally, and the record says
    what it had spent instead of pretending the round never happened.
    """
    repo, script = _repo_with_run(tmp_path)
    before = head(repo)
    _die_on_the_candidate(monkeypatch, KeyboardInterrupt())

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    events = read_events(repo)
    attempts = _attempts(repo)
    assert len(attempts) == 1
    assert attempts[0]["phase"] == "interrupted"
    assert attempts[0]["cost"]["wall_seconds"] >= 0
    assert [e["reason"] for e in events if e.get("type") == "stop"] == ["interrupted"]
    assert head(repo) == before
    assert value(repo) == 10
    assert ledger_mod.validate(events) == []


def test_a_settled_trial_or_a_guard_rejection_is_never_an_attempt(tmp_path):
    """AC-MCV-011: ``attempt`` means "died before settling". A kept candidate
    settled, and a guard rejection settled as ``guard_failed`` — neither owes an
    attempt row, and neither costs a second record of the same iteration.
    """
    repo, script = _repo_with_run(tmp_path)
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    assert [e["outcome"] for e in read_events(repo) if e["type"] == "trial"] == ["keep"]
    assert _attempts(repo) == []

    guard_repo, guard_script = _repo_with_run(tmp_path, name="guarded")
    from test_engine_support import GUARD_BREAK

    breaker = write_agent(tmp_path, GUARD_BREAK, name="breaker.py")
    assert run_cli(
        run_args(guard_repo, breaker, extra=["--max-iterations", "1"])
    ) == 0
    outcomes = [e["outcome"] for e in read_events(guard_repo) if e["type"] == "trial"]
    assert outcomes == ["guard_failed"]
    assert _attempts(guard_repo) == []
    # A guard rejection is not a settled verdict, so it records no cost either.
    trial = [e for e in read_events(guard_repo) if e["type"] == "trial"][0]
    assert "cost" not in trial


# ─── readers accept an attempt without a metric (AC-MCV-012) ─────────────────


def test_status_and_report_accept_an_attempt_without_a_metric(tmp_path, capsys):
    """AC-MCV-012: ``attempt`` carries no metric. ``status`` and ``report`` read
    it without a KeyError, and every count they already published is unchanged —
    the attempt is added beside the totals, not into them.
    """
    repo = make_target(tmp_path, value=10)
    assert init_run(repo) == 0
    cfg = config_mod.load(repo)
    commit = head(repo)
    keep = "c" * 40
    ledger = ledger_mod.Ledger(cfg.events_path)
    ledger.append(
        {
            "type": "baseline", "metric": 10.0, "values": [10.0], "commit": commit,
            "direction": "lower", "noise_floor": 0.01,
            "guard": cfg.guard, "verify": cfg.verify,
        }
    )
    ledger.append(
        {
            "type": "trial", "iteration": 1, "outcome": "keep", "metric": 8.0,
            "values": [8.0], "direction": "lower", "noise_floor": 0.01,
            "guard": "pass", "commit": keep, "description": "a change",
            "cost": {"tokens": 900, "wall_seconds": 1.0},
        }
    )
    # What the run published before the attempt existed.
    before = report_mod.summarize(cfg, ledger.read())

    ledger.append(
        {
            "type": "attempt", "phase": "guard", "exit_code": None,
            "cost": {"tokens": None, "wall_seconds": 12.5},
        }
    )
    ledger.append(
        {
            "type": "stop", "reason": "max_iterations", "iteration": 1,
            "metric": 8.0, "commit": keep,
        }
    )
    assert ledger_mod.validate(read_events(repo)) == []
    capsys.readouterr()

    assert run_cli(["status", "--repo", str(repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["attempts"] == 1
    assert payload["unsettled"] is True
    for key in ("iterations", "outcomes", "best_metric", "best_commit",
                "baseline_metric", "improvement_pct"):
        assert payload[key] == before[key], key

    assert run_cli(["report", "--repo", str(repo)]) == 0
    text = (Path(cfg.state_dir) / "report.md").read_text(encoding="utf-8")
    assert text.count("unsettled: 1 attempt(s)") == 1
    assert f"- iterations: {before['iterations']}" in text


# ─── a run of attempts alone still reports (AC-MCV-013) ──────────────────────


def test_a_run_with_attempts_and_no_trials_reports_in_one_line(tmp_path, capsys):
    """AC-MCV-013: a run that tried and never settled renders a report saying so
    in exactly one line, and exits 0. The totals are labelled a lower bound
    rather than presented as a complete record of a round that never finished.
    """
    repo = make_target(tmp_path, value=10)
    assert init_run(repo) == 0
    cfg = config_mod.load(repo)
    ledger = ledger_mod.Ledger(cfg.events_path)
    ledger.append(
        {
            "type": "baseline", "metric": 10.0, "values": [10.0],
            "commit": head(repo), "direction": "lower", "noise_floor": 0.01,
            "guard": cfg.guard, "verify": cfg.verify,
        }
    )
    ledger.append(
        {
            "type": "attempt", "phase": "agent", "exit_code": 1,
            "cost": {"tokens": 900, "wall_seconds": 4.0},
        }
    )
    ledger.append(
        {
            "type": "stop", "reason": "interrupted", "iteration": 0,
            "metric": 10.0, "commit": head(repo),
        }
    )
    events = read_events(repo)
    assert ledger_mod.validate(events) == []
    capsys.readouterr()

    assert run_cli(["status", "--repo", str(repo)]) == 0
    capsys.readouterr()
    assert run_cli(["report", "--repo", str(repo)]) == 0

    text = (Path(cfg.state_dir) / "report.md").read_text(encoding="utf-8")
    assert text.count(
        "unsettled: 1 attempt(s) — the totals above are a lower bound"
    ) == 1
    assert "keeps: 0 / 0 settled" in text
    assert "keeps / 100k tokens: n/a (no token usage)" in text

    summary = report_mod.summarize(cfg, events)
    assert summary["attempts"] == 1
    assert summary["unsettled"] is True
    assert summary["iterations"] == 0


def test_a_clean_run_says_nothing_about_attempts(tmp_path):
    """AC-MCV-013: with no attempt, neither the summary nor the report invents
    an ``unsettled`` note — the totals above are complete.
    """
    repo, script = _repo_with_run(tmp_path)
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    events = read_events(repo)

    assert report_mod.summarize(config_mod.load(repo), events)["unsettled"] is False
    assert report_mod.unsettled_line(events) is None


def test_a_refusal_leaves_the_history_untouched(tmp_path, monkeypatch):
    """AC-MCV-013: an exception the CLI reports as a *refusal* (exit 2/3) is the
    engine declining to proceed, not an iteration that died — so it writes no
    attempt and the ledger keeps exactly the events it had.
    """
    repo, script = _repo_with_run(tmp_path)

    def refuse(*args, **kwargs):
        raise ledger_mod.LedgerError("cannot hash profile: simulated")

    monkeypatch.setattr(ledger_mod, "provenance_block", refuse)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 3

    events = read_events(repo)
    assert [event["type"] for event in events] == ["baseline"]
    assert _attempts(repo) == []
