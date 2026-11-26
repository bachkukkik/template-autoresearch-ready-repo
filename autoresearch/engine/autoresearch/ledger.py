"""The event ledger: append-only, fsync'd, and replay-validated.

``events.jsonl`` is the run's record of truth. It is append-only because a run
that can rewrite its own history cannot be audited, and it is validated on every
read because a ledger that is merely *written* is not evidence — the point of
replaying the decision rule over it is to prove the recorded keeps were legal
under the very rule that produced them.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import decide as decide_mod

EVENT_TYPES = ("init", "baseline", "trial", "stop", "resume", "attempt")

#: ``attempt`` is an event kind, not a verdict: a verdict would change every
#: reader that switches on one, while a new kind is skipped by readers that do
#: not know it (PRD 30 SC-mcv-4). These are the phases it may name.
ATTEMPT_PHASES = ("agent", "measure", "guard", "interrupted")

OUTCOMES = (
    "keep",
    "discard",
    "inconclusive",
    "guard_failed",
    "crash",
    "no_change",
    "scope_violation",
    "protected_violation",
    "agent_error",
)

#: Outcomes that mean "the candidate never produced a usable measurement".
CRASH_OUTCOMES = ("crash", "agent_error")

#: Outcomes that record an adjudicated keep/discard decision — the only two that
#: owe a provenance block. ``inconclusive`` is recorded but decides nothing, so
#: there is no claim about the candidate for provenance to underwrite.
DECISION_OUTCOMES = ("keep", "discard")

#: Fields every decision's ``provenance`` block must carry. Identifiers and
#: version strings only — a credential *name* may appear, never its value. Extra
#: keys are tolerated by design, so cost/token provenance can be layered on.
PROVENANCE_FIELDS = (
    "model",
    "model_route",
    "engine_version",
    "referee_version",
    "profile_sha256",
    "timestamp",
)

#: The timestamp form ``utc_now`` stamps and the read side insists on: ISO-8601,
#: UTC, second resolution. ``[0-9]``, not ``\d`` — ``\d`` also matches
#: Arabic-Indic digits, which no tool here can parse as an instant.
_ISO_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

#: The longest a recorded identifier may be. ``model`` and ``model_route`` are
#: operator-supplied and written verbatim, so the block is where a pasted
#: payload — not a model name — can still be refused.
MAX_PROVENANCE_FIELD = 512

#: A SHA-256 digest is 64 lowercase hex characters — nothing longer, shorter or
#: otherwise spelled counts.
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

#: ``scheme://userinfo@host`` — userinfo is where a credential hides in a route
#: string, and the colon is optional (RFC 3986): ``https://TOKEN@h`` carries one
#: too. Matched on the way in, because the ledger is append-only.
_CREDENTIALS_IN_ROUTE_RE = re.compile(r"://[^/@\s]+@")


def embeds_credentials(value) -> bool:
    """True when a provenance string carries URL userinfo (``scheme://userinfo@``).

    ``model`` and ``model_route`` are both operator-supplied strings recorded
    *verbatim*, and both are reached by the same mistake: a gateway URL pasted
    where a name belongs. One predicate, so the two fields cannot drift apart —
    a check on the route alone let a ``--model`` URL through.

    The colon is *optional*: RFC 3986 defines userinfo as
    ``*( unreserved / pct-encoded / sub-delims / ":" )``, so ``https://TOKEN@h``
    and ``https://user:@h`` carry a credential just as ``https://user:pw@h``
    does. Requiring ``user:password@`` accepted both and wrote the token into the
    ledger. Any userinfo after a scheme is refused.

    No scheme, no match: an scp-style remote (``git@github.com:x/y``) has no
    ``://`` and therefore no URL userinfo by this rule — and it is not a route a
    model or route field is for, so it is left to the operator's own judgement.
    """
    return isinstance(value, str) and bool(_CREDENTIALS_IN_ROUTE_RE.search(value))


class LedgerError(Exception):
    """The ledger cannot be read or is invalid. The CLI maps it to exit 3."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def provenance_block(
    model: str,
    model_route: str,
    engine_version: str,
    referee_version: str,
    profile_path: os.PathLike | str,
    timestamp: Optional[str] = None,
) -> Dict[str, str]:
    """Build the ``provenance`` sub-dict stamped onto a keep/discard event.

    ``profile_sha256`` hashes the profile file's *content*, so a run cannot
    claim a profile it did not use. ``timestamp`` is injectable for tests; by
    default it is the current UTC instant in ISO-8601 form. Credentials never
    enter this block — identifiers and version strings only, and *either* the
    ``model`` or the ``model_route`` embedding userinfo
    (``scheme://user:password@host``, ``scheme://TOKEN@host``) is refused rather
    than scrubbed: an operator pasting a gateway URL into ``--model`` puts it in
    the same append-only file. An empty ``model`` and any field longer than
    :data:`MAX_PROVENANCE_FIELD` are refused for the same reason — a field that
    names nothing, or carries a pasted payload, proves nothing about the run
    while making the block look complete. Extra keys are tolerated by design, so
    later cost/token provenance can be layered on without a schema break.
    """
    for field, value in (("model", model), ("model_route", model_route)):
        if not isinstance(value, str):
            # A type error is not a length error: answering a `model_route=123`
            # with "longer than 512 characters" names the wrong defect and sends
            # the operator to the wrong field.
            raise LedgerError(
                f"{field} is not a string (got {type(value).__name__}) — "
                f"record an identifier"
            )
        if embeds_credentials(value):
            # The ledger is append-only: a secret written here can never be
            # edited out, only rotated away. Refuse it at the seam that builds
            # the block, and name the field rather than echoing the value.
            raise LedgerError(
                f"{field} embeds credentials — record the {field} without secrets"
            )
    if not model.strip():
        raise LedgerError(
            "model is empty — record a model identifier (or '<adapter>:default'); "
            "an empty field looks complete and names nothing"
        )
    for field, value in (("model", model), ("model_route", model_route)):
        if len(value) > MAX_PROVENANCE_FIELD:
            # Both fields are identifiers, and the block is the last place a
            # pasted payload can be refused instead of appended forever.
            raise LedgerError(
                f"{field} is longer than {MAX_PROVENANCE_FIELD} characters — "
                f"record an identifier, not a payload"
            )
    path = Path(profile_path)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise LedgerError(f"cannot hash profile {path}: {exc}") from exc
    return {
        "model": model,
        "model_route": model_route,
        "engine_version": engine_version,
        "referee_version": referee_version,
        "profile_sha256": digest,
        "timestamp": timestamp if timestamp is not None else utc_now(),
    }


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
        # mid-write): drop that one line with a warning, but every earlier line
        # must still parse — a corrupt line followed by events is a real error.
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


