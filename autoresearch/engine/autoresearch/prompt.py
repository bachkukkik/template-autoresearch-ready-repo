"""Prompt construction for one iteration.

The prompt is the whole interface to the agent, so it carries everything the
agent needs to make a single legal change and nothing that invites it to
improvise: what the goal is, which metric is being optimised, what the scope is,
which files are off limits — and the two things an agent left to itself never
remembers: don't touch git, and finish with a one-line ``CHANGE:`` summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from . import decide as decide_mod

TRIALS_SHOWN = 8
DEAD_ENDS_SHOWN = 10
FAILURE_LOG_LINES = 40

#: The opt-in claim contract (PRD 29). One line, four labels, and the word
#: ``HYPOTHESIS:`` appears nowhere else in the prompt — the reader scores the
#: claim, so the prompt must ask for exactly one.
CLAIM_INSTRUCTION = (
    "6. Finish with a single line: CHANGE: <one-line summary> | "
    "HYPOTHESIS: <the claim being tested> | "
    "PREDICT: <the number you expect, signed> | "
    "FALSIFIED IF: <what result would refute it>"
)


@dataclass
class PromptState:
    """What the loop knows when it composes the next prompt."""

    baseline: Optional[float]
    incumbent: Optional[float]
    incumbent_commit: str = ""
    trials: Sequence[dict] = field(default_factory=list)
    last_failure_log: str = ""
    #: Ask for a falsifiable claim on the mandatory line. Off by default: with
    #: it off the rendered prompt is byte-for-byte what it was before PRD 29.
    hypotheses: bool = False


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "unknown"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _section(title: str, body: List[str]) -> List[str]:
    return [f"## {title}", *body, ""]


def build_prompt(cfg, state: PromptState) -> str:
    """Compose the instruction block for one iteration."""
    lines: List[str] = ["# autoresearch — one iteration", ""]

    if cfg.program:
        lines += _section("Program", cfg.program.rstrip().splitlines())

    lines += _section("Goal", [cfg.goal.strip() if cfg.goal else "(no goal recorded)"])

    lines += _section(
        "Metric",
        [
            f"name: {cfg.metric_name}",
            "direction: " + ("lower is better" if cfg.direction == "lower" else "higher is better"),
            f"baseline: {_fmt(state.baseline)}",
            f"incumbent: {_fmt(state.incumbent)}",
            f"target: {_fmt(cfg.target) if cfg.target is not None else '(none — improve indefinitely)'}",
        ],
    )

    lines += _section(
        "Scope — you may edit only these paths",
        [f"- {scope}" for scope in cfg.scope],
    )

    protected = cfg.protected_paths()
    if protected:
        lines += _section(
            "Protected files — DO NOT EDIT",
            [f"- {path}" for path in protected],
        )

    closing = (
        CLAIM_INSTRUCTION
        if state.hypotheses
        else "6. Finish with a single line: CHANGE: <one-line summary>"
    )
    lines += _section(
        "Rules",
        [
            "1. Make exactly ONE coherent change.",
            "2. Edit only paths inside the scope above. Anything else is rejected and reverted.",
            "3. Do NOT run git commit, git reset or git checkout — the harness owns git.",
            "4. Do not modify the verify or guard commands or the files that implement them.",
            "5. Keep behaviour correct: the guard must pass and the verify command must still print the metric.",
            closing,
        ],
    )

    recent = list(state.trials)[-TRIALS_SHOWN:]
    if recent:
        rows = [
            f"- iter {t.get('iteration')}: {t.get('outcome')}, metric {_fmt(t.get('metric'))} — {t.get('description')}"
            for t in recent
        ]
        lines += _section("Recent trials", rows)
    else:
        lines += _section("Recent trials", ["(none yet — this is the first attempt)"])

    dead_ends: List[str] = []
    unproven: List[str] = []
    filed = set()
    for trial in reversed(state.trials):
        if len(dead_ends) >= DEAD_ENDS_SHOWN and len(unproven) >= DEAD_ENDS_SHOWN:
            break
        # An inconclusive run is not a dead end: the change moved the metric and
        # only failed to clear the noise, so "do not repeat it" would abandon a
        # working direction. It gets its own list with the actionable advice.
        outcome = trial.get("outcome")
        if outcome == "keep":
            continue
        description = (trial.get("description") or "").strip()
        if not description:
            continue
        # One description, one section: newest-first, so the first sighting is
        # that description's latest outcome; a change that was a dead end and
        # came back inconclusive is not listed as both.
        if description in filed:
            continue
        bucket = unproven if outcome == decide_mod.INCONCLUSIVE else dead_ends
        # Each section carries its own cap: a run with no inconclusive trials
        # would never fill the other list, so a single "both are full" test let
        # a long string of discards grow the prompt without bound.
        if len(bucket) >= DEAD_ENDS_SHOWN:
            continue
        bucket.append(description)
        filed.add(description)
    if unproven:
        lines += _section(
            "Inconclusive — unproven, retry only with a larger change",
            [
                f"- {description}: improvement smaller than the measurement noise"
                for description in unproven
            ],
        )
    if dead_ends:
        lines += _section("Dead ends — do not repeat", [f"- {d}" for d in dead_ends])

    if state.last_failure_log:
        tail = state.last_failure_log.rstrip().splitlines()[-FAILURE_LOG_LINES:]
        lines += _section("Last failure (tail)", ["```", *tail, "```"])

    return "\n".join(lines).rstrip() + "\n"
