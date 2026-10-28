"""Adapter argv and result handling. IDs: AC-ENG-030..033."""
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import os
import sys

import pytest

from test_engine_support import make_target, write_agent

from autoresearch.adapters import Adapter, AgentResult, load_records, make_adapter

PROMPT = "PROMPT-BODY"
REPO = "/tmp/repo"


def test_claude_argv_is_exact():
    """AC-ENG-030: the claude invocation shape is fixed — prompt, text output,
    edit permission and the tool allowlist, in that order."""
    adapter = Adapter("claude")
    assert adapter.argv(PROMPT, REPO) == [
        "claude",
        "-p",
        PROMPT,
        "--output-format",
        "text",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Read,Edit,Write,Glob,Grep,Bash",
    ]
    assert adapter.argv(PROMPT, REPO, model="claude-sonnet-4-5")[-2:] == [
        "--model",
        "claude-sonnet-4-5",
    ]
    assert adapter.argv(PROMPT, REPO, extra=["--foo"])[-1] == "--foo"
    assert adapter.binary == "claude"


def test_opencode_hermes_and_dsh_argv_are_exact():
    """AC-ENG-031: each harness keeps its own flag order, and each one gets the
    model flag only when a model was supplied."""
    opencode = Adapter("opencode")
    assert opencode.argv(PROMPT, REPO) == ["opencode", "run", "--dir", REPO, PROMPT]
    assert opencode.argv(PROMPT, REPO, model="m1") == [
        "opencode", "run", "--dir", REPO, "--model", "m1", PROMPT,
    ]

    hermes = Adapter("hermes")
    assert hermes.argv(PROMPT, REPO) == [
        "hermes", "chat", "-q", PROMPT, "-Q", "--yolo", "--in", REPO,
    ]
    assert hermes.argv(PROMPT, REPO, model="m2") == [
        "hermes", "chat", "-q", PROMPT, "-Q", "--yolo", "--in", REPO, "-m", "m2",
    ]

    dsh = Adapter("dsh")
    assert dsh.argv(PROMPT, REPO) == ["dsh", "--profile", "headless", PROMPT]
    assert dsh.argv(PROMPT, REPO, extra=["--verbose"]) == [
        "dsh", "--profile", "headless", "--verbose", PROMPT,
    ]


def test_command_adapter_substitutes_and_appends():
    """AC-ENG-032: {repo} and {prompt_file} are substituted per token, and extra
    argv lands after the template."""
    adapter = Adapter(
        "command",
        agent_cmd="runner --repo {repo} --prompt {prompt_file}",
        extra=["--flag", "value"],
    )
    argv = adapter.argv(PROMPT, REPO)
    assert argv == [
        "runner",
        "--repo",
        REPO,
        "--prompt",
        f"{REPO}/.autoresearch/prompt.txt",
        "--flag",
        "value",
    ]
    assert adapter.binary is None
    assert adapter.resolve_binary() == "runner"


def test_dsh_gets_the_workspace_environment_variable():
    """AC-ENG-032b: dsh is told which worktree it is in, and adapters keep the
    operator's credentials — the scrubbed env belongs to measurement, not to
    agents, which need their own auth to run at all."""
    env = Adapter("dsh").env(REPO)
    assert env["DEEPSEEK_HARNESS_WORKSPACE"] == REPO
    assert set(os.environ).issubset(set(Adapter("claude").env(REPO)))


def test_description_comes_from_the_change_line(tmp_path):
    """AC-ENG-033: the agent's summary is the last ``CHANGE:`` line; without one
    the iteration number is the description."""
    repo = make_target(tmp_path)
    script = write_agent(
        tmp_path,
        "print('thinking')\n"
        "print('CHANGE: first idea')\n"
        "print('CHANGE: tighten the inner loop')\n",
    )
    adapter = make_adapter("command", agent_cmd=f"{sys.executable} {script}")
    result = adapter.run("ignored", repo, 60, iteration=3)
    assert result.exit_code == 0
    assert result.description == "tighten the inner loop"
    assert isinstance(result, AgentResult)

    silent = write_agent(tmp_path, "print('no summary here')\n", name="silent.py")
    adapter = make_adapter("command", agent_cmd=f"{sys.executable} {silent}")
    assert adapter.run("ignored", repo, 60, iteration=3).description == "iteration 3"


