"""The claim an agent pre-registers: one labelled line, read from its channel.

A trial that says what it expects *before* it looks can be graded on the
prediction as well as on the outcome. The agent writes that claim into the same
stream it writes everything else, so this is a reader rather than a form: it
decodes each line the harness emits and takes the assistant's own text. A claim
echoed by a tool result is not a claim, and a ``PREDICT:`` typed with a minus
sign is still a number. ``CLAIM_KEYS`` names the four labels; ``hypothesis`` is
returned as ``text``, and a claim with no ``PREDICT`` is recorded, never scored.
"""

from __future__ import annotations

import json
import math
import re
from typing import Dict, Optional, Tuple

CLAIM_KEYS = ("change", "hypothesis", "predict", "falsified_if")

_LABELS = {"CHANGE": "change", "HYPOTHESIS": "hypothesis",
           "PREDICT": "predict", "FALSIFIED IF": "falsified_if"}

#: One bounded alternation, left to right — no nested quantifier, so no line can
#: make it backtrack. ``FALSIFIED IF`` is spelled out so the two-word label is
#: never read as two labels.
_LABEL_RE = re.compile(
    r"\b(CHANGE|HYPOTHESIS|FALSIFIED\s+IF|PREDICT)\s*:", re.IGNORECASE
)

#: A ``PREDICT:`` value's head: optional sign, padding, one decimal form.
_NUMBER_RE = re.compile(r"^[+-]?\s*(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")

_DIGIT_RE = re.compile(r"[0-9]")

#: Glyphs a model types that ``float()`` refuses: three minus shapes, one space.
_GLYPHS = {"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u00a0": " "}
_TRANSLATION = str.maketrans(_GLYPHS)

#: How deep decoded assistant text is followed: no real transcript nests a text
#: part inside another, and the bound stops a hand-built one from recursing.
MAX_DEPTH = 2


def _value(raw: str) -> str:
    """One field's text: separators trimmed, whitespace collapsed."""
    return " ".join(raw.replace("|", " ").split())


def _number(raw: Optional[str]) -> Optional[float]:
    """The finite number a ``PREDICT:`` value carries; ``None``, never a raise.

    A leading ``+``, padding and a trailing unit word are tolerated; a rest
    that still carries a digit (``1-2``) is two numbers, so it is unparseable.
    """
    body = (raw or "").strip()
    match = _NUMBER_RE.match(body)
    if match is None or _DIGIT_RE.search(body[match.end():]):
        return None
    try:
        number = float("".join(match.group(0).split()))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _fields(line: str) -> Dict[str, str]:
    """Every labelled value on one line, keyed by its canonical name."""
    matches = list(_LABEL_RE.finditer(line))
    ends = [match.start() for match in matches[1:]] + [len(line)]
    found: Dict[str, str] = {}
    for match, end in zip(matches, ends):
        label = " ".join(match.group(1).upper().split())
        found[_LABELS[label]] = _value(line[match.end():end])
    return found


def _claim_of(fields: Dict[str, str]) -> Optional[dict]:
    """The claim one line's fields make, or ``None`` without a hypothesis."""
    text = fields.get("hypothesis") or ""
    if not text:
        return None
    return {"text": text, "predict": _number(fields.get("predict")),
            "falsified_if": fields.get("falsified_if") or None,
            "change": fields.get("change") or None}


def _assistant_text(event: dict) -> Optional[str]:
    """The assistant text one decoded event carries — never a tool payload.

    Three shapes, in order: an opencode ``part`` event, a bare ``part``, and a
    final ``assistant`` message (its ``text`` elements only). No other key is
    read, so a ``tool_result``, ``tool_call`` or ``stdout`` field smuggles
    nothing.
    """
    part = event.get("part")
    if isinstance(part, dict) and isinstance(part.get("text"), str):
        if event.get("type") == "text" or part.get("type") == "text":
            return part["text"]
    if event.get("type") == "assistant":
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        parts = [
            item["text"] for item in (content if isinstance(content, list) else ())
            if isinstance(item, dict) and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        ]
        return "\n".join(parts) or None
    return None


def _channel(line: str) -> Tuple[bool, Optional[str]]:
    """``(is_event, text)`` for one line: a JSON object is an event, not prose.

    An event with no assistant text yields no claim and is never rescanned as
    prose — that rescan is exactly how a tool result became a hypothesis.
    """
    try:
        event = json.loads(line) if line.startswith("{") else None
    except ValueError:
        event = None
    if not isinstance(event, dict):
        return False, None
    return True, _assistant_text(event)


def _claims(text: str, depth: int = 0) -> Optional[dict]:
    """The last claim in a text, following decoded events a bounded depth."""
    claim = None
    for line in (text or "").translate(_TRANSLATION).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_event, body = _channel(stripped)
        if is_event:
            found = _claims(body, depth + 1) if body and depth < MAX_DEPTH else None
        else:
            found = _claim_of(_fields(stripped))
        claim = found if found is not None else claim
    return claim


def parse_claim(text: str) -> Optional[dict]:
    """The last claim ``text`` carries, or ``None`` when none is pre-registered.

    A claim lives on one line naming ``HYPOTHESIS``; ``PREDICT`` is optional,
    because a claim with no number is still a claim. The last one wins.
    """
    return _claims(text)


def claim_from_transcript(transcript: str) -> Optional[dict]:
    """The last claim in a harness transcript — assistant text only.

    Each line is read as what it is: a JSON object contributes its assistant
    text alone, any other line is prose. That rule makes an opencode JSONL
    stream readable and a tool result unreadable.
    """
    return _claims(transcript)
