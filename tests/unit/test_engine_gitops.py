"""Git plumbing failures are config errors, not tracebacks. IDs: AC-ENG-081.

``git`` may be missing, or hang behind a timeout; either way the engine owes the
operator exit 2 and one line of explanation, not a stack trace.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import pytest

from test_engine_support import INCREMENT, init_run, make_target, run_args, run_cli, write_agent

from autoresearch import gitops


def test_a_missing_git_binary_is_a_git_error(tmp_path, monkeypatch):
    """AC-ENG-081: FileNotFoundError from the fork becomes a GitError."""
    repo = make_target(tmp_path)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(gitops.GitError):
        gitops.git(repo, "status")


def test_a_git_timeout_is_a_git_error(tmp_path, monkeypatch):
    """AC-ENG-081b: a hung git is bounded and reported as a GitError."""
    repo = make_target(tmp_path)

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git status", timeout=1)

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(gitops.GitError) as excinfo:
        gitops.git(repo, "status", timeout=1)
    assert "timed out" in str(excinfo.value)


def test_a_git_error_mid_run_exits_2(tmp_path, capsys, monkeypatch):
    """AC-ENG-081c: a GitError raised while reverting reaches the CLI as exit 2."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, INCREMENT)
    assert init_run(repo) == 0

    def broken(repo_path, commit, timeout=120.0, **kwargs):
        raise gitops.GitError("git reset --hard failed: disk on fire")

    monkeypatch.setattr(gitops, "reset_hard", broken)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 2

    captured = capsys.readouterr()
    assert "disk on fire" in captured.err
    assert "Traceback" not in captured.err


def test_bytecode_is_never_a_change(tmp_path):
    """AC-ENG-081d: running a script writes ``__pycache__``/``*.pyc``; that is
    the interpreter's side effect, not an agent edit, so it is not a change."""
    repo = make_target(tmp_path)
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"\x00")
    (repo / "src" / "loose.pyc").write_bytes(b"\x00")
    (repo / "src" / "value.txt").write_text("9\n", encoding="utf-8")

    changed = gitops.status_paths(repo)

    assert changed == ["src/value.txt"]
    assert gitops.is_noise_path("src/__pycache__/x.pyc")
    assert gitops.is_noise_path("x.pyc")
    assert not gitops.is_noise_path("src/x.py")
