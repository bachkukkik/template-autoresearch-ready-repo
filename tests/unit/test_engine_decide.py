"""The keep/discard rule. IDs: AC-ENG-010..012."""
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import pytest

from autoresearch.decide import decide, improvement, target_met


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
