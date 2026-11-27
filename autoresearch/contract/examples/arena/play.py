#!/usr/bin/env python3
"""Replay a scripted arena game, or settle one live round by hand.

A game is a ``game.py`` module carrying one ``GAME`` dict: where the base
example lives, which file is editable, how to run it, which line is the metric,
how many rounds, which strategies (lists of patches) each seat may play, and the
captain replies for each round. ``rules.py`` decides everything numeric; this
file only does I/O — copy the tree, apply a patch, run it, parse one line.

    python3 play.py replay --game ex1-music-abc-cs/game.py --out /tmp/ex1-cs
    python3 play.py settle --state state.json --a a.json --b b.json --round 3

Deterministic by construction: no clock, no timestamp, no absolute path and no
wall second reaches an output. Seat directories under ``--out`` are working
scratch; ``scoreboard.json``, ``scoreboard.md`` and ``round-N/captain-*`` are
the record.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEAMS = ("A", "B")


def _rival(team):
    return "B" if team == "A" else "A"


def _load(path, name):
    """Import a .py file by path (rules.py and game.py are not packages)."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _write_json(path, payload):
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    Path(path).write_text(text + "\n", encoding="utf-8")


def _econ(rules, name):
    presets = {"PORTABLE": rules.PORTABLE, "LEAGUE_S38": rules.LEAGUE_S38}
    try:
        return presets[name]
    except KeyError:
        raise SystemExit(f"unknown economy {name!r} (PORTABLE|LEAGUE_S38)")