def test_command_adapter_writes_the_prompt_file(tmp_path):
    """AC-ENG-033b: the prompt handed over is the prompt recorded on disk."""
    repo = make_target(tmp_path)
    script = write_agent(
        tmp_path,
        "import pathlib, sys\n"
        "text = pathlib.Path(sys.argv[1]).read_text()\n"
        "print('CHANGE: saw %d chars' % len(text))\n",
    )
    adapter = make_adapter(
        "command", agent_cmd=f"{sys.executable} {script} {{prompt_file}}"
    )
    result = adapter.run("hello engine", repo, 60, iteration=1)
    assert result.description == "saw 12 chars"
    assert (repo / ".autoresearch" / "prompt.txt").read_text() == "hello engine"


def test_replay_applies_a_recorded_patch_and_errors_when_missing(tmp_path):
    """AC-ENG-033c: replay is a patch application, and a missing record is an
    agent error rather than a silent no-op."""
    repo = make_target(tmp_path, value=10)
    patch = (
        "diff --git a/src/value.txt b/src/value.txt\n"
        "--- a/src/value.txt\n"
        "+++ b/src/value.txt\n"
        "@@ -1 +1 @@\n"
        "-10\n"
        "+7\n"
    )
    adapter = make_adapter(
        "replay",
        records=[{"iteration": 1, "description": "minus three", "patch": patch}],
    )
    assert adapter.argv(PROMPT, REPO) == []
    result = adapter.run("ignored", repo, 60, iteration=1)
    assert result.exit_code == 0
    assert result.description == "minus three"
    assert (repo / "src" / "value.txt").read_text().strip() == "7"

    missing = adapter.run("ignored", repo, 60, iteration=2)
    assert missing.exit_code != 0
    assert "no replay record" in missing.output_tail


def test_load_records_rejects_garbage(tmp_path):
    """AC-ENG-033d: a malformed record file fails loudly at load."""
    path = tmp_path / "rec.jsonl"
    path.write_text('{"iteration": 1, "patch": ""}\n', encoding="utf-8")
    assert load_records(path)[0]["iteration"] == 1

    path.write_text("{oops\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(path)


def test_unknown_agent_is_rejected():
    """AC-ENG-033e: the adapter list is closed."""
    with pytest.raises(ValueError):
        Adapter("gpt5-cli")


def test_command_adapter_requires_a_command():
    """AC-ENG-033f: the command adapter without --agent-cmd cannot run."""
    with pytest.raises(ValueError):
        Adapter("command")


# ─── the description is untrusted text (AC-ENG-033g) ─────────────────────────


def test_description_strips_control_characters_and_is_capped(tmp_path):
    """AC-ENG-033g: the ``CHANGE:`` summary becomes a commit subject and a report
    table cell, so control characters go, whitespace collapses and the line is
    capped at 120 characters."""
    repo = make_target(tmp_path)
    noisy = write_agent(
        tmp_path,
        "print('CHANGE: fix\\x07the\\ttabs\\x1b[31m and   the  spaces')\n",
    )
    adapter = make_adapter("command", agent_cmd=f"{sys.executable} {noisy}")
    description = adapter.run("ignored", repo, 60, iteration=1).description
    assert description == "fix the tabs [31m and the spaces"
    assert len(description) <= 120

    long = write_agent(tmp_path, "print('CHANGE: ' + 'x' * 300)\n", name="long.py")
    adapter = make_adapter("command", agent_cmd=f"{sys.executable} {long}")
    assert adapter.run("ignored", repo, 60, iteration=1).description == "x" * 120


# ─── Ctrl-C must kill the harness (AC-ENG-034b) ──────────────────────────────


def test_ctrl_c_kills_the_running_agent(tmp_path, monkeypatch):
    """AC-ENG-034b: the loop reverts the worktree after Ctrl-C, so a harness
    still writing must not be left behind."""
    import subprocess
    import time

    repo = make_target(tmp_path)
    pidfile = tmp_path / "agent.pid"
    script = write_agent(
        tmp_path,
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n",
    )

    def interrupted(self, timeout=None):
        for _ in range(500):
            if pidfile.exists():
                break
            time.sleep(0.01)
        raise KeyboardInterrupt

    adapter = make_adapter("command", agent_cmd=f"{sys.executable} {script}")
    monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)
    with pytest.raises(KeyboardInterrupt):
        adapter.run("ignored", repo, 60, iteration=1)
    monkeypatch.undo()

    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    gone = False
    while time.monotonic() < deadline:
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            gone = True
            break
        if reaped == pid:
            gone = os.WIFSIGNALED(status)
            break
        time.sleep(0.02)
    assert gone
