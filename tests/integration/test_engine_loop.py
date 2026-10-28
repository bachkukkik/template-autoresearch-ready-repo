"""The engine as a user meets it — the real CLI in a throwaway git repo.

IDs: AC-ENG-201, AC-ENG-202.

Every test here spawns ``python3 -m autoresearch`` with ``PYTHONPATH=engine``
against a tmp repo holding one integer in ``src/value.txt``, whose metric is
printed by ``score.py`` and whose guard rejects a negative. The contract under
test is therefore the one a wrapper script sees: exit codes, the JSON event
stream, and the bytes on disk — never an in-process call.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
STATE = ".autoresearch"

SCORE_PY = '''"""The measurement: one number, in the engine's preferred shape."""
import pathlib

value = int(pathlib.Path("src/value.txt").read_text().strip())
print(f"METRIC value={value}")
'''

GUARD_PY = '''"""The guard: a candidate that breaks behaviour has no business scoring."""
import pathlib
import sys

raw = pathlib.Path("src/value.txt").read_text().strip()
sys.exit(0 if raw.lstrip("-").isdigit() and int(raw) >= 0 else 1)
'''

DECREMENT = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - {step}))
print("CHANGE: decrement value by {step}")
'''


# ─── driving the CLI ─────────────────────────────────────────────────────────


