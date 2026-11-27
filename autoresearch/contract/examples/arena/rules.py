"""Reference game rules — a CS-style arena distilled from a real season.

This is a REFERENCE GAME: a worked example, not a core layer of the template.
It distils two sources into one readable kit: the archived portable arena
(``vanilla-open-design-autoresearch/autoresearch/_archive/arena/arena.py``) and
the live league's season-38 preset (``autoresearch/league/arena.py``). A round
is two seats, one frozen evaluator and a bank; "CS-style" names the economy —
a loss bonus, bought attempts, a pot for landed work — not the video game.
Nothing here captures or analyses gameplay.

Pure by construction: stdlib only, no file, process, clock or environment
access, so a replay is deterministic and a round settles from JSON alone. The
``R<nn>`` notes name the league rule each non-obvious shape comes from.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

#: Events that cost a seat a point each. Anything else (``anchor_miss``) is
#: recorded on the round but never penalised.
PENALTY_EVENTS = ("crash", "agent_error", "scope_violation", "protected_violation")

#: Seat clock, copied from the league: two equal slots and the tail that follows.
SEAT_WALL = 1140
ROUND_RESERVE = 120
ROUND_WALL = 2 * SEAT_WALL + ROUND_RESERVE
MIN_SEAT_WALL = 240


@dataclass(frozen=True)
class Economy:
    """The numbers a season is played with; a preset changes only some."""

    start_bank: int = 4
    base_iterations: int = 4
    loss_bonus: int = 1
    buy_max: int = 2
    buy_cost: int = 2
    iteration_cap: int = 6
    audit_transfer: int = 10
    event_penalty: int = 1
    loc_bonus: int = 2
    jackpot_factor: int = 3
    ratchet_step: float = 0.005
    default_floor: float = 0.01


#: The archived portable arena's numbers (PRD 19): 4 base attempts, 5 after a
#: loss, up to 2 bought at 2 points each, never more than 6 in a round.
PORTABLE = Economy()

#: The live league at season 38 (R40): its wall funds ONE deep attempt per
#: seat, so the cap collapsed from 6 to 1 and nothing can be bought. Base 2
#: keeps the loss bonus from ever exceeding the cap.
LEAGUE_S38 = Economy(base_iterations=2, iteration_cap=1)


def relative(before: Any, after: Any, lower_is_better: bool = True) -> float:
    """Relative improvement of ``after`` over ``before`` (positive is better)."""
    if before is None or after is None:
        return 0.0
    try:
        start, end = float(before), float(after)
    except (TypeError, ValueError):
        return 0.0
    if start == 0.0:
        if end == start:
            return 0.0
        return 1.0 if (end < 0.0) == lower_is_better else -1.0
    delta = (start - end) if lower_is_better else (end - start)
    return delta / abs(start)


def iterations_for(
    bank: float, buy: int, lost_last_round: bool, econ: Economy = PORTABLE
) -> tuple[int, int]:
    """Iterations this seat may play and what the bought ones cost.

    R36: the clamp is applied to the *base* first, so a loss bonus can never
    lift a seat past the cap, and buying can only fill what the cap leaves.
    """
    bank = float(bank or 0.0)
    base = min(
        econ.base_iterations + (econ.loss_bonus if lost_last_round else 0),
        econ.iteration_cap,
    )
    wanted = max(0, min(int(buy or 0), econ.buy_max))
    room = max(0, econ.iteration_cap - base)
    affordable = min(wanted, room, int(bank // econ.buy_cost) if bank > 0 else 0)
    return base + affordable, affordable * econ.buy_cost


def jackpot(
    snapshot: Mapping[str, Any] | None,
    trunk_snapshot: Mapping[str, Any] | None,
    keys: Iterable[str],
    floor: float,
    directions: Mapping[str, str] | None = None,
) -> bool:
    """Every named key present and moved past ``floor`` — no keys, no pot."""
    keys = tuple(keys or ())
    if not keys:
        return False
    snapshot = snapshot or {}
    trunk_snapshot = trunk_snapshot or {}
    if not all(key in snapshot and key in trunk_snapshot for key in keys):
        return False
    directions = directions or {}
    return all(
        relative(
            trunk_snapshot[key],
            snapshot[key],
            directions.get(key, "lower") == "lower",
        )
        > float(floor)
        for key in keys
    )


def settle(
    team: Mapping[str, Any] | None,
    rival: Mapping[str, Any] | None,
    floor: float,
    econ: Economy = PORTABLE,
    *,
    jackpot_keys: Iterable[str] = (),
    directions: Mapping[str, str] | None = None,
    landed: bool | None = None,
) -> dict[str, Any]:
    """What one round is worth to one team, broken into its components."""
    team = team or {}
    rival = rival or {}
    is_audit = str(team.get("kind") or "measure") == "audit"
    # R21: an unobserved seat yields no reading, never a zero reading.
    no_reading = not is_audit and team.get("baseline") is None
    improvement = 0.0
    if not (is_audit or no_reading):
        improvement = relative(
            team.get("baseline"),
            team.get("best"),
            str(team.get("direction") or "lower") == "lower",
        )
    metric_profit = round(100.0 * improvement, 6)
    # An audit's pay is the transfer; its hits are not also a 100x metric gain.
    scored = econ.audit_transfer * int(team.get("audit_hits") or 0)
    received = -econ.audit_transfer * int(rival.get("audit_hits") or 0)
    events = team.get("events") or {}
    penalty = -econ.event_penalty * sum(
        int(events.get(name) or 0) for name in PENALTY_EVENTS
    )
    subtotal = metric_profit + scored + received + penalty
    # R27: the pot pays only for a literal landed True, and it scales a win
    # only — season 18 tripled a -2 penalty into -6.
    fire = False
    if landed is True and not (no_reading or is_audit):
        fire = jackpot(
            team.get("snapshot"),
            team.get("trunk_snapshot"),
            jackpot_keys,
            floor,
            directions,
        )
    if fire and subtotal > 0:
        subtotal *= econ.jackpot_factor
    # R30: a bonus on a worktree reading alone would pay for work not landed.
    loc_bonus = 0
    if int(team.get("loc_delta") or 0) < 0 and landed is not False:
        loc_bonus = econ.loc_bonus
    out: dict[str, Any] = {
        "improvement": improvement,
        "metric_profit": metric_profit,
        "audit_scored": scored,
        "audit_received": received,
        "penalty": penalty,
        "jackpot": fire,
        "loc_bonus": loc_bonus,
        "no_reading": no_reading,
        "profit": round(subtotal + loc_bonus, 6),
    }
    if landed is not None:
        out["landed"] = landed is True
    return out


def seat_order(round_no: int) -> tuple[str, str]:
    """R28: A opens an odd round, B an even one — alternation halves the edge."""
    return ("A", "B") if int(round_no) % 2 else ("B", "A")


def seat_deadlines(
    started: float, order: Sequence[str], seat_wall: int = SEAT_WALL
) -> dict[str, float]:
    """Each seat's own deadline: its slot, not what the other seat left."""
    return {
        team: started + (index + 1) * seat_wall
        for index, team in enumerate(order)
    }


