"""The keep/discard rule. IDs: AC-ENG-010..012."""
import sys
from pathlib import Path

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

import statistics

import pytest

from autoresearch.decide import (
    T_QUANTILES_975,
    Z,
    decide,
    decide_with_margin,
    improvement,
    margin,
    t_quantile,
    target_met,
)
from autoresearch.measure import Measurement, standard_error_of_difference


def test_lower_direction_requires_beating_the_noise_floor():
    """AC-ENG-010: with a 1% floor, 0.5% better is jitter and 1.1% better is progress."""
    assert decide(98.9, 100.0, "lower", 0.01) == "keep"
    # exactly at the floor is not *beyond* it
    assert decide(99.0, 100.0, "lower", 0.01) == "discard"
    assert decide(99.5, 100.0, "lower", 0.01) == "discard"
    assert decide(100.0, 100.0, "lower", 0.0) == "discard"
    assert decide(101.0, 100.0, "lower", 0.0) == "discard"


def test_higher_direction_mirrors_lower():
    """AC-ENG-011: for a higher-is-better metric the comparison flips."""
    assert decide(101.5, 100.0, "higher", 0.01) == "keep"
    assert decide(101.0, 100.0, "higher", 0.01) == "discard"
    assert decide(99.0, 100.0, "higher", 0.0) == "discard"


def test_negative_incumbent_uses_the_magnitude_of_the_noise_floor():
    """AC-ENG-011b: the floor is a fraction of |incumbent|, so a negative metric
    neither flips the comparison nor lets a worse result be kept."""
    # lower is better: -4.97 is worse than -5.0, and inside the 0.05 margin
    assert decide(-4.97, -5.0, "lower", 0.01) == "discard"
    assert decide(-4.99, -5.0, "lower", 0.0) == "discard"
    # exactly at the margin is not *beyond* it
    assert decide(-5.05, -5.0, "lower", 0.01) == "discard"
    assert decide(-5.06, -5.0, "lower", 0.01) == "keep"

    # higher is better: -4.94 is better than -5.0 beyond the same margin
    assert decide(-4.97, -5.0, "higher", 0.01) == "discard"
    assert decide(-4.94, -5.0, "higher", 0.01) == "keep"
    assert decide(-5.5, -5.0, "higher", 0.01) == "discard"


def test_zero_incumbent_falls_back_to_an_absolute_floor():
    """AC-ENG-012: a relative floor is meaningless at 0, so it becomes absolute."""
    assert decide(0.005, 0.0, "lower", 0.01) == "discard"
    assert decide(-0.02, 0.0, "lower", 0.01) == "keep"
    assert decide(0.005, 0.0, "higher", 0.01) == "discard"
    assert decide(0.02, 0.0, "higher", 0.01) == "keep"


def test_missing_values_and_unknown_direction():
    """AC-ENG-012b: no metric means no keep; a bad direction is a programming error."""
    assert decide(None, 1.0, "lower", 0.0) == "discard"
    assert decide(1.0, None, "lower", 0.0) == "discard"
    with pytest.raises(ValueError):
        decide(1.0, 2.0, "sideways", 0.0)


def test_target_is_inclusive_in_the_chosen_direction():
    """AC-ENG-012c: reaching the target exactly counts."""
    assert target_met(3.0, 3.0, "lower") is True
    assert target_met(2.0, 3.0, "lower") is True
    assert target_met(4.0, 3.0, "lower") is False
    assert target_met(3.0, 3.0, "higher") is True
    assert target_met(None, 3.0, "lower") is False
    assert target_met(3.0, None, "lower") is False


def test_improvement_percentage():
    """AC-ENG-012d: change is signed, so a worse result reads negative."""
    assert improvement(100.0, 90.0, "lower") == pytest.approx(10.0)
    assert improvement(100.0, 90.0, "higher") == pytest.approx(-10.0)
    assert improvement(0.0, 0.0, "lower") == 0.0
    assert improvement(0.0, 1.0, "lower") is None


# ─── the margin quantile, opt-in (PRD 29 AC-HYP-010..013) ───────────────────

#: The spreads these measurements carry: 10.0, 10.2, 10.4 has a sample standard
#: deviation of 0.2, so every assertion below can name the SE it expects.
SERIES = (10.0, 10.2, 10.4, 10.6, 10.8, 11.0)


def _m(values):
    """A measurement over a repeat series, as ``measure()`` would build it."""
    return Measurement(value=statistics.median(values), values=list(values), ok=True)


