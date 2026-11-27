"""PRD 31. IDs: AC-ARN-001..019 — the shared arena rules, without a subprocess.

``rules.py`` is not a package module, so it is loaded by path with
``importlib.util.spec_from_file_location``. The rules are pure: a scenario is
plain dicts, a bank and a floor, which is what makes a replay deterministic.
"""

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path

RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "autoresearch"
    / "contract"
    / "examples"
    / "arena"
    / "rules.py"
)


def _load_rules():
    spec = importlib.util.spec_from_file_location("arena_rules", RULES_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # A frozen dataclass resolves its annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rules = _load_rules()


def _team(**overrides):
    team = {
        "direction": "lower",
        "kind": "measure",
        "baseline": 4.0,
        "best": 2.0,
        "audit_hits": 0,
        "events": {},
        "loc_delta": 0,
        "snapshot": {},
        "trunk_snapshot": {},
    }
    team.update(overrides)
    return team


def _row(a, b, payoff, **extra):
    row = {"a": a, "b": b, "payoff": list(payoff), "cost": {"A": 0, "B": 0}}
    row.update(extra)
    return row


# --- AC-ARN-001 ---


def test_economy_presets():
    """AC-ARN-001: PORTABLE is the archived arena; LEAGUE_S38 is one attempt."""
    econ = rules.PORTABLE
    assert econ.start_bank == 4
    assert econ.base_iterations == 4
    assert econ.loss_bonus == 1
    assert econ.buy_max == 2
    assert econ.buy_cost == 2
    assert econ.iteration_cap == 6
    assert econ.audit_transfer == 10
    assert econ.event_penalty == 1
    assert econ.loc_bonus == 2
    assert econ.jackpot_factor == 3
    assert econ.ratchet_step == 0.005
    assert econ.default_floor == 0.01

    league = rules.LEAGUE_S38
    assert league.base_iterations == 2
    assert league.iteration_cap == 1
    assert league.start_bank == econ.start_bank
    assert league.buy_max == econ.buy_max


# --- AC-ARN-002 ---


def test_relative_missing_and_unparseable_read_zero():
    """AC-ARN-002: None or junk reads as no gain; a zero start is a ±1 step."""
    assert rules.relative(None, 2.0) == 0.0
    assert rules.relative(4.0, None) == 0.0
    assert rules.relative("n/a", 2.0) == 0.0
    assert rules.relative(0.0, 0.0) == 0.0
    assert rules.relative(0.0, -1.0) == 1.0
    assert rules.relative(0.0, 1.0) == -1.0
    assert rules.relative(0.0, 1.0, lower_is_better=False) == 1.0
    assert rules.relative(0.0, -1.0, lower_is_better=False) == -1.0


def test_relative_is_delta_over_absolute_start():
    """AC-ARN-002: delta/abs(start), direction-aware, signed by improvement."""
    assert rules.relative(4.0, 2.0) == 0.5
    assert rules.relative(4.0, 5.0) == -0.25
    assert rules.relative(2.0, 4.0, lower_is_better=False) == 1.0
    assert rules.relative(4.0, 2.0, lower_is_better=False) == -0.5
    assert rules.relative(-2.0, -1.0) == -0.5


# --- AC-ARN-003 ---


def test_iterations_base_loss_bonus_and_buy():
    """AC-ARN-003: 4 base, 5 after a loss, +2 bought at 2 points each, cap 6."""
    assert rules.iterations_for(10, 0, False) == (4, 0)
    assert rules.iterations_for(10, 0, True) == (5, 0)
    assert rules.iterations_for(10, 2, False) == (6, 4)
    assert rules.iterations_for(10, 1, True) == (6, 2)
    assert rules.iterations_for(10, 3, False) == (6, 4)


def test_iterations_never_exceed_cap_and_need_a_bank():
    """AC-ARN-003: a negative or empty bank buys nothing; the cap always holds."""
    assert rules.iterations_for(0, 2, False) == (4, 0)
    assert rules.iterations_for(-4, 2, False) == (4, 0)
    assert rules.iterations_for(None, 2, True) == (5, 0)
    assert rules.iterations_for(1, 2, False) == (4, 0)


def test_iterations_league_preset_is_always_one_and_free():
    """AC-ARN-003: LEAGUE_S38 funds one deep attempt; nothing is buyable."""
    for bank in (-4, 0, 1, 10):
        for lost in (False, True):
            assert rules.iterations_for(bank, 2, lost, rules.LEAGUE_S38) == (1, 0)


# --- AC-ARN-004 ---


def test_settle_metric_profit_and_penalty():
    """AC-ARN-004: 100x the relative gain, minus one point per penalty event."""
    paid = rules.settle(_team(), _team(baseline=None, best=None), 0.01)
    assert paid["improvement"] == 0.5
    assert paid["metric_profit"] == 50.0
    assert paid["penalty"] == 0
    assert paid["profit"] == 50.0

    events = {"crash": 1, "agent_error": 2, "anchor_miss": 5}
    paid = rules.settle(_team(events=events), _team(), 0.01)
    assert paid["penalty"] == -3
    assert paid["profit"] == 47.0


def test_settle_audit_pays_the_transfer_only_both_ways():
    """AC-ARN-004: an audit scores +10/own hit, -10/rival hit, no improvement."""
    audit = _team(kind="audit", baseline=None, best=None, audit_hits=2)
    paid = rules.settle(audit, _team(audit_hits=1), 0.01)
    assert paid["improvement"] == 0.0
    assert paid["metric_profit"] == 0
    assert paid["audit_scored"] == 20
    assert paid["audit_received"] == -10
    assert paid["profit"] == 10.0

    paid = rules.settle(_team(), _team(audit_hits=3), 0.01)
    assert paid["audit_scored"] == 0
    assert paid["audit_received"] == -30
    assert paid["profit"] == 20.0


# --- AC-ARN-005 ---


def test_jackpot_needs_keys_and_landed_work():
    """AC-ARN-005: no keys means no pot; anything but a literal True pays none."""
    snapshot = {"m": 2.0}
    trunk = {"m": 4.0}
    assert rules.jackpot(snapshot, trunk, (), 0.01, {"m": "lower"}) is False
    assert rules.jackpot(snapshot, trunk, ("m",), 0.01, {"m": "lower"}) is True
    assert rules.jackpot(snapshot, {}, ("m",), 0.01, {"m": "lower"}) is False
    assert rules.jackpot(snapshot, trunk, ("m", "n"), 0.01, {}) is False

    paid = rules.settle(
        _team(snapshot=snapshot, trunk_snapshot=trunk),
        _team(),
        0.01,
        jackpot_keys=("m",),
        directions={"m": "lower"},
    )
    assert paid["jackpot"] is False
    paid = rules.settle(
        _team(snapshot=snapshot, trunk_snapshot=trunk),
        _team(),
        0.01,
        jackpot_keys=("m",),
        landed=True,
    )
    assert paid["jackpot"] is True
    assert paid["profit"] == 150.0


def test_jackpot_scales_a_win_never_a_loss():
    """AC-ARN-005: a -2 penalty stays -2 even when the pot fires."""
    snapshot = {"m": 2.0}
    trunk = {"m": 4.0}
    loss = _team(baseline=4.0, best=4.0, events={"crash": 2},
                 snapshot=snapshot, trunk_snapshot=trunk)
    paid = rules.settle(
        loss, _team(), 0.01, jackpot_keys=("m",), landed=True
    )
    assert paid["jackpot"] is True
    assert paid["profit"] == -2.0


# --- AC-ARN-006 ---


def test_loc_bonus_requires_work_not_known_unlanded():
    """AC-ARN-006: a smaller diff pays +2 unless landing is known to be False."""
    team = _team(loc_delta=-3)
    assert rules.settle(team, _team(), 0.01)["loc_bonus"] == 2
    assert rules.settle(team, _team(), 0.01, landed=True)["loc_bonus"] == 2
    paid = rules.settle(team, _team(), 0.01, landed=False)
    assert paid["loc_bonus"] == 0
    assert paid["profit"] == 50.0


# --- AC-ARN-007 ---


def test_no_reading_when_baseline_is_none():
    """AC-ARN-007: an unobserved seat has no reading, no metric pay, no pot."""
    team = _team(baseline=None, best=1.0, snapshot={"m": 1.0},
                 trunk_snapshot={"m": 4.0})
    paid = rules.settle(
        team, _team(), 0.01, jackpot_keys=("m",), landed=True
    )
    assert paid["no_reading"] is True
    assert paid["improvement"] == 0.0
    assert paid["metric_profit"] == 0
    assert paid["jackpot"] is False
    assert paid["profit"] == 0.0

    audit = _team(kind="audit", baseline=None, best=None, audit_hits=1)
    assert rules.settle(audit, _team(), 0.01)["no_reading"] is False


# --- AC-ARN-008 ---


def test_seat_order_alternates():
    """AC-ARN-008: odd rounds open A, even rounds open B."""
    assert rules.seat_order(1) == ("A", "B")
    assert rules.seat_order(2) == ("B", "A")
    assert rules.seat_order(3) == ("A", "B")
    assert rules.seat_order(4) == ("B", "A")


# --- AC-ARN-009 ---


def test_seat_deadlines_give_each_seat_its_own_slot():
    """AC-ARN-009: deadlines are started + slot, never first-come-first-served."""
    deadlines = rules.seat_deadlines(1000, ("A", "B"))
    assert deadlines == {"A": 2140, "B": 3280}
    deadlines = rules.seat_deadlines(1000, ("B", "A"))
    assert deadlines == {"B": 2140, "A": 3280}


def test_first_seat_spending_all_leaves_the_second_a_full_slot():
    """AC-ARN-009: one seat's overspend cannot fund the other's grant."""
    deadlines = rules.seat_deadlines(1000, ("A", "B"))
    assert rules.seat_grant(deadlines["A"], 2140) == 0
    assert rules.seat_grant(deadlines["B"], 1000) == rules.SEAT_WALL
    assert rules.seat_grant(deadlines["B"], 0) == rules.SEAT_WALL


def test_seat_grant_under_the_floor_is_not_served():
    """AC-ARN-009: below MIN_SEAT_WALL the seat is not launched at all."""
    deadline = 3280
    assert rules.seat_grant(deadline, 3280 - 100) == 0
    assert rules.seat_grant(deadline, 3280 - rules.MIN_SEAT_WALL) == (
        rules.MIN_SEAT_WALL
    )
    assert rules.seat_grant(deadline, 3281) == 0


# --- AC-ARN-010 ---


def test_round_wall_is_two_slots_plus_the_tail():
    """AC-ARN-010: ROUND_WALL == 2*SEAT_WALL + ROUND_RESERVE == 2400."""
    assert rules.SEAT_WALL == 1140
    assert rules.ROUND_RESERVE == 120
    assert rules.MIN_SEAT_WALL == 240
    assert rules.ROUND_WALL == 2 * rules.SEAT_WALL + rules.ROUND_RESERVE
    assert rules.ROUND_WALL == 2400


# --- AC-ARN-011 ---


def _state(bank=8):
    return {
        "banks": {"A": bank, "B": bank},
        "matrix": [],
        "ranges": {},
        "last_loser": "A",
    }


def test_void_round_pays_nobody_and_banks_nothing():
    """AC-ARN-011: a void row is the settlement's single zero, and names no loser."""
    state = _state()
    results = {"A": {"cost": 4}, "B": {"cost": 2}}
    profits = {"A": {"profit": 50.0}, "B": {"profit": 40.0}}
    settled = rules.settle_teams(
        state, results, profits, {"A": "x", "B": "y"}, void="B not served"
    )
    for team in ("A", "B"):
        assert settled[team]["profit"] == 0.0
        for key, value in rules.VOID_ZEROED.items():
            assert settled[team][key] == value
    assert state["banks"] == {"A": 8, "B": 8}
    assert state["last_loser"] is None
    row = state["matrix"][0]
    assert row["payoff"] == [0.0, 0.0]
    assert row["cost"] == {"A": 0, "B": 0}
    assert row["void"] == "B not served"


# --- AC-ARN-012 ---


def test_void_rows_are_skipped_by_the_matrix_readers():
    """AC-ARN-012: a void row never enters played_rows, cell means or regret."""
    matrix = [
        _row("x", "y", [0.0, 0.0]),
        _row("x", "y", [100.0, 100.0], void="A not served"),
        _row("y", "y", [5.0, 5.0]),
        _row("x", "x", [0.0, 0.0]),
        _row("y", "x", [0.0, 0.0]),
    ]
    assert len(rules.played_rows(matrix)) == 4
    # (y, x) is the same matchup read from the other seat, so A's pair x/y has
    # two zero rows — and the void row's 100.0 is not one of them.
    assert rules.cell_payoffs(matrix, "A", "x", "y") == [0.0, 0.0]
    assert rules.cell_payoffs(matrix, "B", "y", "x") == [0.0, 0.0]

    verdict = rules.equilibrium(matrix, {"A": "x", "B": "y"}, 0.01, ("x", "y"))
    assert verdict["reached"] is False
    assert verdict["regrets"]["A"] == 5.0
    assert verdict["unknown"] == {"A": [], "B": []}


# --- AC-ARN-013 ---


def test_settle_teams_banks_profit_minus_cost_and_names_the_loser():
    """AC-ARN-013: the bank is payoff - cost, and the row records the charge."""
    state = _state(bank=4)
    results = {"A": {"cost": 4}, "B": {"cost": 0}}
    profits = {"A": {"profit": 10.0}, "B": {"profit": 2.0}}
    settled = rules.settle_teams(
        state, results, profits, {"A": "x", "B": "y"}, winner="A"
    )
    assert state["banks"] == {"A": 10.0, "B": 6.0}
    assert state["last_loser"] == "B"
    row = state["matrix"][0]
    assert row["payoff"] == [10.0, 2.0]
    assert row["cost"] == {"A": 4, "B": 0}
    assert "landed" not in row
    assert settled["A"]["profit"] == 10.0


def test_settle_teams_records_landed_only_when_given():
    """AC-ARN-013: the row carries the landing map only when a caller supplied one."""
    state = _state()
    profits = {"A": {"profit": 1.0}, "B": {"profit": 0.0}}
    rules.settle_teams(
        state,
        {"A": {}, "B": {}},
        profits,
        {"A": "x", "B": "y"},
        winner="A",
        landed={"A": True, "B": False},
    )
    assert state["matrix"][0]["landed"] == {"A": True, "B": False}


# --- AC-ARN-014 ---


def test_round_winner_tie_goes_to_the_opener():
    """AC-ARN-014: more profit wins; an exact tie is the opener's round."""
    assert rules.round_winner(6.0, 5.0, "B") == "A"
    assert rules.round_winner(5.0, 6.0, "A") == "B"
    assert rules.round_winner(5.0, 5.0, "A") == "A"
    assert rules.round_winner(5.0, 5.0, "B") == "B"


def test_settle_teams_names_the_non_opener_as_loser_on_a_tie():
    """AC-ARN-014: the winner kwarg is what turns a tie into a loser."""
    state = _state()
    profits = {"A": {"profit": 5.0}, "B": {"profit": 5.0}}
    rules.settle_teams(
        state, {"A": {}, "B": {}}, profits, {"A": "x", "B": "y"},
        winner="B",
    )
    assert state["last_loser"] == "A"

    state = _state()
    rules.settle_teams(
        state, {"A": {}, "B": {}}, profits, {"A": "x", "B": "y"}
    )
    assert state["last_loser"] is None


# --- AC-ARN-015 ---


def _dense_matrix():
    return [
        _row("x", "x", [0.0, 0.0]),
        _row("x", "y", [10.0, 4.0]),
        _row("y", "x", [3.0, 9.0]),
        _row("y", "y", [5.0, 5.0]),
    ]


def test_equilibrium_reached_on_a_dense_explored_matrix():
    """AC-ARN-015: no unexplored move and no regret above the floor is reached."""
    verdict = rules.equilibrium(
        _dense_matrix(), {"A": "x", "B": "y"}, 0.01, ("x", "y")
    )
    assert verdict["reached"] is True
    assert verdict["regrets"] == {"A": 0.0, "B": 0.0}
    assert verdict["unknown"] == {"A": [], "B": []}
    assert verdict["threshold"] == 1.0
    assert verdict["current"] == {"A": "x", "B": "y"}


def test_equilibrium_blocked_by_an_unexplored_strategy():
    """AC-ARN-015: a cell no round played blocks the verdict and is named."""
    matrix = [row for row in _dense_matrix() if row["a"] != "y" or row["b"] != "y"]
    verdict = rules.equilibrium(matrix, {"A": "x", "B": "y"}, 0.01, ("x", "y"))
    assert verdict["reached"] is False
    assert verdict["unknown"]["A"] == ["y"]


def test_equilibrium_blocked_by_regret():
    """AC-ARN-015: a better unexplored-then-played move over the threshold blocks."""
    matrix = _dense_matrix()
    matrix[-1] = _row("y", "y", [20.0, 5.0])
    verdict = rules.equilibrium(matrix, {"A": "x", "B": "y"}, 0.01, ("x", "y"))
    assert verdict["reached"] is False
    assert verdict["regrets"]["A"] == 10.5
    assert verdict["unknown"] == {"A": [], "B": []}


# --- AC-ARN-016 ---


def test_ratchet_raises_the_floor_one_notch():
    """AC-ARN-016: floor + ratchet_step, rounded to six places."""
    assert rules.ratchet(0.01) == 0.015
    assert rules.ratchet(0.015) == 0.02
    assert rules.ratchet(0.0) == 0.005
    assert rules.ratchet(0.01, rules.Economy(ratchet_step=0.05)) == 0.06


# --- AC-ARN-017 ---


def test_seal_is_canonical_and_key_order_independent():
    """AC-ARN-017: sorted compact JSON, so a reordered choice seals the same."""
    text, digest = rules.seal({"b": 1, "a": 2})
    assert text == '{"a":2,"b":1}'
    assert rules.seal({"a": 2, "b": 1}) == (text, digest)
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_seal_escapes_non_ascii():
    """AC-ARN-017: ensure_ascii keeps the sealed bytes ASCII-only."""
    text, digest = rules.seal({"name": "é"})
    assert text == '{"name":"\\u00e9"}'
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- AC-ARN-018 ---


CAPTAINS = ("context", "smoothing", "audit")
FALLBACK = {"strategy": "context", "buy": 0, "reason": "captain fallback"}


def _parse(text, round_no=2):
    return rules.parse_captain(text, FALLBACK, CAPTAINS, round_no)


def test_parse_captain_reads_the_first_object_in_prose():
    """AC-ARN-018: prose around the object is fine; the reason is stripped."""
    choice = _parse('ok: {"strategy": "smoothing", "buy": 1, "reason": "  try it "}',
                    round_no=2)
    assert choice == {"strategy": "smoothing", "buy": 1, "reason": "try it"}


def test_parse_captain_falls_back_on_unusable_replies():
    """AC-ARN-018: no object, unknown strategy, audit in round 1, bad buy/reason."""
    assert _parse("no json here") == FALLBACK
    assert _parse('{"strategy": "better", "buy": 0, "reason": "x"}') == FALLBACK
    audit = '{"strategy": "audit", "buy": 0, "reason": "x"}'
    assert _parse(audit, round_no=1) == FALLBACK
    assert _parse(audit, round_no=2)["strategy"] == "audit"
    assert _parse('{"strategy": "context", "buy": true, "reason": "x"}') == FALLBACK
    assert _parse('{"strategy": "context", "buy": "2", "reason": "x"}') == FALLBACK
    assert _parse('{"strategy": "context", "buy": 2, "reason": ""}') == FALLBACK
    assert _parse('{"strategy": "context", "buy": 2, "reason": 5}') == FALLBACK


def test_parse_captain_clamps_an_out_of_range_int_buy():
    """AC-ARN-018: buy 3 clamps to 2, buy -2 to 0, and both say so."""
    high = _parse('{"strategy": "context", "buy": 3, "reason": "greedy"}')
    assert high["buy"] == 2
    assert high["clamped"] is True
    low = _parse('{"strategy": "context", "buy": -2, "reason": "odd"}')
    assert low["buy"] == 0
    assert low["clamped"] is True
    plain = _parse('{"strategy": "context", "buy": 2, "reason": "max"}')
    assert plain["buy"] == 2
    assert "clamped" not in plain


def test_parse_captain_truncates_the_reason_and_copies_the_fallback():
    """AC-ARN-018: 200 chars max, and a fallback is returned as a copy."""
    choice = _parse('{"strategy": "context", "buy": 0, "reason": "%s"}' % ("r" * 250))
    assert len(choice["reason"]) == 200
    fallback = dict(FALLBACK)
    rules.parse_captain("junk", fallback, CAPTAINS, 2)["reason"] = "changed"
    assert fallback["reason"] == "captain fallback"


def test_fallback_choice_never_returns_an_impossible_audit():
    """AC-ARN-018: an audit with no rival range falls back to a metric strategy."""
    assert rules.fallback_choice("audit", False, CAPTAINS)["strategy"] == "context"
    assert rules.fallback_choice("audit", True)["strategy"] == "audit"
    assert rules.fallback_choice("smoothing", False)["strategy"] == "smoothing"
    assert rules.fallback_choice("audit", False)["buy"] == 0
    assert rules.fallback_choice("audit", False)["reason"] == "captain fallback"


# --- AC-ARN-019 ---


ALLOWED_IMPORTS = {"__future__", "dataclasses", "hashlib", "json", "typing"}
BANNED_NAMES = {"open", "eval", "exec", "compile", "__import__", "input"}
BANNED_MODULES = {"os", "pathlib", "shutil", "socket", "subprocess", "sys", "time"}


def test_rules_imports_only_the_stdlib_allowlist_and_does_no_io():
    """AC-ARN-019: imports are json/hashlib/dataclasses/typing; no open, no process."""
    tree = ast.parse(RULES_PATH.read_text(encoding="utf-8"))
    imported = set()
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            calls.append(node.func)
    assert imported <= ALLOWED_IMPORTS, imported - ALLOWED_IMPORTS
    for func in calls:
        if isinstance(func, ast.Name):
            assert func.id not in BANNED_NAMES, func.id
        elif isinstance(func, ast.Attribute):
            base = func.value
            if isinstance(base, ast.Name):
                assert base.id not in BANNED_MODULES, base.id
            assert func.attr not in {"open", "popen", "system"}, func.attr
