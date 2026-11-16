"""Measurement dispersion and margin-gated decisions. IDs: AC-EVL-001..004.

PRD 20 SC-evl-1: a measurement reports the median *with* its repeat count and
spread, and a single-repeat run says so.
PRD 20 SC-evl-2: a keep must clear ``max(floor, 1.96 * SE)``; a delta inside
that margin is ``inconclusive`` rather than a coin-flip keep.
SC-evl-2 also fixes the floor reading: ``NOISE_FLOOR_MODE = 'absolute'`` by
default, with ``mode='relative'`` preserving the engine's pre-PRD-20 meaning.
"""
import statistics
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

import pytest

from autoresearch import decide, measure
from autoresearch.decide import INCONCLUSIVE, decide_with_margin, margin

# The engine path was just prepended, so this import is deliberately not first.
import test_engine_support as support  # noqa: E402


def _cfg(repeats):
    """The smallest config ``measure()`` reads; no repo or subprocess involved."""
    return SimpleNamespace(
        verify="fake-verify",
        metric_name="value",
        repeats=repeats,
        verify_timeout=10,
        repo=".",
    )


def _runner(values):
    """A stand-in for ``measure.run_command``: one CommandResult per value."""
    series = iter(values)

    def run(command, repo, timeout, *, env=None):
        return measure.CommandResult(
            exit_code=0,
            stdout=f"METRIC value={next(series)}\n",
            stderr="",
            seconds=0.5,
        )

    return run


def _measurement(values):
    """A Measurement as the reduce step would build it, without a subprocess."""
    return measure.Measurement(
        value=statistics.median(values),
        values=list(values),
        seconds=0.5 * len(values),
        ok=True,
    )


def _median_se(spread_first, n_first, spread_second, n_second):
    """The expected SE of the median difference, factor and all."""
    return measure.MEDIAN_CONSISTENCY * (
        spread_first**2 / n_first + spread_second**2 / n_second
    ) ** 0.5


# ─── SC-evl-1: dispersion is reported, never discarded ───────────────────────


def test_multi_repeat_measurement_reports_median_repeats_and_spread(monkeypatch):
    """AC-EVL-001: after a multi-repeat run the measurement carries the median,
    the repeat count and the sample standard deviation of the repeats."""
    monkeypatch.setattr(measure, "run_command", _runner([1.0, 2.0, 6.0]))

    result = measure.measure(_cfg(repeats=3))

    assert result.ok is True
    assert result.value == 2.0
    assert result.repeats == 3
    assert result.spread == pytest.approx(statistics.stdev([1.0, 2.0, 6.0]))
    assert result.honest is True


def test_single_repeat_measurement_is_flagged_unhonest(monkeypatch):
    """AC-EVL-002: one run has no dispersion, so it is flagged ``honest=False``
    and its spread is ``None`` instead of a fabricated zero."""
    monkeypatch.setattr(measure, "run_command", _runner([2.0]))

    result = measure.measure(_cfg(repeats=1))

    assert result.ok is True
    assert result.value == 2.0
    assert result.repeats == 1
    assert result.spread is None
    assert result.honest is False


def test_failed_multi_repeat_measurement_is_not_honest(monkeypatch):
    """AC-EVL-002: ``honest`` is derived from repeats *and* a point estimate.

    A series that collected values and then failed has several repeats but no
    metric; counting it as evidence because ``repeats >= 2`` would be a lie
    about a run that produced nothing.
    """
    series = iter([2.0, 4.0])

    def third_run_fails(command, repo, timeout, *, env=None):
        try:
            stdout = f"METRIC value={next(series)}\n"
        except StopIteration:
            return measure.CommandResult(
                exit_code=1, stdout="", stderr="boom", seconds=0.5
            )
        return measure.CommandResult(
            exit_code=0, stdout=stdout, stderr="", seconds=0.5
        )

    monkeypatch.setattr(measure, "run_command", third_run_fails)

    result = measure.measure(_cfg(repeats=3))

    assert result.ok is False
    assert result.value is None
    assert result.values == [2.0, 4.0]
    assert result.repeats == 2
    assert result.honest is False
    # The same rule holds for a hand-built measurement, not just the reducer.
    assert measure.Measurement(value=None, values=[2.0, 4.0]).honest is False


