"""The decision rule — the only place a candidate is allowed to win.

"Better" is deliberately strict: a candidate must beat the incumbent by more
than the relative noise floor, otherwise a metric that jitters run to run would
turn the loop into a random walk and every jitter would be committed as progress.
"""

from __future__ import annotations

from typing import Optional

KEEP = "keep"
DISCARD = "discard"


def decide(
    candidate: Optional[float],
    incumbent: Optional[float],
    direction: str,
    noise_floor: float,
) -> str:
    """Return ``'keep'`` only when ``candidate`` is better beyond the noise floor."""
    if candidate is None or incumbent is None:
        return DISCARD
    floor = max(0.0, float(noise_floor))
    # The floor is a fraction of the incumbent's *magnitude*: a negative metric
    # must not flip the margin's sign, or every step toward zero would look
    # like progress. At exactly 0 there is no relative scale, so the floor
    # falls back to an absolute amount.
    margin = abs(float(incumbent)) * floor if incumbent != 0 else floor
    if direction == "lower":
        return KEEP if candidate < incumbent - margin else DISCARD
    if direction == "higher":
        return KEEP if candidate > incumbent + margin else DISCARD
    raise ValueError(f"unknown direction {direction!r}")


def target_met(value: Optional[float], target: Optional[float], direction: str) -> bool:
    """True when ``value`` has reached ``target`` (inclusive)."""
    if value is None or target is None:
        return False
    if direction == "lower":
        return value <= target
    if direction == "higher":
        return value >= target
    raise ValueError(f"unknown direction {direction!r}")


def improvement(baseline: Optional[float], best: Optional[float], direction: str) -> Optional[float]:
    """Percentage improvement of ``best`` over ``baseline`` (positive is better)."""
    if baseline is None or best is None:
        return None
    if baseline == 0:
        return 0.0 if best == 0 else None
    delta = baseline - best if direction == "lower" else best - baseline
    return delta / abs(baseline) * 100.0
