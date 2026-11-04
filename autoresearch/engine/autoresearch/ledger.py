"""The event ledger: append-only, fsync'd, and replay-validated.

``events.jsonl`` is the run's record of truth. It is append-only because a run
that can rewrite its own history cannot be audited, and it is validated on every
read because a ledger that is merely *written* is not evidence — the point of
replaying the decision rule over it is to prove the recorded keeps were legal
under the very rule that produced them.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import decide as decide_mod

EVENT_TYPES = ("init", "baseline", "trial", "stop", "resume")

OUTCOMES = (
    "keep",
    "discard",
    "guard_failed",
    "crash",
    "no_change",
    "scope_violation",
    "protected_violation",
    "agent_error",
)

#: Outcomes that mean "the candidate never produced a usable measurement".
CRASH_OUTCOMES = ("crash", "agent_error")


class LedgerError(Exception):
    """The ledger cannot be read or is invalid. The CLI maps it to exit 3."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Ledger:
    """Append-only writer/reader for one run's ``events.jsonl``."""

    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)
        self._seq: Optional[int] = None

    # -- reading -------------------------------------------------------------

    def read(self) -> List[Dict]:
        if not self.path.is_file():
            return []
        events: List[Dict] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        # The final non-empty line may be a torn append (the process died
        # mid-write). Refusing to read the ledger at all wedged the run forever,
        # so that one line is dropped with a warning; every earlier line must
        # still parse, because a corrupt line with events after it is a real
        # ledger error rather than a half-written tail.
        last_content = max(
            (index for index, line in enumerate(lines, start=1) if line.strip()),
            default=0,
        )
        for number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError as exc:
                if number == last_content:
                    print(
                        f"{self.path}:{number}: ignoring a truncated final line "
                        f"({exc})",
                        file=sys.stderr,
                    )
                    break
                raise LedgerError(
                    f"{self.path}:{number} is not valid JSON: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise LedgerError(f"{self.path}:{number} is not a JSON object")
            events.append(event)
        return events

    def read_tolerant(self) -> Tuple[List[Dict], List[str]]:
        """Read as much as possible; return ``(events, violations)``."""
        try:
            return self.read(), []
        except LedgerError as exc:
            return [], [str(exc)]

    def last_seq(self) -> int:
        if self._seq is None:
            events = self.read()
            self._seq = int(events[-1].get("seq", 0)) if events else 0
        return self._seq

    # -- writing -------------------------------------------------------------

    def append(self, event: Dict) -> Dict:
        """Append one event with ``seq`` and ``ts``; fsync before returning."""
        record = dict(event)
        record["seq"] = self.last_seq() + 1
        record.setdefault("ts", utc_now())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._seq = record["seq"]
        return record


# ─── replay validation ───────────────────────────────────────────────────────


def _numeric(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def validate(events: Sequence[Dict]) -> List[str]:
    """Replay the ledger and report every rule it breaks.

    An empty list means the ledger is valid: sequence contiguous from 1, exactly
    one baseline before any trial, a known outcome per trial, every ``keep``
    legal under :func:`decide.decide` with the recorded noise floor and passing
    its guard, and stops that close one segment at a time — a resumed run
    appends a ``resume`` after a ``stop``, so at most one stop per segment, a
    stop may only be followed by a resume or by nothing, and only the last
    segment may be left open.
    """
    problems: List[str] = []
    if not events:
        # Nothing recorded yet is not a violation — it is a run that has not
        # started. A *partial* ledger is where the rules below bite.
        return []

    first = events[0]
    if first.get("type") not in ("init", "baseline"):
        problems.append(
            f"seq {first.get('seq')}: first event must be 'init' or 'baseline', "
            f"got {first.get('type')!r}"
        )

    expected_seq = 1
    for event in events:
        seq = event.get("seq")
        if seq != expected_seq:
            problems.append(f"seq {seq}: expected {expected_seq} (sequence must be contiguous from 1)")
        expected_seq = expected_seq + 1 if isinstance(seq, int) else expected_seq + 1

    baselines = [e for e in events if e.get("type") == "baseline"]
    if len(baselines) != 1:
        problems.append(f"expected exactly one baseline event, found {len(baselines)}")
    if len(baselines) == 1:
        baseline_index = events.index(baselines[0])
        for index, event in enumerate(events):
            if event.get("type") == "trial" and index < baseline_index:
                problems.append(
                    f"seq {event.get('seq')}: trial appears before the baseline"
                )
                break
        if _numeric(baselines[0].get("metric")) is None:
            problems.append("baseline event has no numeric 'metric'")
        if not baselines[0].get("commit"):
            problems.append("baseline event has no 'commit'")

    stops = [e for e in events if e.get("type") == "stop"]
    # A stop closes one segment of the run. Continuing a stopped run appends a
    # `resume`, so the ledger is a sequence of segments and the single-final-stop
    # rule becomes: at most one stop per segment, a stop is only ever followed by
    # a resume (or by nothing), and only the last segment may be left open.
    segment = 1
    stops_in_segment = 0
    previous_type = None
    for event in events:
        kind = event.get("type")
        if kind == "stop":
            stops_in_segment += 1
            if stops_in_segment > 1:
                problems.append(
                    f"seq {event.get('seq')}: at most one stop event per segment "
                    f"— segment {segment} has {stops_in_segment} with no 'resume' between them"
                )
        elif kind == "resume":
            if previous_type != "stop":
                problems.append(
                    f"seq {event.get('seq')}: 'resume' must follow a 'stop' "
                    f"(segment {segment})"
                )
            segment += 1
            stops_in_segment = 0
        elif previous_type == "stop":
            problems.append(
                f"seq {event.get('seq')}: stop event must be the last event of its "
                f"segment — only a 'resume' may follow a stop"
            )
        previous_type = kind

    for event in events:
        if event.get("type") not in EVENT_TYPES:
            problems.append(f"seq {event.get('seq')}: unknown event type {event.get('type')!r}")

    # Replay the incumbent through the trials, re-deciding every keep.
    incumbent_metric = _numeric(baselines[0].get("metric")) if baselines else None
    direction = None
    noise_floor = None
    if baselines:
        direction = baselines[0].get("direction")
        noise_floor = _numeric(baselines[0].get("noise_floor"))

    seen_iterations: List[int] = []
    for event in events:
        if event.get("type") != "trial":
            continue
        seq = event.get("seq")
        outcome = event.get("outcome")
        if outcome not in OUTCOMES:
            problems.append(f"seq {seq}: unknown outcome {outcome!r}")
            continue
        iteration = event.get("iteration")
        if not isinstance(iteration, int):
            problems.append(f"seq {seq}: trial has no integer 'iteration'")
        else:
            seen_iterations.append(iteration)

        event_direction = event.get("direction", direction)
        event_floor = _numeric(event.get("noise_floor"))
        if event_floor is None:
            event_floor = noise_floor
        if event_direction not in ("lower", "higher"):
            problems.append(f"seq {seq}: trial has no usable 'direction'")

        metric = _numeric(event.get("metric"))
        if outcome == "keep":
            if event.get("guard") != "pass":
                problems.append(
                    f"seq {seq}: keep recorded with guard={event.get('guard')!r} (must be 'pass')"
                )
            if metric is None:
                problems.append(f"seq {seq}: keep recorded without a numeric 'metric'")
            elif (
                incumbent_metric is None
                or event_floor is None
                or event_direction not in ("lower", "higher")
            ):
                problems.append(f"seq {seq}: keep cannot be re-decided (no incumbent/noise floor)")
            elif decide_mod.decide(metric, incumbent_metric, event_direction, event_floor) != "keep":
                problems.append(
                    f"seq {seq}: keep is not better than the incumbent "
                    f"{incumbent_metric:g} beyond the noise floor {event_floor:g}"
                )
            else:
                incumbent_metric = metric
        elif metric is not None and outcome in ("discard", "guard_failed"):
            # A non-keep never moves the incumbent; nothing to replay.
            pass

    duplicates = {i for i in seen_iterations if seen_iterations.count(i) > 1}
    for iteration in sorted(duplicates):
        problems.append(f"iteration {iteration} appears more than once")

    return problems


def load(path: os.PathLike | str) -> Tuple[List[Dict], List[str]]:
    """Read + validate in one step; never raises on a malformed ledger."""
    ledger = Ledger(path)
    events, problems = ledger.read_tolerant()
    if problems:
        return events, problems
    return events, validate(events)


def require_valid(path: os.PathLike | str) -> List[Dict]:
    """Read + validate, raising :class:`LedgerError` when the ledger is invalid."""
    events, problems = load(path)
    if problems:
        raise LedgerError("; ".join(problems))
    return events