def test_standard_error_of_difference_propagates_both_sides():
    """AC-EVL-001 (helper): SE(delta) = 1.2533 * sqrt(s1^2/n1 + s2^2/n2) over
    sample standard deviations — the factor is the median's, since the point
    estimates are medians."""
    incumbent = _measurement([10.0, 10.2, 9.8])  # spread 0.2, n = 3
    candidate = _measurement([9.8, 9.6, 9.4])  # spread 0.2, n = 3

    expected = _median_se(0.2, 3, 0.2, 3)
    assert measure.standard_error_of_difference(
        candidate, incumbent
    ) == pytest.approx(expected)


def test_median_consistency_factor_keeps_the_margin_honest():
    """AC-EVL-001 (helper): the median's SE is wider than the mean's, so the
    factor is applied — dropping it would narrow the margin ~20%."""
    first = _measurement([10.0, 10.2, 9.8])
    second = _measurement([9.8, 9.6, 9.4])

    mean_se = (0.2**2 / 3 + 0.2**2 / 3) ** 0.5
    observed = measure.standard_error_of_difference(second, first)

    assert observed == pytest.approx(1.2533 * mean_se)
    assert observed > mean_se


def test_standard_error_of_difference_is_none_below_two_repeats():
    """AC-EVL-001 (helper): a side with fewer than two repeats has no sample
    standard deviation, so there is no error to propagate."""
    honest = _measurement([10.0, 10.2, 9.8])
    single = _measurement([10.0])

    assert measure.standard_error_of_difference(honest, single) is None
    assert measure.standard_error_of_difference(single, honest) is None
    assert measure.standard_error_of_difference(single, single) is None


def test_standard_error_gates_on_repeats_not_on_the_spread_field():
    """AC-EVL-001 (helper): the gate is the repeat count — the single source of
    truth for "was this measured" — so a measurement that reports repeats but no
    recorded dispersion contributes zero variance instead of crashing or
    silently widening the margin."""
    bare = measure.Measurement(value=1.0, repeats=5, spread=None)
    honest = _measurement([10.0, 10.2, 9.8])

    assert bare.honest is True
    assert bare.spread is None
    assert measure.standard_error_of_difference(
        bare, honest
    ) == pytest.approx(_median_se(0.0, 5, 0.2, 3))


# ─── SC-evl-2: the margin and the inconclusive verdict ───────────────────────


def test_delta_inside_z_se_is_inconclusive_even_above_the_raw_floor():
    """AC-EVL-003: with repeats on both sides, a delta inside 1.96 * SE is
    ``inconclusive`` even though it clears the raw 0.01 floor."""
    incumbent = _measurement([100.0, 100.2, 99.8])  # median 100.0, spread 0.2
    candidate = _measurement([99.75, 99.95, 99.55])  # median 99.75, spread 0.2

    expected_se = _median_se(0.2, 3, 0.2, 3)
    observed_margin = margin(candidate, incumbent, 0.01)

    assert observed_margin == pytest.approx(1.96 * expected_se)
    assert observed_margin > 0.01  # the raw floor would have kept this
    assert decide_with_margin(candidate, incumbent, "lower", 0.01) == INCONCLUSIVE


def test_delta_outside_the_margin_keeps_or_discards():
    """AC-EVL-003: a delta beyond ``1.96 * SE`` in the better direction is a
    keep; the same distance in the worse direction is a discard."""
    incumbent = _measurement([100.0, 100.2, 99.8])
    better = _measurement([99.0, 99.2, 98.8])  # 1.0 better, beyond ~0.5
    worse = _measurement([101.0, 101.2, 100.8])

    assert decide_with_margin(better, incumbent, "lower", 0.01) == "keep"
    assert decide_with_margin(worse, incumbent, "lower", 0.01) == "discard"
    assert decide_with_margin(better, incumbent, "higher", 0.01) == "discard"
    assert decide_with_margin(worse, incumbent, "higher", 0.01) == "keep"


