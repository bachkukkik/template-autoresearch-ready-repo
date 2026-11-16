#!/usr/bin/env python3
"""Brute-force legacy-equivalence sweeps for the engine's keep rule (PRD 20).

The claim (SC-evl-2): the margin-gated rule is **never more permissive** than the
bare noise-floor rule it replaced. This script enumerates a finite grid of
verdicts and counts the disagreements, so the claim is a number a reader can
re-derive instead of a sentence to believe.

Both rules are the shipped ones — ``decide()`` and ``decide_with_margin()`` from
``autoresearch/engine/autoresearch`` are imported, never re-implemented, so a
regression in the engine moves these counts.

Domain (fixed, so the numbers are comparable run to run):

* values  — 16 metric values: three negative (a sign flip must not turn a floor
  into a subsidy), zero (no relative scale — the floor falls back to absolute),
  sub-unit, and two large incumbents.
* floors  — the 7 configured noise floors below, read ``mode="relative"``, which
  is what ``loop.py`` passes, so a fractional profile keeps its pre-port meaning.
* directions — ``lower`` and ``higher``; a pair is counted under each.
* single repeat — one value per side and no dispersion, so ``margin()`` collapses
  to the floor: this is the configuration where the two rules MUST agree exactly.
* honest pair — two repeats per side at spreads ``{0, 1, 3}``, where the two
  rules are allowed to differ: an observed SE can only widen the margin.

Sweeps (``VALUES`` squared, never sampled):

1. ``16 × 16 × 2 × 7  = 3584`` one-repeat points. Invariant: ``added == 0`` and
   ``lost == 0`` — the only divergence is the ``inconclusive`` band.
2. ``16 × 16 × 3 × 3 × 2 × 3 = 13824`` honest pairs. Invariant: ``added == 0``
   (the margin never keeps what the floor refused); ``lost > 0`` here is the
   safety property, not a defect.

Exit 0 when every invariant holds, 1 with the offending counts otherwise.
Stdlib only; no network, no target, no git. Run from anywhere:

    python3 scripts/legacy_grid.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = REPO_ROOT / "autoresearch" / "engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from autoresearch.decide import (  # noqa: E402  (path set above)
    INCONCLUSIVE,
    KEEP,
    decide,
    decide_with_margin,
)
from autoresearch.measure import Measurement  # noqa: E402

VALUES = (
    -100.0, -10.0, -5.0, -2.0, -1.0, 0.0, 1.0, 2.0,
    3.0, 5.0, 10.0, 20.0, 50.0, 100.0, 250.0, 1000.0,
)
FLOORS = (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5)
HONEST_FLOORS = (0.0, 0.05, 0.2)
SPREADS = (0.0, 1.0, 3.0)
DIRECTIONS = ("lower", "higher")
MODE = "relative"
ROOT2 = math.sqrt(2.0)


def single(value: float) -> Measurement:
    """One repeat of ``value`` — no dispersion, so not ``honest``."""
    return Measurement(value=value, values=[value])


def paired(median: float, spread: float) -> Measurement:
    """Two repeats of ``median`` whose sample SD is exactly ``spread``."""
    half = spread / ROOT2
    return Measurement(value=median, values=[median - half, median + half])


def keeps(legacy: str, gated: str) -> tuple[bool, bool]:
    """``(legacy keep, margin keep)`` for one point."""
    return legacy == KEEP, gated == KEEP


def grid() -> dict:
    """Sweep 1 — one repeat per side: the rules must agree exactly."""
    points = legacy_keeps = margin_keeps = added = lost = inside = ties = 0
    for incumbent in VALUES:
        for candidate in VALUES:
            for direction in DIRECTIONS:
                for floor in FLOORS:
                    points += 1
                    legacy = decide(candidate, incumbent, direction, floor)
                    gated = decide_with_margin(
                        single(candidate), single(incumbent), direction, floor, mode=MODE
                    )
                    kept_legacy, kept_margin = keeps(legacy, gated)
                    legacy_keeps += kept_legacy
                    margin_keeps += kept_margin
                    added += kept_margin and not kept_legacy
                    lost += kept_legacy and not kept_margin
                    inside += gated == INCONCLUSIVE
                    ties += candidate == incumbent
    return {
        "points": points, "legacy_keeps": legacy_keeps,
        "margin_keeps": margin_keeps, "added": added, "lost": lost,
        "inside": inside, "ties": ties, "inside_delta": inside - ties,
    }


def honest_pairs() -> dict:
    """Sweep 2 — two repeats per side: the margin may only widen."""
    points = legacy_keeps = margin_keeps = added = lost = 0
    for incumbent in VALUES:
        for candidate in VALUES:
            for cand_spread in SPREADS:
                for inc_spread in SPREADS:
                    for direction in DIRECTIONS:
                        for floor in HONEST_FLOORS:
                            points += 1
                            legacy = decide(candidate, incumbent, direction, floor)
                            gated = decide_with_margin(
                                paired(candidate, cand_spread),
                                paired(incumbent, inc_spread),
                                direction, floor, mode=MODE,
                            )
                            kept_legacy, kept_margin = keeps(legacy, gated)
                            legacy_keeps += kept_legacy
                            margin_keeps += kept_margin
                            added += kept_margin and not kept_legacy
                            lost += kept_legacy and not kept_margin
    return {
        "points": points, "legacy_keeps": legacy_keeps,
        "margin_keeps": margin_keeps, "added": added, "lost": lost,
    }


def report(run: dict) -> bool:
    """Print both sweeps and the invariants; return True when they hold."""
    first, second = run["grid"], run["pair"]
    pairs = len(VALUES) * len(VALUES)
    print(
        f"domain                 : {len(VALUES)} values x {len(VALUES)} values x "
        f"{len(DIRECTIONS)} directions, floor mode={MODE}"
    )
    for title, sweep, legend in (
        ("one-repeat grid", first,
         f"{pairs} pairs x {len(DIRECTIONS)} directions x {len(FLOORS)} floors"),
        ("honest pair sweep", second,
         f"{pairs} pairs x {len(SPREADS)} x {len(SPREADS)} spreads x "
         f"{len(DIRECTIONS)} directions x {len(HONEST_FLOORS)} floors"),
    ):
        print(f"{title:<22} : {sweep['points']} points ({legend})")
        print(f"  legacy keeps         : {sweep['legacy_keeps']}")
        print(f"  margin-gated keeps   : {sweep['margin_keeps']}")
        print(f"  keeps the margin added: {sweep['added']}")
        print(f"  keeps the margin lost : {sweep['lost']}")
    print(
        f"inside the floor       : {first['inside']} "
        f"({first['inside'] // len(DIRECTIONS)} per direction: {first['ties']} exact ties + "
        f"{first['inside_delta']} non-zero delta) — all inconclusive"
    )
    ok = first["added"] == 0 and first["lost"] == 0 and second["added"] == 0
    print(
        f"invariants             : grid added=0 {_verdict(first['added'] == 0)}, "
        f"grid lost=0 {_verdict(first['lost'] == 0)}, "
        f"honest added=0 {_verdict(second['added'] == 0)}"
    )
    return ok


def _verdict(holds: bool) -> str:
    """``PASS`` / ``FAIL`` for one invariant."""
    return "PASS" if holds else "FAIL"


def main() -> int:
    run = {"grid": grid(), "pair": honest_pairs()}
    return 0 if report(run) else 1


if __name__ == "__main__":
    raise SystemExit(main())