def engine(*args, cwd, timeout=240):
    """Run ``python3 -m autoresearch <args>`` as a subprocess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ENGINE)
    return subprocess.run(
        [sys.executable, "-m", "autoresearch", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def git(repo, *args, timeout=120):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr.strip()}"
    return proc


def make_repo(path, value=10):
    """A git repo on ``main`` whose metric is the integer in ``src/value.txt``."""
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "target@example.com")
    git(path, "config", "user.name", "Target")
    (path / "src").mkdir()
    (path / "src" / "value.txt").write_text(f"{value}\n", encoding="utf-8")
    (path / "score.py").write_text(SCORE_PY, encoding="utf-8")
    (path / "guard.py").write_text(GUARD_PY, encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-m", "init")
    return path


def write_agent(tmp_path, step=2):
    """The ``--agent-cmd`` template of a script outside the repo."""
    script = tmp_path / "agent.py"
    script.write_text(DECREMENT.format(step=step), encoding="utf-8")
    return f"{sys.executable} {script} {{repo}}"


def init_args(repo, *, target=3):
    return [
        "init",
        "--repo",
        str(repo),
        "--verify",
        f"{sys.executable} score.py",
        "--guard",
        f"{sys.executable} guard.py",
        "--metric-name",
        "value",
        "--direction",
        "lower",
        "--scope",
        "src",
        "--target",
        str(target),
    ]


def json_events(stdout):
    """The ``--json`` event stream, one object per line."""
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def read_events(repo):
    path = Path(repo) / STATE / "events.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def trial_metrics(events):
    return [e["metric"] for e in events if e.get("type") == "trial"]


# ─── tests ───────────────────────────────────────────────────────────────────


def test_recorded_run_replays_to_the_same_metrics_through_the_cli(tmp_path):
    """AC-ENG-201: a run driven through the CLI on a command agent is recorded,
    then replayed in a fresh clone of its baseline commit on a named branch — no
    agent binary, no network — and produces the identical metric sequence, the
    same stop reason, and a report carrying the EVIDENCE section."""
    repo = make_repo(tmp_path / "repo", value=10)
    agent_cmd = write_agent(tmp_path, step=2)
    record = tmp_path / "rec.jsonl"

    proc = engine(*init_args(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (repo / STATE / "run.json").is_file()

    proc = engine(
        "run",
        "--repo",
        str(repo),
        "--agent",
        "command",
        "--agent-cmd",
        agent_cmd,
        "--max-iterations",
        "6",
        "--record",
        str(record),
        "--json",
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr

    stream = json_events(proc.stdout)
    outcomes = [e["outcome"] for e in stream if e.get("type") == "trial"]
    original = trial_metrics(stream)
    assert outcomes == ["keep", "keep", "keep", "keep"]
    assert original == [8.0, 6.0, 4.0, 2.0]
    assert stream[-1]["type"] == "stop"
    assert stream[-1]["reason"] == "target"

    # the ledger agrees with the stream it printed
    events = read_events(repo)
    assert [e["outcome"] for e in events if e.get("type") == "trial"] == outcomes
    assert trial_metrics(events) == original
    assert [e["reason"] for e in events if e.get("type") == "stop"] == ["target"]
    baseline = [e for e in events if e.get("type") == "baseline"][0]["commit"]

    # one record per committed iteration, each a real diff
    records = [json.loads(line) for line in record.read_text().splitlines() if line]
    assert [r["iteration"] for r in records] == [1, 2, 3, 4]
    assert "--- a/src/value.txt" in records[0]["patch"]

    proc = engine("status", "--repo", str(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "ledger: valid" in proc.stdout
    assert "stop target" in proc.stdout
    assert "4 iteration(s)" in proc.stdout

    proc = engine("report", "--repo", str(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("report.md")
    text = (repo / STATE / "report.md").read_text(encoding="utf-8")
    assert "EVIDENCE" in text
    for event in events:
        if event.get("outcome") == "keep":
            assert event["commit"] in text

    # replay: a fresh clone of the baseline commit, on a named branch
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(repo), str(clone)],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    git(clone, "config", "user.email", "replay@example.com")
    git(clone, "config", "user.name", "Replay")
    git(clone, "checkout", "-b", "replay", baseline)
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "replay"
    assert (clone / "src" / "value.txt").read_text().strip() == "10"

    proc = engine(*init_args(clone), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    proc = engine(
        "run",
        "--repo",
        str(clone),
        "--agent",
        "replay",
        "--replay",
        str(record),
        "--max-iterations",
        "6",
        "--json",
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr

    replayed = json_events(proc.stdout)
    assert trial_metrics(replayed) == original
    assert [e["outcome"] for e in replayed if e.get("type") == "trial"] == outcomes
    assert replayed[-1]["reason"] == "target"
    assert (clone / "src" / "value.txt").read_text().strip() == "2"
    assert trial_metrics(read_events(clone)) == original


def test_missing_agent_binary_exits_two_without_a_baseline(tmp_path):
    """AC-ENG-203: the documented exit code for a missing adapter binary is 2,
    and a run that never started must not leave a baseline behind."""
    repo = make_repo(tmp_path / "repo", value=10)
    assert engine(*init_args(repo), cwd=tmp_path).returncode == 0

    proc = engine(
        "run",
        "--repo",
        str(repo),
        "--agent",
        "command",
        "--agent-cmd",
        "/nonexistent/agent {prompt_file}",
        cwd=tmp_path,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "not on PATH" in proc.stderr
    assert "Traceback" not in proc.stderr
    assert read_events(repo) == []
    assert git(repo, "status", "--porcelain").stdout == ""


def test_dry_run_validates_and_touches_nothing(tmp_path):
    """AC-ENG-202: ``--dry-run`` proves the config, the guard, the metric and the
    adapter argv without an agent run, a commit, or a written event."""
    repo = make_repo(tmp_path / "repo", value=10)
    agent_cmd = write_agent(tmp_path, step=2)

    proc = engine(*init_args(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    before = git(repo, "rev-parse", "HEAD").stdout.strip()
    commits = git(repo, "rev-list", "--count", "HEAD").stdout.strip()

    proc = engine(
        "run",
        "--repo",
        str(repo),
        "--agent",
        "command",
        "--agent-cmd",
        agent_cmd,
        "--max-iterations",
        "3",
        "--dry-run",
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "dry run" in proc.stdout
    assert "metric: value=10" in proc.stdout
    assert "target <= 3" in proc.stdout
    assert "nothing was committed and no events were written" in proc.stdout

    assert git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == commits
    events = repo / STATE / "events.jsonl"
    assert not events.is_file() or events.read_text(encoding="utf-8").strip() == ""
    assert git(repo, "status", "--porcelain").stdout == ""
    assert (repo / "src" / "value.txt").read_text().strip() == "10"