def test_the_t_quantile_uses_the_table_at_the_measured_repeat_count():
    """AC-HYP-010: ``quantile_name='t'`` multiplies the SE by the two-sided 95%
    Student-t value for ``df = n - 1``, where ``n`` is the honest repeat count
    the SE was computed from: 12.706 at two repeats, 4.303 at three, 2.571 at
    six. The ``z`` margin stays the narrower one it always was."""
    for count, table in ((2, 12.706), (3, 4.303), (6, 2.571)):
        incumbent = _m(SERIES[:count])
        candidate = _m([value - 2 for value in SERIES[:count]])
        se = standard_error_of_difference(candidate, incumbent)
        assert se is not None
        assert margin(candidate, incumbent, 0.01, quantile_name="t") == pytest.approx(
            table * se
        )
        assert margin(candidate, incumbent, 0.01) == pytest.approx(1.96 * se)
        assert margin(candidate, incumbent, 0.01, quantile_name="t") > margin(
            candidate, incumbent, 0.01
        )


def test_a_one_repeat_arm_has_no_sample_for_a_t_multiple():
    """AC-HYP-010: below two repeats there is no dispersion, so the SE is
    ``None`` and the margin is the floor under *either* quantile — the
    multiplier never meets a standard error it could inflate."""
    single = _m([10.0])
    assert standard_error_of_difference(single, single) is None
    assert margin(single, single, 0.01) == 0.01
    assert margin(single, single, 0.01, quantile_name="t") == 0.01


def test_the_default_quantile_reproduces_todays_margin_float_for_float():
    """AC-HYP-011: ``z`` is the default and computes the same ``max(floor,
    Z * SE)`` it always did — asserted with ``==``, not a tolerance, because
    a rounding change would move every verdict a replay re-decides."""
    incumbent = _m(SERIES[:3])
    candidate = _m([value - 2 for value in SERIES[:3]])
    se = standard_error_of_difference(candidate, incumbent)
    assert margin(candidate, incumbent, 0.01) == max(0.01, 1.96 * se)
    assert margin(candidate, incumbent, 0.01, quantile_name="z") == margin(
        candidate, incumbent, 0.01
    )
    # A floor above the quantile term still wins, under either name.
    assert margin(candidate, incumbent, 100.0, quantile_name="t") == 100.0


def test_decide_with_margin_passes_the_quantile_through():
    """AC-HYP-011: the same choice reaches the verdict. A 0.5 improvement clears
    the ``z`` margin (0.40) and not the ``t`` one (0.88), so one candidate is a
    keep under the default and ``inconclusive`` under ``t``."""
    incumbent = _m(SERIES[:3])
    close = _m([9.5, 9.7, 9.9])
    assert margin(close, incumbent, 0.0) < 0.5 < margin(
        close, incumbent, 0.0, quantile_name="t"
    )
    assert decide_with_margin(close, incumbent, "lower", 0.0) == "keep"
    assert (
        decide_with_margin(close, incumbent, "lower", 0.0, quantile_name="t")
        == "inconclusive"
    )


def test_the_published_t_quantiles_are_the_ones_in_the_table():
    """AC-HYP-012: the table is the published two-sided 95% one — 12.706 at
    df 1, 4.303 at 2, 2.571 at 5, 2.228 at 10, 2.042 at 30 — complete for df
    1..30 and strictly decreasing, which is what makes it a table and not a
    guess."""
    assert t_quantile(1) == 12.706
    assert t_quantile(2) == 4.303
    assert t_quantile(5) == 2.571
    assert t_quantile(10) == 2.228
    assert t_quantile(30) == 2.042
    assert t_quantile(4) == 2.776
    assert sorted(T_QUANTILES_975) == list(range(1, 31))
    assert all(
        T_QUANTILES_975[df] > T_QUANTILES_975[df + 1] for df in range(1, 30)
    )
    assert all(value > Z for value in T_QUANTILES_975.values())


def test_a_degrees_of_freedom_the_table_cannot_answer_falls_back_to_z():
    """AC-HYP-013: ``df <= 0`` and ``df > 30`` both answer ``Z`` instead of
    raising — the gate never becomes an exception — and an unknown quantile name
    is a programming error rather than a silent ``z``."""
    for df in (0, -1, -100):
        assert t_quantile(df) == Z
    for df in (31, 32, 1000):
        assert t_quantile(df) == Z

    single = _m([10.0])
    with pytest.raises(ValueError):
        margin(single, single, 0.01, quantile_name="f")
    with pytest.raises(ValueError):
        decide_with_margin(single, single, "lower", 0.01, quantile_name="f")
