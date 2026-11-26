"""Cost beside score: tokens, wall seconds and the rates they enable.

IDs: AC-MCV-001..005 (PRD 30 SC-mcv-1..3). The rule under test throughout is
that a cost is *additive*: it is recorded where it is known, recorded as an
explicit null where it is not, and never reaches the decision. A verdict, a
delta and a margin are the same numbers whether or not a trial was priced.
"""
import sys
from pathlib import Path

import pytest

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

from test_engine_support import (  # noqa: E402
    make_target,
    init_run,
    read_events,
    run_args,
    run_cli,
    write_agent,
)

from autoresearch import measure as measure_mod  # noqa: E402
from autoresearch import report as report_mod  # noqa: E402
from autoresearch import usage as usage_mod  # noqa: E402

#: A candidate that shrinks the metric, then says nothing about what it cost.
SILENT_AGENT = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - 2))
print("CHANGE: decrement value by 2")
'''

#: The same candidate on a harness that reports usage on its transcript.
PRICED_AGENT = SILENT_AGENT + '''
import json

print(json.dumps({"message": {"usage": {"input_tokens": 900, "output_tokens": 334}}}))
'''


def _measurements(values):
    """The scripted verify series: a baseline, then one candidate."""
    return iter(
        [measure_mod.Measurement(value, [float(value)], 1.5, True) for value in values]
    )


def _settle(tmp_path, monkeypatch, agent_body, name="repo", values=(10.0, 8.0)):
    """Run one iteration with scripted measurements; return ``(repo, trial)``.

    The measurement is scripted so two runs differ in exactly one thing — what
    the harness printed about its usage — which is what AC-MCV-005 compares.
    """
    repo = make_target(tmp_path, value=10, name=name)
    assert init_run(repo) == 0
    script = write_agent(tmp_path, agent_body, name=f"{name}-agent.py")
    scripted = _measurements(values)
    monkeypatch.setattr(measure_mod, "measure", lambda cfg, *, log=None: next(scripted))
    argv = run_args(repo, script, extra=["--max-iterations", "1"])
    assert run_cli(argv) == 0
    trials = [e for e in read_events(repo) if e.get("type") == "trial"]
    assert len(trials) == 1
    return repo, trials[0]


def _events(*trials):
    """A valid ledger: one baseline, then the trials given."""
    rows = [
        {
            "type": "baseline", "seq": 1, "metric": 10.0, "commit": "a" * 40,
            "direction": "lower", "noise_floor": 0.01,
        }
    ]
    for index, extra in enumerate(trials, start=2):
        row = {
            "type": "trial", "seq": index, "iteration": index - 1,
            "direction": "lower", "noise_floor": 0.01, "commit": "b" * 40,
            "description": "a change",
        }
        row.update(extra)
        rows.append(row)
    return rows


# ─── reading usage off a transcript (AC-MCV-001) ─────────────────────────────


def test_usage_is_read_from_every_accepted_shape_or_reported_absent():
    """AC-MCV-001: the four shapes a harness prints are decoded, input+output is
    summed when there is no total, and a transcript with no usage line yields
    ``None`` — never a zero, never a guess from prose.
    """
    assert usage_mod.tokens_from_transcript('{"usage": {"total_tokens": 120}}') == 120
    assert usage_mod.tokens_from_transcript(
        '{"usage": {"input_tokens": 90, "output_tokens": 30}}'
    ) == 120
    assert usage_mod.tokens_from_transcript(
        '{"message": {"usage": {"input_tokens": 90, "output_tokens": 30}}}'
    ) == 120
    assert usage_mod.tokens_from_transcript('{"part": {"usage": {"total_tokens": 7}}}') == 7

    # A stated total wins over the pair it was derived from.
    assert usage_mod.tokens_from_transcript(
        '{"usage": {"total_tokens": 5, "input_tokens": 1, "output_tokens": 1}}'
    ) == 5

    # Half a sum is not a total, and prose is not a measurement.
    assert usage_mod.tokens_from_transcript('{"usage": {"input_tokens": 90}}') is None
    assert usage_mod.tokens_from_transcript("CHANGE: shave the value\nok\n") is None
    assert usage_mod.tokens_from_transcript("") is None
    assert usage_mod.tokens_from_transcript('{"usage": {}}') is None


# ─── a settled trial carries its cost (AC-MCV-002) ───────────────────────────


def test_a_settled_trial_records_null_tokens_not_zero(tmp_path, monkeypatch):
    """AC-MCV-002: a harness that reports no usage still leaves a ``cost`` dict —
    ``tokens`` present and null, ``wall_seconds`` a real measurement. Zero would
    claim the agent was free; absence would claim nothing was tried.
    """
    _repo, trial = _settle(tmp_path, monkeypatch, SILENT_AGENT)

    assert trial["outcome"] == "keep"
    assert "cost" in trial
    assert trial["cost"]["tokens"] is None
    assert trial["cost"]["tokens"] != 0
    assert isinstance(trial["cost"]["wall_seconds"], float)
    assert trial["cost"]["wall_seconds"] > 0


def test_a_settled_trial_records_the_tokens_its_transcript_reported(tmp_path, monkeypatch):
    """AC-MCV-002: when the transcript does carry usage, the trial's cost is that
    number — read from the one helper, not recomputed anywhere in the loop.
    """
    _repo, trial = _settle(tmp_path, monkeypatch, PRICED_AGENT)

    assert trial["outcome"] == "keep"
    assert trial["cost"]["tokens"] == 1234  # 900 input + 334 output
    assert trial["cost"]["wall_seconds"] > 0


# ─── the report prints a denominator (AC-MCV-003) ────────────────────────────


def test_the_cost_section_prints_rates_over_settled_trials():
    """AC-MCV-003: keeps per 100k tokens and per hour, over settled trials only,
    with the numerator read from the same subset as its denominator.
    """
    events = _events(
        {"outcome": "keep", "metric": 8.0, "guard": "pass",
         "cost": {"tokens": 150000, "wall_seconds": 1800.0}},
        {"outcome": "discard", "metric": 9.0, "guard": "pass",
         "cost": {"tokens": 50000, "wall_seconds": 900.0}},
        {"outcome": "inconclusive", "metric": 9.0, "guard": "pass",
         "cost": {"tokens": None, "wall_seconds": 300.0}},
    )

    lines = report_mod.cost_lines(events)

    assert lines[0] == "keeps: 1 / 3 settled"
    # 200k tokens across the two trials that reported them; one of them kept.
    assert lines[1] == "keeps / 100k tokens: 0.50"
    # 3000 s = 1/1.2 h; one keep among the trials that reported a wall time.
    assert lines[2] == "keeps / hour: 1.20"


def test_the_cost_section_says_why_it_cannot_divide():
    """AC-MCV-003: an unknown denominator prints ``n/a`` with its reason — for a
    trial that recorded null, and for a ledger written before cost existed.
    """
    unknown = _events(
        {"outcome": "keep", "metric": 8.0, "guard": "pass",
         "cost": {"tokens": None, "wall_seconds": None}},
    )
    legacy = _events({"outcome": "keep", "metric": 8.0, "guard": "pass"})

    for events in (unknown, legacy):
        lines = report_mod.cost_lines(events)
        assert lines[0] == "keeps: 1 / 1 settled"
        assert lines[1] == "keeps / 100k tokens: n/a (no token usage)"
        assert lines[2] == "keeps / hour: n/a (no wall time)"

    # An unsettled trial is not a denominator either: it measured nothing.
    unsettled = _events({"outcome": "agent_error", "metric": None,
                         "cost": {"tokens": 900, "wall_seconds": 1.0}})
    assert report_mod.cost_lines(unsettled)[0] == "keeps: 0 / 0 settled"


def test_the_rendered_report_carries_the_cost_section():
    """AC-MCV-003: the section is in ``report.md``, not merely a helper."""
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        repo="/r", verify="python3 score.py", guard=None, metric_name="value",
        direction="lower", target=None, noise_floor=0.01, repeats=1,
        scope=("src",), protected={}, protected_paths=lambda: [], goal=None,
    )
    events = _events(
        {"outcome": "keep", "metric": 8.0, "guard": "pass",
         "cost": {"tokens": 100000, "wall_seconds": 3600.0}},
    )

    text = report_mod.render_markdown(cfg, events)

    assert "## Cost" in text
    assert "keeps: 1 / 1 settled" in text
    assert "keeps / 100k tokens: 1.00" in text
    assert "keeps / hour: 1.00" in text


# ─── the tsv export gains two columns (AC-MCV-004) ───────────────────────────


def test_results_tsv_adds_the_cost_columns_and_leaves_them_empty():
    """AC-MCV-004: ``tokens`` and ``wall_seconds`` are trailing columns, empty
    rather than zero when unknown — the baseline never has a cost, and an
    unknown count is not a measured one.
    """
    events = _events(
        {"outcome": "keep", "metric": 8.0, "guard": "pass",
         "cost": {"tokens": 150000, "wall_seconds": 1800.0}},
        {"outcome": "discard", "metric": 9.0, "guard": "pass",
         "cost": {"tokens": None, "wall_seconds": 12.5}},
    )

    lines = report_mod.results_tsv(events).splitlines()

    assert lines[0] == (
        "iter\tcommit\tmetric\toutcome\tdescription\ttokens\twall_seconds"
    )
    assert lines[1].split("\t")[5:] == ["", ""]        # baseline
    assert lines[2].split("\t")[5:] == ["150000", "1800"]
    assert lines[3].split("\t")[5:] == ["", "12.5"]    # null tokens, real wall


# ─── cost never changes a verdict (AC-MCV-005) ───────────────────────────────


def test_cost_never_changes_a_verdict_delta_or_margin(tmp_path, monkeypatch):
    """AC-MCV-005 (SC-mcv-3): the same trial, once priced and once not, settles
    with an identical verdict, delta and margin. Cost is recorded beside the
    decision and feeds nothing in it.
    """
    priced_repo, priced = _settle(
        tmp_path, monkeypatch, PRICED_AGENT, name="priced"
    )
    silent_repo, silent = _settle(
        tmp_path, monkeypatch, SILENT_AGENT, name="silent"
    )

    # The two runs really did differ in what they recorded.
    assert priced["cost"]["tokens"] == 1234
    assert silent["cost"]["tokens"] is None

    # …and in nothing else that the decision was made of.
    for key in ("outcome", "metric", "margin", "se", "spread", "values", "guard"):
        assert priced[key] == silent[key], key
    assert priced["outcome"] == "keep"

    # The delta is what a reader computes from the two metrics; equal inputs
    # make it equal, which is the claim SC-mcv-3 makes.
    def delta(repo, trial):
        baseline = [e for e in read_events(repo) if e.get("type") == "baseline"][0]
        return baseline["metric"] - trial["metric"]

    assert delta(priced_repo, priced) == delta(silent_repo, silent) == pytest.approx(2.0)
