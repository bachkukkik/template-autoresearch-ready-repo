"""The prompt — the whole interface to the agent for one iteration.

IDs: AC-ENG-070..076. These are pure-function tests: a ``RunConfig`` and a
``PromptState`` in, the exact instruction block out, so a section that silently
disappears (or grows without bound) is caught without running a loop.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from autoresearch import config as config_mod  # noqa: E402
from autoresearch import prompt as prompt_mod  # noqa: E402


def make_cfg(**overrides):
    data = dict(
        repo="/tmp/repo",
        verify="python3 score.py",
        metric_name="value",
        direction="lower",
        scope=("src",),
        guard="python3 guard.py",
        target=3.0,
        noise_floor=0.01,
        protected={"score.py": "0" * 64, "guard.py": "1" * 64},
        goal="shrink the value",
    )
    data.update(overrides)
    return config_mod.RunConfig(**data)


def make_state(**overrides):
    data = dict(baseline=10.0, incumbent=8.0, incumbent_commit="abc1234def", trials=[])
    data.update(overrides)
    return prompt_mod.PromptState(**data)


def test_prompt_states_the_goal_metric_scope_and_protected_files():
    """AC-ENG-070: the agent is told the goal, the number it is optimising, the
    direction, where it may write and what it must never touch."""
    text = prompt_mod.build_prompt(make_cfg(), make_state())

    assert "shrink the value" in text
    assert "name: value" in text
    assert "direction: lower is better" in text
    assert "baseline: 10" in text
    assert "incumbent: 8" in text
    assert "target: 3" in text
    assert "- src" in text
    assert "Protected files — DO NOT EDIT" in text
    assert "- score.py" in text and "- guard.py" in text


def test_prompt_carries_the_rules_the_agent_must_keep():
    """AC-ENG-071: one change, no git, and a ``CHANGE:`` line — the three rules an
    agent left to itself always breaks."""
    text = prompt_mod.build_prompt(make_cfg(), make_state())

    assert "ONE coherent change" in text
    assert "Do NOT run git commit" in text
    assert "CHANGE:" in text


def test_prompt_shows_only_the_last_eight_trials():
    """AC-ENG-072: the history is bounded — a 200-iteration run must not send a
    200-row table back to the agent."""
    trials = [
        {"iteration": i, "outcome": "discard", "metric": 10.0 + i, "description": f"attempt {i}"}
        for i in range(1, 11)
    ]
    text = prompt_mod.build_prompt(make_cfg(), make_state(trials=trials))

    assert "- iter 10:" in text
    assert "- iter 3:" in text
    assert "- iter 2:" not in text
    assert prompt_mod.TRIALS_SHOWN == 8


def test_prompt_lists_dead_ends_once_each():
    """AC-ENG-073: what already failed is listed, deduplicated, and never
    includes a keep."""
    trials = [
        {"iteration": 1, "outcome": "guard_failed", "metric": None, "description": "negative value"},
        {"iteration": 2, "outcome": "keep", "metric": 8.0, "description": "decrement"},
        {"iteration": 3, "outcome": "discard", "metric": 9.0, "description": "negative value"},
        {"iteration": 4, "outcome": "crash", "metric": None, "description": "divide by zero"},
    ]
    text = prompt_mod.build_prompt(make_cfg(), make_state(trials=trials))

    assert "Dead ends — do not repeat" in text
    dead_ends = text.split("Dead ends — do not repeat")[1]
    assert dead_ends.count("- negative value") == 1
    assert "- divide by zero" in dead_ends
    assert "- decrement" not in dead_ends


def test_prompt_has_no_failure_section_without_a_failure():
    """AC-ENG-074: an empty log is not a section — the prompt does not invite the
    agent to read a blank code block."""
    assert "Last failure" not in prompt_mod.build_prompt(make_cfg(), make_state())


def test_prompt_carries_only_the_tail_of_the_last_failure():
    """AC-ENG-075: the last 40 lines of failure output, no more — the agent needs
    the error, not a 4000-line transcript."""
    log = "\n".join(f"line {i}" for i in range(1, 61))
    text = prompt_mod.build_prompt(make_cfg(), make_state(last_failure_log=log))

    assert "## Last failure (tail)" in text
    section = text.split("## Last failure (tail)")[1]
    lines = [line for line in section.splitlines() if line.startswith("line ")]
    assert len(lines) == prompt_mod.FAILURE_LOG_LINES == 40
    assert lines[0] == "line 21"
    assert lines[-1] == "line 60"
    assert "line 20" not in section


def test_prompt_includes_the_program_when_one_is_configured():
    """AC-ENG-076: standing instructions come first, because they outrank the
    per-iteration advice below them."""
    text = prompt_mod.build_prompt(
        make_cfg(program="Always prefer the smaller diff.\n"), make_state()
    )
    assert "## Program" in text
    assert "Always prefer the smaller diff." in text
    assert text.index("## Program") < text.index("## Goal")
