"""Reading token usage out of a harness transcript.

A harness either reports usage in its transcript or it does not, and those are
two different facts: ``None`` is "not exposed", while ``0`` would claim the
agent ran for free. Nothing here estimates. A transcript with no ``usage``
object yields ``None`` and the record says so.

The accepted shapes are the ones harnesses actually print: one JSON object
per line, with the usage object at the top, under ``message``, or under
``part``::

    {"usage": {"total_tokens": 1234}}
    {"usage": {"input_tokens": 900, "output_tokens": 334}}
    {"message": {"usage": {"input_tokens": 900, "output_tokens": 334}}}
    {"part": {"usage": {"total_tokens": 1234}}}

This is the engine's *only* reader of usage: the loop asks it once per trial and
records the answer beside the verdict, where nothing downstream can change the
verdict back (PRD 30 SC-mcv-1, SC-mcv-3).
"""

from __future__ import annotations

import json
from typing import Optional

#: Where a ``usage`` object sits inside one decoded line, in the order tried.
USAGE_PATHS = (("usage",), ("message", "usage"), ("part", "usage"))

TOTAL = "total_tokens"
PROMPT = "input_tokens"
COMPLETION = "output_tokens"


def _count(value) -> Optional[int]:
    """One token count, or ``None``.

    A bool is an int in Python and a negative count is not a count, so both are
    refused rather than summed. An integral float (``1234.0``, which JSON
    producers do emit) is accepted; anything else is not a number of tokens.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        value = int(value) if value.is_integer() else None
    if not isinstance(value, int):
        return None
    return value if value >= 0 else None


def usage_object(record):
    """The ``usage`` object inside one decoded line, or ``None``."""
    if not isinstance(record, dict):
        return None
    for path in USAGE_PATHS:
        node = record
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict):
            return node
    return None


def usage_total(record) -> Optional[int]:
    """The tokens one line reports: ``total_tokens``, else input + output.

    One of ``input_tokens``/``output_tokens`` missing is not a total — half a
    sum would read as a measurement of the whole — so that yields ``None``.
    """
    usage = usage_object(record)
    if usage is None:
        return None
    total = _count(usage.get(TOTAL))
    if total is not None:
        return total
    prompt = _count(usage.get(PROMPT))
    completion = _count(usage.get(COMPLETION))
    if prompt is None or completion is None:
        return None
    return prompt + completion


def tokens_from_transcript(text) -> Optional[int]:
    """The tokens a transcript reports, or ``None`` when it reports none.

    Lines that are not JSON objects — the agent's prose, a log prefix — are
    skipped rather than fatal, because a transcript is a mixture by nature.
    Each line carrying usage is one turn, so they add up. A harness that
    repeated a cumulative total on several lines would be counted more than
    once, which is why the number is only ever published beside the
    denominator that makes it a rate, never as a billing figure.
    """
    total = None
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            record = json.loads(stripped)
        except ValueError:
            continue
        found = usage_total(record)
        if found is not None:
            total = found if total is None else total + found
    return total