def test_single_repeats_fall_back_to_the_absolute_floor(monkeypatch):
    """AC-EVL-004: with no dispersion on either side the margin collapses to
    the configured floor read as an absolute amount on the metric scale."""
    monkeypatch.setattr(measure, "run_command", _runner([100.0]))
    incumbent = measure.measure(_cfg(repeats=1))
    monkeypatch.setattr(measure, "run_command", _runner([99.5]))
    candidate = measure.measure(_cfg(repeats=1))

    # 0.5 better than the incumbent, inside a 1.0 absolute floor.
    assert margin(candidate, incumbent, 1.0) == pytest.approx(1.0)
    assert decide_with_margin(candidate, incumbent, "lower", 1.0) == INCONCLUSIVE

    # The same delta clears a 0.1 absolute floor.
    assert margin(candidate, incumbent, 0.1) == pytest.approx(0.1)
    assert decide_with_margin(candidate, incumbent, "lower", 0.1) == "keep"


def test_margin_is_the_larger_of_floor_and_z_se():
    """AC-EVL-003: ``margin()`` is exported and is exactly
    ``max(absolute floor, 1.96 * median SE)``."""
    tight = _measurement([10.0, 10.2, 9.8])  # z * SE ~ 0.40
    assert margin(tight, tight, 0.5) == pytest.approx(0.5)
    assert margin(tight, tight, 0.01) == pytest.approx(1.96 * _median_se(0.2, 3, 0.2, 3))

    noisy = _measurement([10.0, 14.0, 6.0])  # spread 4.0; z * SE ~ 8.0
    assert margin(noisy, noisy, 0.5) == pytest.approx(1.96 * _median_se(4.0, 3, 4.0, 3))


def test_margin_reads_a_relative_floor_when_the_caller_asks():
    """AC-EVL-004: ``NOISE_FLOOR_MODE`` defaults to absolute; the loop passes
    ``mode='relative'`` so a profile written as a fraction keeps its old
    meaning — the single most dangerous line in the port."""
    assert decide.NOISE_FLOOR_MODE == "absolute"
    incumbent = _measurement([200.0])
    candidate = _measurement([190.0])

    assert margin(candidate, incumbent, 0.01) == pytest.approx(0.01)
    assert margin(candidate, incumbent, 0.01, mode="relative") == pytest.approx(2.0)

    with pytest.raises(ValueError):
        margin(candidate, incumbent, 0.01, mode="sideways")


def test_negative_noise_floor_clamps_to_zero_everywhere():
    """AC-EVL-004: a negative floor is a configuration mistake, and both readers
    must read it the same way — as *no floor* — rather than one taking its
    magnitude and the other ignoring it."""
    incumbent = _measurement([10.0, 10.2, 9.8])
    candidate = _measurement([9.7, 9.9, 9.5])

    assert decide._floor_amount(-0.5, 100.0, "absolute") == 0.0
    assert decide._floor_amount(-0.5, 100.0, "relative") == 0.0

    single_a = _measurement([10.0])
    single_b = _measurement([9.0])
    assert margin(single_b, single_a, -0.5) == pytest.approx(0.0)
    # decide() already clamps: the same negative floor cannot gate one path.
    assert decide.decide(9.0, 10.0, "lower", -0.5) == "keep"


def test_zero_spread_mean_margin_is_the_floor_and_an_exact_tie_is_inconclusive():
    """AC-EVL-003: identical repeats give spread 0.0, so SE is 0, the margin is
    exactly the floor, and a candidate that ties the incumbent is
    ``inconclusive`` — not a keep on a 0 > 0 comparison."""
    incumbent = _measurement([100.0, 100.0, 100.0])
    candidate = _measurement([100.0, 100.0, 100.0])

    assert incumbent.spread == 0.0
    assert measure.standard_error_of_difference(candidate, incumbent) == 0.0
    assert margin(candidate, incumbent, 0.25) == pytest.approx(0.25)
    assert decide_with_margin(candidate, incumbent, "lower", 0.25) == INCONCLUSIVE
    assert decide_with_margin(candidate, incumbent, "higher", 0.25) == INCONCLUSIVE