def _margin_problem(
    event: Dict, seq, metric: float, incumbent: float, direction: str
) -> Optional[str]:
    """Why a keep fails its *recorded* margin, or ``None``.

    A ledger written before PRD 20 has no ``margin`` and is replayed by the
    legacy floor rule alone. A ledger that records one makes the stronger claim
    — the delta it kept also cleared the measured margin — so replay holds it to
    that. ``margin >= floor`` by construction, so this can only reject a keep
    the newer rule could not have granted, never one it did.
    """
    if "margin" not in event:
        return None
    raw = event.get("margin")
    if raw is None:
        # An explicit null claims nothing, exactly like an absent field: there
        # is no margin to hold this keep to.
        return None
    recorded = _numeric(raw)
    if recorded is None:
        return f"seq {seq}: keep records a non-numeric 'margin' {raw!r}"
    if not math.isfinite(recorded) or recorded < 0:
        # NaN compares false against everything (so it would approve the keep),
        # a negative value approves any move, an infinity is unclearable — each
        # is a broken claim about why the keep was granted, not a legacy event.
        return (
            f"seq {seq}: keep records an unusable 'margin' {raw!r} "
            "(must be finite and >= 0)"
        )
    delta = incumbent - metric if direction == "lower" else metric - incumbent
    if delta <= recorded:
        return (
            f"seq {seq}: keep's improvement {delta:g} does not exceed its "
            f"recorded margin {recorded:g}"
        )
    return None