def seat_grant(
    deadline: float,
    now: float,
    seat_wall: int = SEAT_WALL,
    min_seat_wall: int = MIN_SEAT_WALL,
) -> int:
    """Seconds the seat may run, or 0 when it is not served at all.

    R27: below ``min_seat_wall`` the engine cannot pay for its own start-up,
    so launching would only produce a seat killed on a wall it never had.
    """
    remaining = int(max(0, min(float(deadline) - float(now), seat_wall)))
    return 0 if remaining < min_seat_wall else remaining


def round_winner(profit_a: float, profit_b: float, opener: str) -> str:
    """Higher profit wins; R39 gives an exact tie to the round's opener."""
    if float(profit_a) == float(profit_b):
        return opener
    return "A" if float(profit_a) > float(profit_b) else "B"


#: R28: every component a scoreboard prints, zeroed beside a void payoff. The
#: settlement is the one writer of this map, so no caller can half-zero a row.
VOID_ZEROED: dict[str, Any] = {
    "profit": 0.0,
    "metric_profit": 0.0,
    "jackpot": False,
    "loc_bonus": 0,
    "audit_scored": 0.0,
    "audit_received": 0.0,
    "penalty": 0.0,
}


def _last_loser(
    profits: Mapping[str, Mapping[str, Any]], winner: str | None
) -> str | None:
    """The seat that lost the round, or None when the round named no winner."""
    if winner in ("A", "B"):
        return "B" if winner == "A" else "A"
    left = float(profits["A"]["profit"])
    right = float(profits["B"]["profit"])
    if left == right:
        return None
    return "A" if left < right else "B"