def test_missing_values_discard_and_bad_direction_raises():
    """AC-EVL-003: no metric still means no keep; a bad direction is a bug."""
    incumbent = _measurement([10.0, 10.2, 9.8])
    assert decide_with_margin(measure.Measurement(None), incumbent, "lower", 0.01) == "discard"
    assert decide_with_margin(incumbent, measure.Measurement(None), "lower", 0.01) == "discard"
    with pytest.raises(ValueError):
        decide_with_margin(incumbent, incumbent, "sideways", 0.01)


# ─── SC-evl-2, engine wiring: the loop decides on the margin ─────────────────


def _single(metric):
    """A one-repeat measurement, exactly what a ``--repeats 1`` run yields."""
    return measure.Measurement(value=metric, values=[metric], ok=True)


#: Deltas that sit *outside* the relative floor read the old way. Inside the
#: floor the two rules are allowed to differ — that is the next test.
LEGACY_EQUIVALENT_CASES = [
    (9.0, 10.0, "lower", 0.01),
    (11.0, 10.0, "lower", 0.01),
    (11.0, 10.0, "higher", 0.01),
    (9.0, 10.0, "higher", 0.01),
    (-5.5, -5.0, "lower", 0.01),
    (-4.5, -5.0, "lower", 0.01),
    (10.0, 0.0, "higher", 0.5),
    (0.0, 10.0, "lower", 0.5),
]


@pytest.mark.parametrize("candidate, incumbent, direction, floor", LEGACY_EQUIVALENT_CASES)
def test_single_repeat_verdict_matches_the_legacy_rule(
    candidate, incumbent, direction, floor
):
    """AC-EVL-004: with one repeat on each side there is no dispersion, the
    margin is the floor read the engine's relative way (``|incumbent| * floor``),
    and every delta outside that floor gets exactly the verdict the pre-PRD-20
    rule gave it. That is what keeps single-repeat runs — and every ledger they
    wrote — behaving as they did.
    """
    new = decide_with_margin(
        _single(candidate), _single(incumbent), direction, floor, mode="relative"
    )
    assert new == decide.decide(candidate, incumbent, direction, floor)


