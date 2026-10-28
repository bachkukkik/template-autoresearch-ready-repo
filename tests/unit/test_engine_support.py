"""Shared fixtures for the autoresearch engine tests.

Not a test module: it builds throwaway git repos and drives the engine, so the
missive "the loop needs a real repo with real commits" is satisfied once.

The target repo is the smallest honest harness for the loop: ``src/value.txt``
holds an integer, ``score.py`` prints ``METRIC value=<int>`` and ``guard.py``
exits 0 iff that integer is non-negative. Every agent below is a small Python
script outside the repo, which is exactly what the ``command`` adapter is for.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

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


# ─── repo + agent builders ───────────────────────────────────────────────────


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def make_target(tmp_path, value=10, *, name="repo", score_body=None, guard_body=None):
    """A git repo whose metric is the integer in ``src/value.txt``."""
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "target@example.com")
    git(repo, "config", "user.name", "Target")
    (repo / "src").mkdir()
    (repo / "src" / "value.txt").write_text(f"{value}\n", encoding="utf-8")
    (repo / "score.py").write_text(score_body or SCORE_PY, encoding="utf-8")
    (repo / "guard.py").write_text(guard_body or GUARD_PY, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "init")
    return repo


def write_agent(tmp_path, body, name="agent.py"):
    """An agent stand-in: a python script run by the ``command`` adapter."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def agent_cmd(script):
    """The ``--agent-cmd`` template for a script that takes the repo as argv[1]."""
    return f"{sys.executable} {script} {{repo}}"


DECREMENT = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - {step}))
print("CHANGE: decrement value by {step}")
'''

INCREMENT = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) + 1))
print("CHANGE: increment value by 1")
'''

NO_CHANGE = '''
print("CHANGE: nothing to do")
'''

OUTSIDE_SCOPE = '''
import pathlib, sys

repo = pathlib.Path(sys.argv[1])
(repo / "src" / "value.txt").write_text("8")
(repo / "notes.txt").write_text("out of scope\\n")
print("CHANGE: edit outside the scope")
'''

PROTECTED_EDIT = '''
import pathlib, sys

repo = pathlib.Path(sys.argv[1])
(repo / "src" / "value.txt").write_text("8")
(repo / "score.py").write_text('print("METRIC value=0")\\n')
print("CHANGE: rewrite the score")
'''

GUARD_BREAK = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text("-1")
print("CHANGE: make the value negative")
'''


# ─── driving the engine ──────────────────────────────────────────────────────


def run_cli(argv):
    """Run the engine in-process; returns the exit code."""
    from autoresearch.cli import main

    return main(list(argv))


def init_args(repo, *, target=None, guard=True, repeats=1, direction="lower",
              scope="src", extra=()):
    argv = [
        "init",
        "--repo",
        str(repo),
        "--verify",
        f"{sys.executable} score.py",
        "--metric-name",
        "value",
        "--direction",
        direction,
        "--scope",
        scope,
        "--repeats",
        str(repeats),
    ]
    if guard:
        argv += ["--guard", f"{sys.executable} guard.py"]
    if target is not None:
        argv += ["--target", str(target)]
    return argv + list(extra)


def init_run(repo, **kwargs):
    return run_cli(init_args(repo, **kwargs))


def run_args(repo, script=None, *, agent="command", extra=()):
    argv = ["run", "--repo", str(repo), "--agent", agent]
    if script is not None:
        argv += ["--agent-cmd", agent_cmd(script)]
    return argv + list(extra)


def read_events(repo):
    import json

    path = Path(repo) / ".autoresearch" / "events.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def outcomes(repo):
    return [e["outcome"] for e in read_events(repo) if e.get("type") == "trial"]


def stop_reason(repo):
    """The last stop's reason, after proving the stops are well-formed.

    A resumed run appends a ``resume`` event before it iterates, so a second
    stop is only legal after one. Reading the *last* stop without that check
    would hide a resume that appended a duplicate stop — the ledger would look
    finished while it was actually invalid.
    """
    from autoresearch import ledger as ledger_mod

    events = read_events(repo)
    problems = [p for p in ledger_mod.validate(events) if "stop" in p or "resume" in p]
    assert not problems, problems
    stops = [e for e in events if e.get("type") == "stop"]
    return stops[-1]["reason"] if stops else None


def head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def value(repo):
    return int((Path(repo) / "src" / "value.txt").read_text(encoding="utf-8").strip())


def engine_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ENGINE)
    return env


def run_engine(*args, cwd=ROOT, timeout=180):
    """Run ``python3 -m autoresearch`` as a subprocess (the integration path)."""
    return subprocess.run(
        [sys.executable, "-m", "autoresearch", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=engine_env(),
    )


# ─── self-check ──────────────────────────────────────────────────────────────


def test_support_fixture_builds_a_clean_git_repo(tmp_path):
    """AC-ENG-000: the fixture itself is a clean repo with a working metric."""
    repo = make_target(tmp_path, value=10)
    assert git(repo, "status", "--porcelain").stdout == ""
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"

    proc = subprocess.run(
        [sys.executable, "score.py"], cwd=str(repo), capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "METRIC value=10" in proc.stdout
    assert subprocess.run(
        [sys.executable, "guard.py"], cwd=str(repo), check=False
    ).returncode == 0