def settle_teams(
    state: dict[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    profits: Mapping[str, Mapping[str, Any]],
    strategies: Mapping[str, str],
    *,
    winner: str | None = None,
    landed: Mapping[str, bool] | None = None,
    void: str | None = None,
) -> dict[str, Any]:
    """Bank the round, append its payoff row, name the loser; return the profits.

    ``void`` names a round that paid nobody because a seat was never served:
    the settlement is the single writer of that zero.
    """
    if void:
        settled = {
            team: {**profits[team], **VOID_ZEROED} for team in ("A", "B")
        }
        state["matrix"].append(
            {
                "a": strategies["A"],
                "b": strategies["B"],
                "payoff": [0.0, 0.0],
                "cost": {"A": 0, "B": 0},
                "void": str(void),
            }
        )
        state["last_loser"] = None
        return settled
    cost = {team: int(results[team].get("cost") or 0) for team in ("A", "B")}
    # R33: the bank moves by payoff - cost; the charge is its own cell.
    for team in ("A", "B"):
        state["banks"][team] = round(
            float(state["banks"][team]) + profits[team]["profit"] - cost[team], 6
        )
    row: dict[str, Any] = {
        "a": strategies["A"],
        "b": strategies["B"],
        "payoff": [profits["A"]["profit"], profits["B"]["profit"]],
        "cost": cost,
    }
    if landed is not None:
        row["landed"] = {team: bool(landed[team]) for team in ("A", "B")}
    state["matrix"].append(row)
    state["last_loser"] = _last_loser(profits, winner)
    return {team: profits[team] for team in ("A", "B")}


def played_rows(matrix: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The rows a round actually paid — a void row is a record, not a move."""
    return [row for row in matrix if not row.get("void")]


def cell_payoffs(
    matrix: Sequence[Mapping[str, Any]], team: str, mine: str, theirs: str
) -> list[float]:
    """One team's payoffs for ``mine`` vs ``theirs``, readable from either seat."""
    index = 0 if team == "A" else 1
    other = 1 - index
    payoffs: list[float] = []
    for row in played_rows(matrix):
        if row["a"] == mine and row["b"] == theirs:
            payoffs.append(float(row["payoff"][index]))
        elif row["a"] == theirs and row["b"] == mine:
            payoffs.append(float(row["payoff"][other]))
    return payoffs


def _cell(
    matrix: Sequence[Mapping[str, Any]], team: str, mine: str, theirs: str
) -> float | None:
    """The mean payoff of a pair, or None when no played round explored it."""
    payoffs = cell_payoffs(matrix, team, mine, theirs)
    return sum(payoffs) / len(payoffs) if payoffs else None


def equilibrium(
    matrix: Sequence[Mapping[str, Any]],
    current: Mapping[str, str],
    floor: float,
    strategies: Iterable[str],
) -> dict[str, Any]:
    """The honest verdict: reached only if no known move pays and none is unknown."""
    threshold = 100.0 * float(floor)
    regrets: dict[str, float | None] = {}
    unknown: dict[str, list[str]] = {}
    ok = True
    for team, rival in (("A", "B"), ("B", "A")):
        mine, theirs = current[team], current[rival]
        here = _cell(matrix, team, mine, theirs)
        alternatives: list[float] = []
        unseen: list[str] = []
        for strategy in strategies:
            if strategy == mine:
                continue
            payoff = _cell(matrix, team, strategy, theirs)
            if payoff is None:
                unseen.append(strategy)
            else:
                alternatives.append(payoff)
        unknown[team] = unseen
        if here is None:
            regrets[team] = None
            ok = False
            continue
        regret = round(max([p - here for p in alternatives] + [0.0]), 6)
        regrets[team] = regret
        if unseen or regret > threshold:
            ok = False
    return {
        "reached": ok,
        "regrets": regrets,
        "unknown": unknown,
        "threshold": round(threshold, 6),
        "current": dict(current),
    }


def ratchet(floor: float, econ: Economy = PORTABLE) -> float:
    """Raise the noise floor one notch for the next round."""
    return round(float(floor) + econ.ratchet_step, 6)


def seal(choice: Mapping[str, Any]) -> tuple[str, str]:
    """Canonical text of a captain's choice and its sha256, for committing first."""
    text = json.dumps(
        dict(choice), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    body = str(text or "")
    for index, char in enumerate(body):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(body[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object in captain reply")


def fallback_choice(
    previous_strategy: str,
    audit_possible: bool,
    strategies: Iterable[str] | None = None,
) -> dict[str, Any]:
    """The team's last strategy — an audit with no target is unusable.

    ``strategies`` is optional so the two-argument form still reads; without it
    the reserved word ``measure`` stands in for the game's first metric leg.
    """
    strategy = previous_strategy
    if strategy == "audit" and not audit_possible:
        pool = [name for name in (strategies or ()) if name != "audit"]
        strategy = pool[0] if pool else "measure"
    return {"strategy": strategy, "buy": 0, "reason": "captain fallback"}


def parse_captain(
    text: str,
    fallback: Mapping[str, Any],
    strategies: Iterable[str],
    round_no: int,
    econ: Economy = PORTABLE,
) -> dict[str, Any]:
    """A validated captain choice, or the fallback when the reply is unusable."""
    try:
        payload = _first_json_object(text)
    except ValueError:
        return dict(fallback)
    allowed = {
        name for name in strategies if name != "audit" or int(round_no) >= 2
    }
    strategy = payload.get("strategy")
    buy = payload.get("buy")
    reason = payload.get("reason")
    if strategy not in allowed:
        return dict(fallback)
    # ``True`` is an int in Python; a boolean buy is a malformed reply.
    if isinstance(buy, bool) or not isinstance(buy, int):
        return dict(fallback)
    if not isinstance(reason, str) or not reason.strip():
        return dict(fallback)
    choice: dict[str, Any] = {
        "strategy": strategy,
        "buy": buy,
        "reason": reason.strip()[:200],
    }
    if buy < 0 or buy > econ.buy_max:
        # R32: the two-sided clamp keeps the intent, and says it was clamped.
        choice["buy"] = max(0, min(buy, econ.buy_max))
        choice["clamped"] = True
    return choice
