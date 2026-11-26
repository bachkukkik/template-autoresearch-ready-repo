"""Cost survives the whole pipeline: ledger, report and tsv. ID: AC-MCV-201.

A scripted replay over a throwaway git repo: the fake agent edits the scored
file and prints one JSONL usage object, the loop settles the trial, and the
report is expected to publish the denominator. The second half of the contract
is the absence case — a harness that says nothing about usage yields a null
token count, an ``n/a`` rate, and an *empty* tsv cell, never a zero.

The contract under test is the one a wrapper script sees: the real
``python3 -m autoresearch`` CLI, a throwaway repo, a scripted agent, no model
and no network.
"""
import sys
from pathlib import Path

# tests/unit owns the engine harness (repo builder, argv builders, subprocess
# runner); the integration tier imports it rather than re-cloning it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

import test_engine_support as support  # noqa: E402

sys.path.insert(0, str(support.ENGINE))

STATE = ".autoresearch"

#: A candidate that shrinks the metric and reports usage on its transcript, the
#: way a structured harness does: one JSON object per line.
PRICED_AGENT = '''
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - 2))
print("CHANGE: decrement value by 2")
print(json.dumps({"message": {"usage": {"input_tokens": 200000,
                                        "output_tokens": 50000}}}))
'''

#: The same candidate from a harness that reports no usage at all.
SILENT_AGENT = '''
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - 2))
print("CHANGE: decrement value by 2")
'''


def run_one(tmp_path, agent_body, name="repo"):
    """Init a repo, run one iteration with this agent, return ``(repo, events)``."""
    repo = support.make_target(tmp_path, value=10, name=name)
    reserve = support.run_engine(*support.init_args(repo), cwd=tmp_path)
    assert reserve.returncode == 0, reserve.stderr
    agent = support.write_agent(tmp_path, agent_body, name=f"{name}-agent.py")
    argv = support.run_args(repo, agent, extra=["--max-iterations", "1"])
    proc = support.run_engine(*argv, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return repo, support.read_events(repo)


def report_of(repo, tmp_path):
    proc = support.run_engine("report", "--repo", str(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return (repo / STATE / "report.md").read_text(encoding="utf-8")


def tsv_rows(repo):
    text = (repo / STATE / "results.tsv").read_text(encoding="utf-8")
    return [line.split("\t") for line in text.splitlines()]


def _positive(value):
    """True when a tsv cell holds a positive number — the wall is always known."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def test_a_priced_trial_publishes_its_cost_everywhere(tmp_path):
    """AC-MCV-201 (a): a settled keep whose harness reported 250k tokens carries
    that cost in the ledger, a real ``keeps / 100k tokens`` rate in the report
    and the two trailing tsv columns — 1 keep over 2.5 lots of 100k tokens.
    """
    repo, events = run_one(tmp_path, PRICED_AGENT)

    trials = [e for e in events if e.get("type") == "trial"]
    assert [t["outcome"] for t in trials] == ["keep"]
    assert trials[0]["cost"]["tokens"] == 250000
    assert trials[0]["cost"]["wall_seconds"] > 0
    assert not [e for e in events if e.get("type") == "attempt"]

    text = report_of(repo, tmp_path)
    assert "## Cost" in text
    assert "keeps: 1 / 1 settled" in text
    assert "keeps / 100k tokens: 0.40" in text
    hour_lines = [line for line in text.splitlines()
                  if line.startswith("keeps / hour:")]
    assert len(hour_lines) == 1
    assert hour_lines[0] != "keeps / hour: n/a (no wall time)"
    assert float(hour_lines[0].split(": ")[1]) > 0

    rows = tsv_rows(repo)
    assert rows[0] == [
        "iter", "commit", "metric", "outcome", "description", "tokens",
        "wall_seconds",
    ]
    assert rows[1][5:] == ["", ""]               # the baseline has no cost
    keeps = [row for row in rows[1:] if row[3] == "keep"]
    assert len(keeps) == 1
    assert keeps[0][5] == "250000"
    assert float(keeps[0][6]) > 0


def test_a_silent_harness_yields_null_tokens_and_an_empty_cell(tmp_path):
    """AC-MCV-201 (b): absent usage stays absent end to end — a null in the
    ledger, ``n/a`` with its reason in the report, and an empty tsv cell, so no
    reader can mistake an unknown cost for a free one.
    """
    repo, events = run_one(tmp_path, SILENT_AGENT, name="silent")

    trials = [e for e in events if e.get("type") == "trial"]
    assert [t["outcome"] for t in trials] == ["keep"]
    assert trials[0]["cost"]["tokens"] is None
    assert trials[0]["cost"]["tokens"] != 0
    assert trials[0]["cost"]["wall_seconds"] > 0

    text = report_of(repo, tmp_path)
    assert "keeps: 1 / 1 settled" in text
    assert "keeps / 100k tokens: n/a (no token usage)" in text
    assert "keeps / hour: " in text and "n/a (no wall time)" not in text

    rows = tsv_rows(repo)
    keeps = [row for row in rows[1:] if row[3] == "keep"]
    assert keeps[0][5] == ""                        # empty, not "0"
    assert _positive(keeps[0][6])