def test_single_repeat_only_diverges_inside_the_floor_where_nothing_is_claimed():
    """AC-EVL-004: the sole behavioural difference at one repeat is the band the
    old rule called ``discard`` on a coin flip. There the margin cannot separate
    the runs, so it reports ``inconclusive`` — a verdict that keeps nothing.
    """
    assert decide.decide(9.95, 10.0, "lower", 0.01) == "discard"
    assert (
        decide_with_margin(_single(9.95), _single(10.0), "lower", 0.01, mode="relative")
        == INCONCLUSIVE
    )
    # A tie (delta exactly 0) is the same story, not a "0 > 0" keep.
    assert decide.decide(10.0, 10.0, "lower", 0.01) == "discard"
    assert (
        decide_with_margin(_single(10.0), _single(10.0), "lower", 0.01, mode="relative")
        == INCONCLUSIVE
    )
    # The exhaustive form of this claim is a tracked script, so the figure a
    # document quotes is one `python3 scripts/legacy_grid.py` re-derives.
    grid = Path(__file__).resolve().parents[2] / "scripts" / "legacy_grid.py"
    result = subprocess.run(
        [sys.executable, str(grid)], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stderr
    assert "keeps the margin added: 0" in result.stdout
    assert "keeps the margin lost : 0" in result.stdout


def test_the_incumbent_measurement_is_rebuilt_from_the_ledgers_values():
    """AC-EVL-003: the loop rebuilds the incumbent from what the *ledger* recorded,
    so a trial judged after a keep — or a resumed run — compares against the
    incumbent's dispersion, not its median alone. A pre-PRD-20 event that recorded
    only a metric rebuilds as one repeat: no spread is invented, so the margin
    falls back to the floor exactly as it did when that ledger was written.
    """
    from autoresearch import loop as loop_mod

    rebuilt = loop_mod._measurement_of({"metric": 10.0, "values": [9.8, 10.0, 10.2]})
    assert rebuilt.value == 10.0
    assert rebuilt.repeats == 3
    assert rebuilt.spread == pytest.approx(0.2)
    assert rebuilt.honest is True

    legacy = loop_mod._measurement_of({"metric": 10.0})
    assert legacy.value == 10.0
    assert legacy.repeats == 1
    assert legacy.spread is None
    assert legacy.honest is False
    assert margin(_single(9.95), legacy, 0.01, mode="relative") == pytest.approx(0.1)
    assert (
        decide_with_margin(_single(8.0), legacy, "lower", 0.01, mode="relative")
        == decide.decide(8.0, 10.0, "lower", 0.01)
    )


def test_the_default_repeat_count_is_three_so_the_gate_is_live(tmp_path):
    """AC-EVL-001: the repeat count is set where the decision is made, and the
    default is 3. A statistical gate defaulting to n=1 is dormant while the docs
    claim it is live — downstream shipped the layer, then found its seats still
    ran ``--repeats 1``, so the margin collapsed to the floor in every real
    round. ``init`` without ``--repeats`` therefore records 3, and a trial at
    that default is ``honest`` with a real (here zero, for a deterministic
    verify) standard error.
    """
    from autoresearch import config as config_mod

    assert config_mod.DEFAULT_REPEATS == 3

    repo = support.make_target(tmp_path, value=10)
    argv = support.init_args(repo)
    index = argv.index("--repeats")
    del argv[index : index + 2]  # drop the explicit flag: the default decides
    assert support.run_cli(argv) == 0
    assert config_mod.load(repo).repeats == 3

    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.run_cli(support.run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    trial = [e for e in support.read_events(repo) if e.get("type") == "trial"][0]
    assert trial["outcome"] == "keep"
    assert trial["repeats"] == 3
    assert trial["honest"] is True
    assert trial["se"] == pytest.approx(0.0)  # deterministic verify: no spread
    assert trial["margin"] == pytest.approx(10.0 * 0.01)  # so the floor decides


def test_a_single_repeat_run_still_keeps_and_discards_as_before(tmp_path):
    """AC-EVL-004: end to end at ``--repeats 1``, a better candidate is still
    kept and a worse one still discarded — the margin gate changed the math and
    left the ordinary verdicts alone.
    """
    repo = support.make_target(tmp_path, value=10)
    assert support.init_run(repo) == 0
    improving = support.write_agent(
        tmp_path, support.DECREMENT.format(step=2), name="improving.py"
    )
    assert support.run_cli(support.run_args(repo, improving, extra=["--max-iterations", "1"])) == 0
    kept = support.head(repo)

    worsening = support.write_agent(tmp_path, support.INCREMENT, name="worsening.py")
    assert support.run_cli(support.run_args(repo, worsening, extra=["--max-iterations", "2"])) == 0

    assert support.outcomes(repo) == ["keep", "discard"]
    assert support.value(repo) == 8
    assert support.head(repo) == kept


def test_a_decided_trial_records_dispersion_margin_and_null_cost(tmp_path, monkeypatch):
    """AC-EVL-003: a decided trial carries the dispersion it was judged on
    (``repeats``, ``spread``, ``honest``), the standard error and the margin
    actually applied, and both cost fields as an explicit ``null`` — no adapter
    reports tokens or API calls today, and a fabricated ``0`` would read as "the
    agent was free".
    """
    repo = support.make_target(tmp_path, value=10)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.init_run(repo) == 0

    scripted = iter(
        [
            measure.Measurement(10.2, [10.0, 10.2, 10.4], 1.5, True),
            measure.Measurement(8.2, [8.0, 8.2, 8.4], 1.5, True),
        ]
    )
    monkeypatch.setattr(measure, "measure", lambda cfg, *, log=None: next(scripted))

    assert support.run_cli(support.run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    trial = [e for e in support.read_events(repo) if e.get("type") == "trial"][0]
    assert trial["outcome"] == "keep"
    assert trial["values"] == [8.0, 8.2, 8.4]
    assert trial["repeats"] == 3
    assert trial["spread"] == pytest.approx(0.2)
    assert trial["honest"] is True

    expected_se = _median_se(0.2, 3, 0.2, 3)
    assert trial["se"] == pytest.approx(expected_se)
    assert trial["margin"] == pytest.approx(max(10.2 * 0.01, 1.96 * expected_se))
    assert trial["margin"] > trial["se"]

    assert "agent_tokens" in trial and trial["agent_tokens"] is None
    assert "agent_api_calls" in trial and trial["agent_api_calls"] is None
    assert trial["agent_tokens"] != 0


def test_an_inconclusive_candidate_is_reverted_and_never_moves_the_incumbent(tmp_path):
    """AC-EVL-003: a candidate the margin cannot separate is recorded as
    ``inconclusive``, reverted exactly like a discard, and counted as a non-keep
    by the plateau rule. Its metric is still recorded — the measurement happened
    — but the incumbent's metric and commit are untouched.
    """
    repo = support.make_target(tmp_path, value=10)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.init_run(repo, extra=["--noise-floor", "0.5"]) == 0
    before = support.head(repo)

    assert support.run_cli(
        support.run_args(repo, script, extra=["--max-iterations", "3", "--plateau", "1"])
    ) == 0

    assert support.outcomes(repo) == ["inconclusive"]
    assert support.stop_reason(repo) == "plateau"
    assert support.head(repo) == before
    assert support.value(repo) == 10

    trial = [e for e in support.read_events(repo) if e.get("type") == "trial"][0]
    assert trial["metric"] == 8.0  # better, but only by 2.0
    assert trial["margin"] == pytest.approx(5.0)  # |10| * 0.5, one repeat each
    assert trial["honest"] is False
    assert trial["se"] is None

    # The same candidate under the default floor is a keep: the margin, not the
    # candidate, is what stopped it.
    kept = support.make_target(tmp_path, name="kept", value=10)
    assert support.init_run(kept) == 0
    keeping = support.write_agent(
        tmp_path, support.DECREMENT.format(step=2), name="keeping.py"
    )
    assert support.run_cli(support.run_args(kept, keeping, extra=["--max-iterations", "1"])) == 0
    assert support.outcomes(kept) == ["keep"]


# ─── the margin a decision records is the margin it used ─────────────────────


def test_the_recorded_margin_is_the_one_the_verdict_used(tmp_path, monkeypatch):
    """AC-EVL-003: the trial event's ``margin`` is the number the verdict was
    judged against — one number, threaded through both.

    The rule derives its own threshold from the floor it is given, so the loop
    computes the margin once and hands *that number* back as the floor. The spy
    proves the thread rather than the arithmetic: the second evaluation starts
    from the first one's answer, and both end at the value the event records. A
    loop that computed the margin twice would call the rule with the configured
    floor instead, leaving two independently derived thresholds — and a ledger
    that explains a keep with a margin the keep never cleared.
    """
    repo = support.make_target(tmp_path)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.init_run(repo, repeats=3) == 0

    calls = []
    real_margin = decide.margin

    def spying_margin(candidate, incumbent, noise_floor, *, mode="absolute"):
        value = real_margin(candidate, incumbent, noise_floor, mode=mode)
        calls.append({"floor": float(noise_floor), "mode": mode, "value": value})
        return value

    monkeypatch.setattr(decide, "margin", spying_margin)
    code = support.run_cli(support.run_args(repo, script, extra=["--max-iterations", "1"]))

    assert code == 0
    trial = [e for e in support.read_events(repo) if e.get("type") == "trial"][-1]
    assert trial["outcome"] == "keep"
    assert len(calls) == 2, calls
    # The rule was handed the loop's threshold, not the raw configured floor...
    assert calls[1]["floor"] == pytest.approx(calls[0]["value"])
    # ...and applying that floor reproduced it, so the recorded margin is the
    # margin the verdict actually used.
    assert calls[1]["value"] == pytest.approx(calls[0]["value"])
    assert trial["margin"] == pytest.approx(calls[1]["value"])