def _provenance_problems(events: Sequence[Dict]) -> List[str]:
    """Report every decision event whose provenance block is absent/incomplete.

    Presence is not enough: the two fields with a canonical spelling — the UTC
    timestamp and the content digest — are shape-checked here, because a garbage
    string in either slot makes the block *look* complete while proving nothing.
    """
    problems: List[str] = []
    for event in events:
        if event.get("type") != "trial" or event.get("outcome") not in DECISION_OUTCOMES:
            continue
        seq = event.get("seq")
        block = event.get("provenance")
        if not isinstance(block, dict):
            problems.append(
                f"seq {seq}: {event.get('outcome')} decision has no provenance block"
            )
            continue
        for field in PROVENANCE_FIELDS:
            if not block.get(field):
                problems.append(f"seq {seq}: provenance block is missing {field!r}")
        timestamp = block.get("timestamp")
        if timestamp and not (
            isinstance(timestamp, str) and _ISO_UTC_RE.fullmatch(timestamp)
        ):
            # fullmatch, not match: ``^…$`` matches *before* a trailing newline,
            # so a paste with a stray line ending would read as an instant.
            problems.append(f"seq {seq}: provenance timestamp is not ISO-8601 UTC")
        digest = block.get("profile_sha256")
        if digest and not (isinstance(digest, str) and _SHA256_RE.fullmatch(digest)):
            problems.append(
                f"seq {seq}: provenance profile_sha256 is not a 64-hex digest"
            )
    return problems


def validate(events: Sequence[Dict], require_provenance: bool = False) -> List[str]:
    """Replay the ledger and report every rule it breaks.

    An empty list means the ledger is valid: sequence contiguous from 1, exactly
    one baseline before any trial, a known outcome per trial, every ``keep``
    legal under :func:`decide.decide` with the recorded noise floor and passing
    its guard — and, when the event records a ``margin`` (PRD 20 SC-evl-2), also
    improving by more than that margin — and stops that close one segment at a
    time: a resumed run appends a ``resume`` after a ``stop``, so at most one
    stop per segment, a stop may only be followed by a resume or by nothing, and
    only the last segment may be left open.

    ``require_provenance`` additionally demands the six-field provenance block
    on every keep/discard decision. It defaults to ``False`` so ledgers written
    before provenance existed keep replaying; a caller that cares about
    provenance opts in rather than having the check silently skipped.
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
    # A stop closes one segment; continuing a stopped run appends a `resume`, so
    # the rule becomes: at most one stop per segment, a stop followed only by a
    # resume (or nothing), and only the last segment may be left open.
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
                # The legacy rule is necessary but no longer sufficient: a keep
                # that recorded the margin it was granted must also clear it.
                margin_problem = _margin_problem(
                    event, seq, metric, incumbent_metric, event_direction
                )
                if margin_problem:
                    problems.append(margin_problem)
                else:
                    incumbent_metric = metric
        elif metric is not None and outcome in (
            "discard",
            "inconclusive",
            "guard_failed",
        ):
            # A non-keep never moves the incumbent; nothing to replay.
            # ``inconclusive`` is listed because that is its claim: the margin
            # could not separate the runs, so the candidate was reverted.
            pass

    duplicates = {i for i in seen_iterations if seen_iterations.count(i) > 1}
    for iteration in sorted(duplicates):
        problems.append(f"iteration {iteration} appears more than once")

    if require_provenance:
        problems.extend(_provenance_problems(events))

    return problems


def load(
    path: os.PathLike | str, require_provenance: bool = False
) -> Tuple[List[Dict], List[str]]:
    """Read + validate in one step; never raises on a malformed ledger."""
    ledger = Ledger(path)
    events, problems = ledger.read_tolerant()
    if problems:
        return events, problems
    return events, validate(events, require_provenance=require_provenance)


def require_valid(
    path: os.PathLike | str, require_provenance: bool = False
) -> List[Dict]:
    """Read + validate, raising :class:`LedgerError` when the ledger is invalid."""
    events, problems = load(path, require_provenance=require_provenance)
    if problems:
        raise LedgerError("; ".join(problems))
    return events
