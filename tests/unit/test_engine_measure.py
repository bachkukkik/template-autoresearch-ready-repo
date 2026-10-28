"""Metric parsing, environment scrubbing and command execution. IDs: AC-ENG-001..005."""
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import sys

from test_engine_support import make_target

from autoresearch import measure


# ─── parse_metric ────────────────────────────────────────────────────────────


def test_metric_shapes_in_priority_order():
    """AC-ENG-001: METRIC beats a labelled line, and a labelled line beats a
    bare final float."""
    both = "value: 1.5\nMETRIC value=2.5\n"
    assert measure.parse_metric(both, "value") == 2.5

    labelled = "METRIC other=9.0\nvalue: 3.25\n"
    assert measure.parse_metric(labelled, "value") == 3.25

    bare = "noise line\n4.75\n"
    assert measure.parse_metric(bare, "value") == 4.75


def test_last_matching_line_wins_and_missing_is_none():
    """AC-ENG-002: a script may log a header value then the final one; the last
    match wins, and a name that never appears parses to None."""
    text = "METRIC value=9\nworking...\nMETRIC value=4\n"
    assert measure.parse_metric(text, "value") == 4.0

    assert measure.parse_metric("METRIC other=4\n", "value") is None
    # A bare float is only accepted as the *last* non-empty line.
    assert measure.parse_metric("4.5\nstill running\n", "value") is None
    assert measure.parse_metric("", "value") is None
    # Integers, signs and exponents are all floats.
    assert measure.parse_metric("METRIC value=-1e3\n", "value") == -1000.0


# ─── environment scrubbing ───────────────────────────────────────────────────


def test_scrubbed_env_drops_credential_shaped_names():
    """AC-ENG-003: any variable whose *name* looks like a credential is removed
    from a measurement child, whatever its value."""
    env = {
        "PATH": "/usr/bin",
        "OPENAI_API_KEY": "sk-live-should-never-reach-verify",
        "AWS_SECRET_ACCESS_KEY": "x",
        "GITHUB_TOKEN": "y",
        "DB_PASSWORD": "z",
        "SERVICE_CREDENTIAL": "w",
        "HOME": "/root",
        "MY_KEYSTORE_NOTE": "name-contains-KEY-so-it-goes",
        "PYTHONPATH": "/engine",
    }
    scrubbed = measure.scrub_env(env)
    assert set(scrubbed) == {"PATH", "HOME", "PYTHONPATH"}
    assert "sk-" not in repr(scrubbed)


def test_measurement_child_never_sees_the_key(tmp_path, monkeypatch):
    """AC-ENG-003b: the scrubbed env reaches the actual child process."""
    repo = make_target(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live")
    (repo / "env.py").write_text(
        "import os, sys\n"
        "print('METRIC value=1' if 'OPENAI_API_KEY' not in os.environ else 'METRIC value=0')\n",
        encoding="utf-8",
    )
    result = measure.run_command(f"{sys.executable} env.py", repo, 60)
    assert result.exit_code == 0
    assert "METRIC value=1" in result.stdout


# ─── running commands ────────────────────────────────────────────────────────


def test_run_command_timeout_kills_the_child(tmp_path):
    """AC-ENG-004: every subprocess call is bounded; a hung verify is killed and
    reported as timed out rather than hanging the loop."""
    repo = make_target(tmp_path)
    (repo / "slow.py").write_text(
        "import time\ntime.sleep(30)\nprint('METRIC value=1')\n", encoding="utf-8"
    )
    result = measure.run_command(f"{sys.executable} slow.py", repo, 0.5)
    assert result.timed_out is True
    # timeout + the bounded drain, with slack — not "whatever the child felt like"
    assert result.seconds < 3


def test_measure_repeats_and_median(tmp_path):
    """AC-ENG-005: repeats are reduced by median, and a failing run is not ok."""
    from types import SimpleNamespace

    def cfg(repo, command, repeats=1):
        return SimpleNamespace(
            verify=command,
            metric_name="value",
            repeats=repeats,
            verify_timeout=60,
            repo=str(repo),
        )

    repo = make_target(tmp_path)
    (repo / "noisy.py").write_text(
        "import random\n"
        "print('METRIC value=' + str(random.choice([2, 4, 9])))\n",
        encoding="utf-8",
    )

    measurement = measure.measure(cfg(repo, f"{sys.executable} noisy.py", repeats=3))
    assert measurement.ok is True
    assert len(measurement.values) == 3
    assert measurement.value == sorted(measurement.values)[1]

    (repo / "broken.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    broken = measure.measure(cfg(repo, f"{sys.executable} broken.py"))
    assert broken.ok is False
    assert broken.value is None
    assert "exit 3" in broken.log_tail

    (repo / "silent.py").write_text("print('no metric here')\n", encoding="utf-8")
    silent = measure.measure(cfg(repo, f"{sys.executable} silent.py"))
    assert silent.ok is False
    assert "no 'value' metric" in silent.log_tail


# ─── a killed child cannot outlive its timeout (AC-ENG-004b/c) ───────────────

LEAKY_GRANDCHILD = '''
import subprocess, sys, time

# A grandchild in its own session inherits our stdout and holds the pipe open.
subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(30)"],
    stdout=sys.stdout,
    start_new_session=True,
)
print("METRIC value=1", flush=True)
time.sleep(30)
'''

SLEEPER = '''
import os, pathlib, time

pathlib.Path(%r).write_text(str(os.getpid()))
time.sleep(30)
'''


def _wait_gone(pid, seconds=5.0):
    """True once ``pid`` has exited (reaped by us or gone already)."""
    import os
    import time as clock

    end = clock.monotonic() + seconds
    while clock.monotonic() < end:
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if reaped == pid:
            return os.WIFSIGNALED(status)
        clock.sleep(0.02)
    return False


def test_timeout_is_bounded_even_when_a_grandchild_holds_the_pipe(tmp_path):
    """AC-ENG-004b: killing the process group does not close a pipe a ``setsid``
    grandchild still holds, so the drain after the kill must be bounded too.
    Otherwise ``--verify-timeout`` is not a bound at all."""
    repo = make_target(tmp_path)
    (repo / "leaky.py").write_text(LEAKY_GRANDCHILD, encoding="utf-8")

    result = measure.run_command(f"{sys.executable} leaky.py", repo, 1)

    assert result.timed_out is True
    assert result.seconds < 7  # timeout 1 s + the 5 s drain, plus slack


def test_ctrl_c_kills_the_running_child(tmp_path, monkeypatch):
    """AC-ENG-004c: an interrupt must not orphan the child — the group is killed
    before the KeyboardInterrupt propagates to the loop."""
    import subprocess
    import time

    import pytest

    repo = make_target(tmp_path)
    pidfile = tmp_path / "sleeper.pid"
    (repo / "sleeper.py").write_text(SLEEPER % str(pidfile), encoding="utf-8")

    def interrupted(self, timeout=None):
        for _ in range(500):
            if pidfile.exists():
                break
            time.sleep(0.01)
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)
    with pytest.raises(KeyboardInterrupt):
        measure.run_command(f"{sys.executable} sleeper.py", repo, 60)
    monkeypatch.undo()

    assert _wait_gone(int(pidfile.read_text()))