def _guard(text, game):
    """A reading counts only if the metric parses and the gate line is True."""
    metric = None
    for line in text.splitlines():
        if line.startswith(game["metric"] + ":"):
            try:
                metric = float(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    if metric is None:
        return None
    gate = game.get("gate")
    if gate:
        seen = [line.split(":", 1)[1].strip() for line in text.splitlines()
                if line.startswith(gate + ":")]
        if seen != ["True"]:
            return None
    return metric


def _run(game, workdir):
    """Run one seat's command. No shell; a timeout is a crash, not a hang."""
    try:
        done = subprocess.run(
            [str(part) for part in game["run"]],
            cwd=str(workdir), capture_output=True, text=True,
            timeout=float(game["timeout"]),
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return done.stdout


def _measure(game, workdir):
    return _guard(_run(game, workdir), game)


def _prepare(workdir, base, game, text):
    """A fresh seat tree: frozen files copied, the editable written."""
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    for name in game.get("files", ()):
        shutil.copyfile(base / name, workdir / name)
    (workdir / game["editable"]).write_text(text, encoding="utf-8")
    return workdir


def _apply(text, patches):
    """Apply a candidate's patches; None when an anchor does not match once."""
    for mode, find, replace in patches:
        if mode == "literal":
            if text.count(find) != 1:
                return None
            text = text.replace(find, replace, 1)
            continue
        if len(re.findall(find, text, flags=re.M)) != 1:
            return None
        text = re.sub(find, replace, text, count=1, flags=re.M)
    return text


def _bump(events, name):
    events[name] = events.get(name, 0) + 1


def _seat(game, base, workdir, team, strategy, trunk_text, trunk_metric,
          granted, cursors, rival_landed):
    """One seat's whole round: its candidates, its keeps, its events."""
    result = {
        "kind": "measure", "direction": game["direction"],
        "baseline": trunk_metric, "best": None, "keeps": [], "audit_hits": 0,
        "events": {}, "loc_delta": 0, "iterations": granted, "attempts": 0,
        "snapshot": {}, "trunk_snapshot": {}, "note": "", "_text": trunk_text,
    }
    if strategy == "audit":
        result["kind"] = "audit"
        if rival_landed is None:
            result["note"] = "no landed rival work to audit"
            return result
        _prepare(workdir, base, game, rival_landed)
        result["attempts"] = 1
        # A hit is the rival's landed file failing the guard on a second look.
        result["audit_hits"] = 0 if _measure(game, workdir) is not None else 1
        return result

    pool = game["strategies"].get(strategy, ())
    cursor = cursors[(team, strategy)]
    best_text, best = trunk_text, trunk_metric
    lower = game["direction"] == "lower"
    for _ in range(int(granted)):
        if cursor >= len(pool):
            break
        desc, patches = pool[cursor]
        cursor += 1
        result["attempts"] += 1
        candidate = _apply(best_text, patches)
        if candidate is None:
            _bump(result["events"], "anchor_miss")
            continue
        _prepare(workdir, base, game, candidate)
        metric = _measure(game, workdir)
        if metric is None:
            _bump(result["events"], "crash")
            _prepare(workdir, base, game, best_text)
            continue
        if metric < best if lower else metric > best:
            best_text, best = candidate, metric
            result["keeps"].append(desc)
            continue
        _prepare(workdir, base, game, best_text)
    cursors[(team, strategy)] = cursor
    result["note"] = "pool exhausted" if result["attempts"] < granted else ""
    result["best"] = best
    result["_text"] = best_text
    if result["keeps"]:
        result["loc_delta"] = (len(best_text.splitlines())
                               - len(trunk_text.splitlines()))
    if best is not None:
        result["snapshot"] = {game["metric"]: best}
    if trunk_metric is not None:
        result["trunk_snapshot"] = {game["metric"]: trunk_metric}
    return result


def _public(result):
    return {key: value for key, value in result.items()
            if not key.startswith("_")}


def _seal_captain(round_dir, team, choice, rules):
    """The sealed choice, and the digest of the file exactly as written."""
    text, _ = rules.seal(choice)
    (round_dir / f"captain-{team}.json").write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (round_dir / f"captain-{team}.sha256").write_text(digest + "\n",
                                                      encoding="utf-8")
    return digest


def _markdown(record):
    """One table row per round — the record a reader skims first."""
    lines = [
        f"# {record['name']} — scripted replay",
        "",
        f"Economy `{record['economy']}`, {len(record['rounds'])} rounds. "
        f"Trunk {record['start_metric']:.6f} -> "
        f"{record['final_trunk_metric']:.6f}.",
        "",
        "| round | opener | strategies A/B | payoff A/B | banks A/B "
        "| landed A/B | void | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in record["rounds"]:
        landed = row.get("landed") or {}
        if row.get("void"):
            mark, verdict = "—", f"void: {row['void']}"
        else:
            mark = "/".join("yes" if landed.get(t) else "no" for t in TEAMS)
            winner = row["winner"]
            verdict = (f"{winner} landed" if landed.get(winner)
                       else f"{winner} kept nothing")
        lines.append(
            f"| {row['round']} | {row['opener']} "
            f"| {row['strategies']['A']}/{row['strategies']['B']} "
            f"| {row['payoff'][0]:.6f}/{row['payoff'][1]:.6f} "
            f"| {row['banks']['A']:.6f}/{row['banks']['B']:.6f} "
            f"| {mark} | {row.get('void') or '—'} | {verdict} |"
        )
    eq = record["equilibrium"]
    lines += [
        "",
        f"Equilibrium reached: **{str(eq['reached'])}** "
        f"(threshold {eq['threshold']}, unexplored cells: "
        f"A={len(eq['unknown']['A'])}, B={len(eq['unknown']['B'])}).",
        "",
        "A void row pays nobody and is skipped by the equilibrium;",
        "seat directories are scratch and never vendored.",
        "",
    ]
    return "\n".join(lines)


def replay(args):
    rules = _load(HERE / "rules.py", "arena_rules")
    game_path = Path(args.game).resolve()
    game = _load(game_path, "arena_game").GAME
    econ = _econ(rules, game.get("economy", "PORTABLE"))
    base = (game_path.parent / game["base"]).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    trunk_text = _read(base / game["start"])
    state = {"banks": {team: float(econ.start_bank) for team in TEAMS},
             "matrix": [], "last_loser": None}
    names = list(game["strategies"]) + (["audit"] if game.get("audit") else [])
    cursors = {(team, name): 0 for team in TEAMS
               for name in game["strategies"]}
    previous = {team: None for team in TEAMS}
    landed_text = {team: None for team in TEAMS}
    floor, start_metric, trunk_metric = float(econ.default_floor), None, None
    rounds = []

    for number in range(1, int(game["rounds"]) + 1):
        round_dir = out / f"round-{number}"
        round_dir.mkdir(parents=True, exist_ok=True)
        order = rules.seat_order(number)
        _prepare(round_dir / "trunk-measure", base, game, trunk_text)
        baseline = _measure(game, round_dir / "trunk-measure")
        if baseline is None:
            raise SystemExit(f"round {number}: the trunk fails its own guard")
        trunk_metric = baseline
        if start_metric is None:
            start_metric = baseline

        unserved = list(game.get("unserved", {}).get(number, ()))
        void = ", ".join(f"{team} not served" for team in unserved) or None
        replies = game.get("captains", {}).get(number, {})
        choices, strategies, iterations, results, digests = {}, {}, {}, {}, {}
        for team in order:  # the opener plays first; seats are independent
            fallback = rules.fallback_choice(
                previous[team] or names[0],
                landed_text[_rival(team)] is not None, names)
            choice = rules.parse_captain(replies.get(team, ""), fallback,
                                         names, number, econ)
            choices[team] = choice
            strategies[team] = choice["strategy"]
            previous[team] = choice["strategy"]
            digests[team] = _seal_captain(round_dir, team, choice, rules)
            granted, cost = rules.iterations_for(
                state["banks"][team], choice["buy"],
                state["last_loser"] == team, econ)
            iterations[team] = granted
            if team in unserved:
                results[team] = {
                    "kind": "measure", "direction": game["direction"],
                    "baseline": None, "best": None, "keeps": [],
                    "audit_hits": 0, "events": {}, "loc_delta": 0,
                    "iterations": granted, "attempts": 0, "snapshot": {},
                    "trunk_snapshot": {}, "cost": 0,
                    "note": "injected: not served",
                }
                continue
            results[team] = _seat(
                game, base, round_dir / f"seat-{team}", team,
                strategies[team], trunk_text, baseline, granted, cursors,
                landed_text[_rival(team)])
            results[team]["cost"] = cost

        profits = {team: rules.settle(
            results[team], results[_rival(team)], floor, econ,
            jackpot_keys=game.get("jackpot_keys", ())) for team in TEAMS}
        winner = rules.round_winner(profits["A"]["profit"],
                                    profits["B"]["profit"], order[0])
        landed = {team: False for team in TEAMS}
        if not void and results[winner]["keeps"]:
            _prepare(round_dir / "landing", base, game,
                     results[winner]["_text"])
            again = _measure(game, round_dir / "landing")
            if again is not None:
                landed[winner] = True
                trunk_text, trunk_metric = results[winner]["_text"], again
                # What a later audit re-runs: the file that actually landed.
                landed_text[winner] = results[winner]["_text"]
        profits = {team: rules.settle(
            results[team], results[_rival(team)], floor, econ,
            jackpot_keys=game.get("jackpot_keys", ()),
            landed=landed[team]) for team in TEAMS}
        settled = rules.settle_teams(state, results, profits, strategies,
                                     winner=winner, landed=landed, void=void)
        verdict = rules.equilibrium(state["matrix"], strategies, floor, names)

        record = {
            "round": number, "opener": order[0], "order": list(order),
            "floor": floor, "trunk_metric": baseline,
            "captains": {team: {"choice": choices[team],
                                "sha256": digests[team]} for team in TEAMS},
            "strategies": strategies, "iterations": iterations,
            "cost": {team: int(results[team].get("cost") or 0)
                     for team in TEAMS},
            "attempts": {team: results[team]["attempts"] for team in TEAMS},
            "results": {team: _public(results[team]) for team in TEAMS},
            "payoff": [settled["A"]["profit"], settled["B"]["profit"]],
            "banks": dict(state["banks"]),
            "winner": None if void else winner, "landed": landed,
            "void": void, "injected": unserved, "equilibrium": verdict,
        }
        _write_json(round_dir / "scoreboard.json", record)
        rounds.append(record)
        floor = rules.ratchet(floor, econ)
        print(f"round {number}: {strategies['A']}/{strategies['B']} payoff "
              f"{record['payoff'][0]:.6f}/{record['payoff'][1]:.6f} "
              f"{record['void'] or record['winner']}")

    record = {
        "name": game["name"], "economy": game.get("economy", "PORTABLE"),
        "rounds": rounds, "banks": dict(state["banks"]),
        "matrix": state["matrix"], "equilibrium": rounds[-1]["equilibrium"],
        "start_metric": start_metric, "final_trunk_metric": trunk_metric,
    }
    _write_json(out / "scoreboard.json", record)
    (out / "scoreboard.md").write_text(_markdown(record), encoding="utf-8")
    print(f"wrote {out / 'scoreboard.json'} and {out / 'scoreboard.md'}")


def settle(args):
    """The live bridge: settle two engine result files the operator wrote."""
    rules = _load(HERE / "rules.py", "arena_rules")
    econ = _econ(rules, args.economy)
    try:
        state = json.loads(_read(args.state))
    except (OSError, ValueError) as exc:
        print(f"settle: cannot read state {args.state}: {exc}", file=sys.stderr)
        return 2
    if not {"banks", "matrix"} <= set(state):
        print("settle: state needs banks and matrix", file=sys.stderr)
        return 2
    results, strategies = {}, {}
    for team, path in (("A", args.a), ("B", args.b)):
        try:
            results[team] = json.loads(_read(path))
        except (OSError, ValueError) as exc:
            print(f"settle: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        missing = [key for key in ("kind", "direction", "baseline", "best",
                                   "cost", "strategy")
                   if key not in results[team]]
        if missing:
            print(f"settle: {path} needs {', '.join(missing)}",
                  file=sys.stderr)
            return 2
        strategies[team] = results[team]["strategy"]
    floor = float(state.get("floor", econ.default_floor))
    pre = {team: rules.settle(results[team], results[_rival(team)], floor,
                              econ) for team in TEAMS}
    order = rules.seat_order(args.round)
    winner = rules.round_winner(pre["A"]["profit"], pre["B"]["profit"],
                                order[0])
    landed = {team: bool(results[team].get("landed")) for team in TEAMS}
    void = args.void or None
    profits = {team: rules.settle(results[team], results[_rival(team)], floor,
                                  econ, landed=landed[team])
               for team in TEAMS}
    rules.settle_teams(state, results, profits, strategies, winner=winner,
                       landed=landed, void=void)
    state["floor"] = rules.ratchet(floor, econ)
    state["round"] = args.round
    _write_json(args.state, state)
    print(json.dumps({"round": args.round, "winner": winner, "void": void,
                      "profits": {t: profits[t]["profit"] for t in TEAMS},
                      "banks": state["banks"]}, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="play.py",
                                     description="replay or settle a game")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("replay", help="replay a game.py into --out")
    one.add_argument("--game", required=True)
    one.add_argument("--out", required=True)
    two = sub.add_parser("settle", help="settle one round of engine results")
    two.add_argument("--state", required=True)
    two.add_argument("--a", required=True)
    two.add_argument("--b", required=True)
    two.add_argument("--round", type=int, required=True)
    two.add_argument("--economy", default="PORTABLE")
    two.add_argument("--void", default=None)
    args = parser.parse_args(argv)
    if args.command == "replay":
        replay(args)
        return 0
    return settle(args)


if __name__ == "__main__":
    sys.exit(main())
