"""Record/replay, status and report. IDs: AC-ENG-060..064."""
import json
import subprocess
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from test_engine_support import (  # noqa: E402
    DECREMENT,
    git,
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


def trial_metrics(repo):
    return [
        e["metric"]
        for e in read_events(repo)
        if e.get("type") == "trial" and e.get("metric") is not None
    ]


def clone_at(tmp_path, repo, commit, name="clone"):
    """A fresh clone parked on a named branch at ``commit`` — replay's start point."""
    clone = tmp_path / name
    subprocess.run(["git", "clone", str(repo), str(clone)], capture_output=True, check=True)
    git(clone, "config", "user.email", "replay@example.com")
    git(clone, "config", "user.name", "Replay")
    git(clone, "checkout", "-b", "replay", commit)
    return clone


def test_record_writes_patches_and_replay_reproduces_the_run(tmp_path):
    """AC-ENG-060: a live run becomes replayable — the same patches, applied in a
    fresh clone, produce the same metric sequence without the agent present."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    record = tmp_path / "record.jsonl"
    assert init_run(repo, target=3) == 0

    assert run_cli(
        run_args(
            repo,
            script,
            extra=["--max-iterations", "6", "--record", str(record)],
        )
    ) == 0

    records = [json.loads(line) for line in record.read_text().splitlines()]
    assert [r["iteration"] for r in records] == [1, 2, 3, 4]
    assert all(r["description"] == "decrement value by 2" for r in records)
    # the patch is a real unified diff of the candidate against its incumbent
    assert "--- a/src/value.txt" in records[0]["patch"]
    assert "+8" in records[0]["patch"]

    original = trial_metrics(repo)
    assert original == [8.0, 6.0, 4.0, 2.0]

    baseline = [e for e in read_events(repo) if e.get("type") == "baseline"][0]["commit"]
    clone = clone_at(tmp_path, repo, baseline)
    assert run_cli(init_args(clone, target=3)) == 0

    assert run_cli(
        run_args(
            clone,
            None,
            agent="replay",
            extra=["--replay", str(record), "--max-iterations", "6"],
        )
    ) == 0

    assert trial_metrics(clone) == original
    assert [e["outcome"] for e in read_events(clone) if e.get("type") == "trial"] == [
        "keep", "keep", "keep", "keep",
    ]
    assert (clone / "src" / "value.txt").read_text().strip() == "2"


def test_replay_without_a_record_for_the_iteration_is_an_agent_error(tmp_path):
    """AC-ENG-060b: replay does not silently skip a missing iteration."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    record = tmp_path / "record.jsonl"
    assert init_run(repo) == 0
    assert run_cli(
        run_args(repo, script, extra=["--max-iterations", "1", "--record", str(record)])
    ) == 0

    clone = clone_at(tmp_path, repo, head(repo))
    assert run_cli(init_args(clone)) == 0
    assert run_cli(
        run_args(
            clone,
            None,
            agent="replay",
            extra=["--replay", str(record), "--max-iterations", "2"],
        )
    ) == 0

    trial_outcomes = [e["outcome"] for e in read_events(clone) if e.get("type") == "trial"]
    assert trial_outcomes == ["no_change", "agent_error"]


def test_status_summarises_a_valid_run(tmp_path, capsys):
    """AC-ENG-061: status replays the ledger and reports the incumbent, the
    improvement and how the run ended."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "6"])) == 0
    capsys.readouterr()

    assert run_cli(["status", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "baseline 10" in out
    assert "best 2" in out
    assert "+80.00%" in out
    assert "4 iteration(s)" in out
    assert "stop target" in out
    assert "ledger: valid" in out

    assert run_cli(["status", "--repo", str(repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["problems"] == []
    assert payload["iteration_count" if "iteration_count" in payload else "iterations"] == 4


def test_status_exits_three_on_a_tampered_ledger(tmp_path, capsys):
    """AC-ENG-062: a ledger that cannot be replayed is exit 3 and names the
    violation — a rewritten history must not read as a success."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    path = repo / STATE / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    for event in events:
        if event.get("type") == "trial" and event["outcome"] == "keep":
            event["metric"] = 99.0  # a keep that never beat its incumbent
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    assert run_cli(["status", "--repo", str(repo)]) == 3
    captured = capsys.readouterr()
    assert "INVALID" in captured.err
    assert "not better than the incumbent" in captured.err

    # report refuses to render a history that does not replay
    assert run_cli(["report", "--repo", str(repo)]) == 3


def test_report_has_evidence_with_reproduce_commands(tmp_path, capsys):
    """AC-ENG-063: the report does not ask to be believed — every keep carries the
    commit and the command that reproduces its metric."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3, extra=["--goal", "shrink the value"]) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "6"])) == 0
    capsys.readouterr()

    assert run_cli(["report", "--repo", str(repo)]) == 0
    printed = capsys.readouterr().out.strip()
    assert printed.endswith("report.md")

    text = (repo / STATE / "report.md").read_text()
    assert "# autoresearch report" in text
    assert "shrink the value" in text
    assert "## EVIDENCE" in text
    keeps = [e for e in read_events(repo) if e.get("outcome") == "keep"]
    assert keeps
    for keep in keeps:
        assert keep["commit"] in text
        assert f"git checkout {keep['commit']} && " in text
    assert text.count("git checkout") == len(keeps)
    assert "| iter | commit | outcome | metric | description |" in text

    # --out writes somewhere else and still prints the path
    custom = tmp_path / "out" / "run.md"
    assert run_cli(["report", "--repo", str(repo), "--out", str(custom)]) == 0
    assert custom.is_file()
    assert "## EVIDENCE" in custom.read_text()


def test_report_renders_a_missing_commit_as_a_dash(tmp_path):
    """AC-ENG-063b: an empty ledger has no commits, and ``None`` is not a sha —
    a run that recorded nothing must still read as a report, not a bug."""
    from autoresearch import config as config_mod
    from autoresearch import report as report_mod

    repo = make_target(tmp_path, value=10)
    assert init_run(repo) == 0

    text = report_mod.render_markdown(config_mod.load(repo), [])
    assert "- baseline: - (`-`)" in text
    assert "- best: - (`-`)" in text
    assert "None" not in text


def test_results_tsv_is_a_flat_export(tmp_path):
    """AC-ENG-064: results.tsv mirrors the ledger for a spreadsheet, baseline
    included as iteration 0."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "6"])) == 0
    assert run_cli(["report", "--repo", str(repo)]) == 0

    lines = (repo / STATE / "results.tsv").read_text().splitlines()
    assert lines[0] == "iter\tcommit\tmetric\toutcome\tdescription"
    assert lines[1].split("\t")[0] == "0"
    assert lines[1].split("\t")[3] == "baseline"
    rows = [line.split("\t") for line in lines[1:]]
    assert [row[3] for row in rows] == ["baseline", "keep", "keep", "keep", "keep"]
    assert [row[2] for row in rows] == ["10", "8", "6", "4", "2"]
    assert all(row[4] for row in rows)


# ─── agent-controlled text in the report (AC-ENG-063b) ───────────────────────


def test_a_pipe_in_a_description_cannot_break_the_trial_table():
    """AC-ENG-063b: the description is agent text inside a markdown table, so a
    ``|`` in it must be escaped rather than split the row."""
    from types import SimpleNamespace

    from autoresearch import report as report_mod

    cfg = SimpleNamespace(
        repo="/r", verify="python3 score.py", guard=None, metric_name="value",
        direction="lower", target=None, noise_floor=0.01, repeats=1,
        scope=("src",), protected={}, protected_paths=lambda: [], goal=None,
    )
    events = [
        {"type": "baseline", "seq": 1, "metric": 10.0, "commit": "a" * 40,
         "direction": "lower", "noise_floor": 0.01},
        {"type": "trial", "seq": 2, "iteration": 1, "outcome": "keep", "metric": 8.0,
         "commit": "b" * 40, "description": "a | b | c", "guard": "pass"},
    ]

    text = report_mod.render_markdown(cfg, events)

    assert "a \\| b \\| c" in text
    assert "| a | b | c |" not in text
