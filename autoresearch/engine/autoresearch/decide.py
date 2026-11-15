"""The decision rule — the only place a candidate is allowed to win.

"Better" is deliberately strict: a candidate must beat the incumbent by more
than the noise margin, otherwise a metric that jitters run to run would turn the
loop into a random walk and every jitter would be committed as progress.

The margin is ``max(configured noise floor, Z * standard error of the
difference of the two medians)``. A delta *inside* that margin cannot separate
the two runs, so it has its own verdict — ``inconclusive`` — which is neither a
keep nor a discard penalty: the candidate is reverted and nothing is claimed
about it.
"""

from __future__ import annotations

from typing import Optional

from .measure import Measurement, standard_error_of_difference

KEEP = "keep"
DISCARD = "discard"
INCONCLUSIVE = "inconclusive"

#: Two-sided 95% normal quantile: the margin is this many standard errors.
#: Asymptotic only — see :func:`margin` on how thin this gets at small ``n``.
Z = 1.96

#: How a profile's ``noise_floor`` is read by :func:`margin`: absolute unless a
#: caller asks for the legacy fraction reading. The loop passes ``"relative"``
#: so a fraction profile keeps its old meaning (AC-EVL-004).
NOISE_FLOOR_MODE = "absolute"


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
    # must not flip its sign. At exactly 0 there is no relative scale, so the
    # floor falls back to an absolute amount.
    floor_amount = abs(float(incumbent)) * floor if incumbent != 0 else floor
    if direction == "lower":
        return KEEP if candidate < incumbent - floor_amount else DISCARD
    if direction == "higher":
        return KEEP if candidate > incumbent + floor_amount else DISCARD
    raise ValueError(f"unknown direction {direction!r}")


def _floor_amount(noise_floor: float, incumbent: Optional[float], mode: str) -> float:
    """Read a configured noise floor as an absolute amount (or legacy relative).

    A negative floor clamps to ``0.0`` — "no floor" — which is exactly what
    :func:`decide` does with the same value. The two readers must not disagree
    about the sign of a configuration mistake, or a profile could gate one path
    and not the other.
    """
    floor = max(0.0, float(noise_floor))
    if mode == "absolute":
        return floor
    if mode == "relative":
        return floor if not incumbent else abs(float(incumbent)) * floor
    raise ValueError(f"unknown noise floor mode {mode!r}")


def margin(
    candidate: Measurement,
    incumbent: Measurement,
    noise_floor: float,
    *,
    mode: str = NOISE_FLOOR_MODE,
) -> float:
    """The improvement a candidate must beat: ``max(floor, Z * SE)``.

    Arguments are ``(candidate, incumbent)`` — **the same order as
    :func:`decide` and :func:`decide_with_margin`**, so wiring one call site
    into another cannot silently invert a verdict. The function itself is
    symmetric (an SE of a difference does not care which side is which); the
    order is a contract for the reader, not a computation.

    ``SE`` is the independent two-sample standard error of the difference of the
    two medians (:func:`measure.standard_error_of_difference`), which includes
    the :data:`measure.MEDIAN_CONSISTENCY` factor. When either side has fewer
    than two repeats there is no dispersion, so the margin is the floor alone
    (AC-EVL-004), read as an absolute amount unless ``mode='relative'``.

    ``Z = 1.96`` is the *asymptotic* 95% normal quantile and the repeats are
    few: at ``n = 2`` the exact small-sample quantile is ``t(0.975, df=1) =
    12.7``, so this margin is optimistic by roughly an order of magnitude at the
    smallest honest sample. A future PRD may switch to ``t``-based margins.
    """
    floor = _floor_amount(noise_floor, incumbent.value, mode)
    se = standard_error_of_difference(candidate, incumbent)
    return floor if se is None else max(floor, Z * se)


def decide_with_margin(
    candidate: Measurement,
    incumbent: Measurement,
    direction: str,
    noise_floor: float,
    *,
    mode: str = NOISE_FLOOR_MODE,
) -> str:
    """Margin-gated verdict: ``'keep'``, ``'discard'`` or ``'inconclusive'``.

    Arguments are ``(candidate, incumbent)`` — **the same order as
    :func:`decide` and :func:`margin`**; passing them the other way round would
    invert every verdict without raising.

    Unlike :func:`decide`, the threshold is :func:`margin` rather than a bare
    floor: a delta *inside* the margin cannot separate the two runs, so it is
    ``'inconclusive'`` — neither a keep nor a discard penalty. With fewer than
    two repeats on either side the margin collapses to the noise floor (read the
    way ``mode`` says), so this is :func:`decide`'s behaviour except that an
    exact tie is ``'inconclusive'`` rather than a discard.
    """
    if candidate.value is None or incumbent.value is None:
        return DISCARD
    threshold = margin(candidate, incumbent, noise_floor, mode=mode)
    if direction == "lower":
        delta = float(incumbent.value) - float(candidate.value)
    elif direction == "higher":
        delta = float(candidate.value) - float(incumbent.value)
    else:
        raise ValueError(f"unknown direction {direction!r}")
    if delta > threshold:
        return KEEP
    if delta < -threshold:
        return DISCARD
    return INCONCLUSIVE


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
