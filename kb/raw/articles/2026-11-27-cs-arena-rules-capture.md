---
source_url: https://github.com/vanilla-republic/vanilla-open-design-autoresearch
ingested: 2026-11-27
sha256: 3b02a47fd564e6124ea507584f67c8d735bfea145f085830c2e1a58276a0ebca
source_type: code-capture
kind: article
title: "CS-style arena — economy, settlement and the five-round VOD (code capture)"
---

# CS-style arena — a code capture

## Provenance

**What.** The rules half of the downstream league's two-seat game, read from the
code at commit `e85cc56` (2026-11-26) rather than from prose. Read in full or in
the ranges cited below:

- `autoresearch/_archive/arena/arena.py` — the portable runner, 1,387 lines:
  `30-52` (strategies and economy constants), `132-145` (`relative`), `148-157`
  (`iterations_for`), `160-165` (`_jackpot`), `168-206` (`settle`), `209-219`
  (`_cell`), `222-261` (`equilibrium`), `264-272` (`ratchet`, `seal`), `275-322`
  (`_first_json_object`, `audit_possible`, `fallback_choice`, `parse_captain`).
- `autoresearch/league/arena.py` — the live league, 9,080 lines: `73-87`
  (`STRATEGIES`), `108-125` (base, loss bonus, R40 cap, comeback),
  `127-151` (transfer, penalties, bonus, floor), `340-399` (slots, reserves,
  timeouts), `424-427` (round cap, season wall), `945-961` (`iterations_for`,
  R36 clamp), `1037-1192` (`settle`), `1218-1227` (`round_winner`), `2490-2513`
  (`parse_captain`, R32 clamp), `5894-5919` (`seat_order`, `seat_wall`),
  `5922-5964` (`unserved_seat`), `6325-6334` (`VOID_ZEROED`), `6337-6457`
  (`settle_teams`), `6460-6483` (`merge_teams`, R39 tie).
- `docs/prd/19-arena-codification.md:107-249` — *The Game* and *Hard Limits*.
- `autoresearch/_archive/arena/runs-vod/` — the five real rounds
  (`scoreboard.md`, `state.json`, `round-N/scoreboard.json`).

**What it is not.** Not a port, and not the whole game. The live module's
weight review, noise band, `paid_legs`, golden buzz, bounty and census veto are
named here only where they change what a settlement pays; none is captured in
enough detail to re-implement. The 1,387-line archived runner's git, prompt and
dashboard machinery is not captured either.

**Labels.** `[M]` read directly in the code at the line cited; `[S]` stated by a
committed season record or PRD of the same repo (quoted, with its number);
`[I]` inference.

**Why this repo cares.** The template runs one seat. The moment it runs two — a
fan-out, an A/B arm, a competitor — fairness stops being a sentiment and becomes
arithmetic that has to be decided before the round starts. This capture holds
the numbers and the three rules that make the arithmetic honest.

## The name: an economy, not a video game

PRD 19's heading is literal: "Counter-Strike's economy, ported" `[M]`
(`19-arena-codification.md:150`). What travels is the **money model of a
round-based match** — a starting bank, income for losing, a purchase that buys
work, and a cap — not a shooter. Nothing in either module reads a game server, a
demo or a frame; the measured object is a git worktree and a metric `[M]`.

The shape is one round at a time: two seats, a referee, a trunk, a floor that
ratchets, and a verdict per round. A season is a sequence of those rounds.

## Two economies, one rule set

Both files carry the same names; only the values differ. The archived runner is
the **portable** preset, the live league is the tuned one.

| Constant | Archived, portable | Live league, season 38 |
|---|---|---|
| `START_BANK` | 4 | 4 |
| `BASE_ITERATIONS` | 4 | **2** |
| `LOSS_BONUS` | 1 | 1 |
| `BUY_MAX` | 2 | 2 |
| `BUY_COST` | 2 | 2 |
| `ITERATION_CAP` | 6 | **1** |
| `AUDIT_TRANSFER` | 10 | 10 |
| `EVENT_PENALTY` | 1 | 1 |
| `LOC_BONUS` | 2 | 2 |
| `JACKPOT_FACTOR` | 3 | 3 |
| `RATCHET_STEP` | 0.005 | 0.005 |
| `DEFAULT_FLOOR` | 0.01 | 0.01 |
| `SEAT_WALL` | — | 1140 |
| `ROUND_RESERVE` | — | 120 |
| `ROUND_WALL` | 1200 | 2×1140+120 = 2400 |
| `MIN_SEAT_WALL` | — | 240 |
| `MAX_WALL` | 840 | `ROUND_WALL − 120` = 2280 |

`[M]` (`_archive/arena/arena.py:33-52`; `league/arena.py:108-151,340-366`).

**Why the live cap collapsed to one.** Not tuning for difficulty — a measurement:

> Season 24 (R40): ONE deep attempt per seat. Season 23 priced a cap of 3
> against a 330 s call, but rounds 73-75 died at that ceiling with the agent
> unfinished, so the iteration the cap promised was never the one that paid …
> With the R36 clamp this cap bounds the base as well as the bonuses —
> `min(BASE_ITERATIONS + bonuses, ITERATION_CAP)` is 1 — so a seat plays one
> iteration and a buy has no room left to fill. `[M]` (`league/arena.py:112-120`)

So in season 38 the whole economy is vestigial by arithmetic: base 2 clamped to
1, no room under the cap, `buy` always costs 0. The constants are kept because
the rules that read them are shared with the portable game `[I]`.

**What the live settlement adds on top** (all `[M]`, `league/arena.py:1037-1192`):
per-leg weights, a noise band above which an improvement pays nothing, a
comeback multiplier (`1 + min(gap,100)/200`, a win only), the golden buzz
(`GOLDEN_BUZZ = 25`, one qualified seat), `paid_legs` (a strategy outside the
game's priced legs scores no improvement), and `landed` gates on the pot, the
buzz and the location bonus. The archived `settle` has none of these; it is the
portable core.

## Settlement

PRD 19 states the round's worth in one block `[M]` (`19:129-137`):

```
metric_profit = 100 × relative(baseline → best)        # 0 on an audit round
scored        = +10 × own audit hits
received      = −10 × rival audit hits
penalty       = −1  × (crash + agent_error + scope_violation + protected_violation)
subtotal      = metric_profit + scored + received + penalty
if jackpot: subtotal *= 3
profit        = subtotal + (2 if loc_delta < 0 else 0)
```

`relative(before, after, lower_is_better)` is the only non-trivial term `[M]`
(`_archive/arena.py:132-145`): `None` or unparseable → `0.0`; a zero start →
`0.0` if unchanged, else `±1.0` by direction; otherwise `delta / abs(start)`.

Three gates ride the formula, each bought with a recorded failure:

- **The pot pays only landed work (R27).** "the pot is a bonus for work that
  LANDED, so it pays for nothing but a literal `True` … season 16 paid +41.6667
  for a keep every cherry-pick dropped" `[M]` (`league/arena.py:1067-1072`).
- **The location bonus rides the same gate (R30).** "A seat that kept nothing
  shrank nothing … season 21 banked +1.0 for a timed-out seat whose diff never
  landed" `[M]` (`:1076-1080`).
- **The factor scales the win, never the loss.** "Season 18 tripled a -2 penalty
  into -6; a penalty is the price of an event the pot has nothing to do with"
  `[M]` (`:1157-1161`). The code is literally
  `subtotal = subtotal * 3 if subtotal > 0 else subtotal`.

The **audit** leg gets its own sentence because without it the leg dominates:
"An audit's pay is the transfer (+10/hit); its hit count is not also a 100x
metric improvement, or one hit would be worth 110" `[M]`
(`_archive/arena.py:178-186`).

The **jackpot** needs every declared leg to beat the floor. Archived:
`_jackpot` returns `False` unless all of `SNAPSHOT_KEYS = ("better","cheaper",
"faster")` are present in both snapshots and each `relative(trunk, seat) >
floor` `[M]` (`:160-165`). A single-metric game therefore has no jackpot at
all — not a hard one, an impossible one `[I]`. That is why no pot fires in the
VOD record: "the trunk carried no `faster` snapshot at all" `[M]`
(`19:139-142`).

**No reading is not a zero (R21).** "a result with no baseline is `no_reading`,
not a zero — the round could not tell a leg that gained nothing from one that
could not be read" `[M]` (`league/arena.py:1062-1065`).

## Sealed captains

A captain sees its bank, its last result and the rival's kept range, and answers
one JSON object `{strategy, buy, reason}`. The runner writes the canonical JSON
(sorted keys, compact separators) and its sha256 before the round starts — "so
the choice is fixed before the outcome is known" `[S]` (`19:165-172`) — using
the pure `seal()` `[M]` (`_archive:269-272`).

Fallbacks are silent and named: an unparseable reply becomes the team's previous
strategy with `reason: "captain fallback"`, and a fallback audit with nothing to
audit becomes `better` `[M]` (`:296-322`). `audit` is refused outright before
round 2 `[M]` (`:312`).

**R32: clamp the number, keep the intent.** The archived runner rejects an
out-of-range `buy`; the live league clamps it:

> an over-limit buy must not cost the captain its strategy. The prompt invited
> 2 base + 1 free + 3 bought = the stated hard cap, so a live captain answered
> `buy: 3` with a good leg and was discarded onto its last one. Clamp it …
> `[M]` (`league/arena.py:2506-2510`)

Only a constitutional fault — an unknown strategy, a non-integer `buy`, an empty
reason — forfeits the decision `[M]` (`:2502-2512`). The two behaviours are a
real divergence between the archived and live copies, not a typo `[M]`.

## Iterations: the cap is a cap (R36)

Archived `iterations_for` computes `base = BASE_ITERATIONS + loss_bonus`, takes
`wanted = clamp(buy, 0, BUY_MAX)`, `room = max(0, cap − base)`, and buys
`min(wanted, room, bank // BUY_COST)` `[M]` (`_archive:148-157`). The live
version clamps the base as well:

> Season 23 (R36): the cap bounds every grant, not only the buys. A seat that
> lost the last round AND trailed summed to 4 grants against a cap of 3, then
> had its buys refused because `room` was 0 — so the prompt's "hard cap" was
> false in exactly the rounds a comeback seat needed it to be true. `[M]`
> (`league/arena.py:952-957`)

The charge is separate from the payoff: the bank moves by `profit − cost`, and
every row carries the `cost` cell, because "Season 22 recorded `cost: 4` beside
banks that only ever added the payoff, so every buy was free and the prompt's
price was fiction" `[M]` (`:6356-6361`).

## Slots, opener, void (R28)

- **Alternating opener.** `seat_order(n)` is `("A","B")` on odd rounds and
  `("B","A")` on even ones — "over a season each team opens about as often as it
  follows, and neither owns the opening slot the way A did" `[M]`
  (`league/arena.py:5894-5902`).
- **A slot belongs to its seat.** `seat_wall(deadline, now) =
  max(0, min(ROUND_WALL, deadline − now))`, the caller caps it at `SEAT_WALL`,
  and a seat with less than `MIN_SEAT_WALL = 240` s left is **not launched**:
  "A slot belongs to its seat — the first seat can no longer spend the second's
  time" `[M]` (`:5905-5919`, `:346-350`). The record says `not_served: True`
  with exit code `199`, a value no wrapper, shell or signal returns `[M]`
  (`:366,5922-5964`).
- **Void, not scored.** A round that serves only one seat pays nobody. The
  settlement is the single writer of that zero: "it banks 0 for both seats and
  writes a `[0.0, 0.0]` payoff whatever profit it was handed, so no caller can
  leave a half-played round reading as a played one. A void round also names no
  loser: nothing was played, so nothing was lost" `[M]` (`:6349-6354`). The
  `VOID_ZEROED` map zeroes every component a scoreboard prints —
  `profit, metric_profit, jackpot, golden_buzz, loc_bonus, audit_scored,
  audit_received, penalty` — "or the row would show a real 0-0 beside a pot"
  `[M]` (`:6322-6334`). Cost is 0 too: "the seat may never have been served the
  buy it was granted" `[M]` (`:6361`).

## R39: a tie goes to the opener

Two seats can measure the same improvement. The merge order is by profit, and a
tie is broken by the round's own opener:

> Season 23 (R39): a tie is not a merit order, so it no longer decides the
> round. Rounds 70 and 71 both had the seats measure the SAME improvement …
> the stable sort kept A first, A's keeps applied first, and
> `guard_reverted_team` reverted the LAST merged — B, both rounds, for no reason
> either seat could read. `[M]` (`league/arena.py:6469-6477`)

`round_winner` itself returns `None` on equal profit `[M]` (`:1218-1227`), so a
tie names no loser and the opener — `seat_order`'s first element — merges first.

## Equilibrium: the caveat is the rule

The verdict is an epsilon-Nash check over the **explored** matrix `[M]`
(`_archive:222-261`): threshold `100 × floor`; regret = `max(0, best explored
alternative − current payoff)`; `reached` only if both teams have no unexplored
strategy and no regret above the threshold. The floor ratchets `+0.005` per
round from `0.01`, so the rule gets harder as teams get better `[M]`
(`:264-266`).

In VOD round 1 both regrets were `0.0` and the verdict was still
`"reached": false`, because three strategies per team were unexplored `[M]`
(`round-1/scoreboard.json`). PRD 19 states the consequence: "A game that
reported an equilibrium there would be lying with a straight face" `[M]`
(`19:183-186`).

## The five-round VOD record

`runs-vod/scoreboard.md` in full `[M]`:

| round | floor | profit A | profit B | jackpot A | jackpot B |
|-------|-------|----------|----------|-----------|-----------|
| 1 | 0.01 | 9.4247 (corrected from 10.1969) | -2 | n | n |
| 2 | 0.015 | 3.58621 | -2 | n | n |
| 3 | 0.02 | 3.65487 | -2 | n | n |
| 4 | 0.025 | -2 | -2 | n | n |
| 5 | 0.03 | -2 | -1 | n | n |

Trunk metric by round: `259 → 232 → 226 → 220 → 220 → 220` `[M]` (round bases
and bests; the recorded correction reads "259->232, not 230").

`state.json` closes the set `[M]`: banks `A 16.665784` / `B −5.0` — exactly
`4 + Σ profit` per team, since every `cost` was 0 — floor `0.035`, head
`30d2d46…`, `current {A: better, B: cheaper}`, five matrix rows, `round: 6`.
Choices were `audit` once (round 3, seat B) and `better`/`cheaper` otherwise;
no buy was ever taken `[M]`.

The correction is the interesting part of the record. Round 1's own
`scoreboard.json` still says `10.196911`; the aggregate tape says `9.4247` and
`state.json.corrections` carries the reason: an iteration in the keep set
changed call semantics, "so the referee reverted it (259->232, not 230)" `[M]`.
The per-round file was not rewritten: the correction is appended where the
aggregate reads it `[I]`.

Equilibrium was `reached: false` in all five rounds `[M]`.

## What the capture does not establish

- **No tournament result.** Five rounds is a demo of the record shape, not a
  sample. Both regrets sit at `0.0` while the matrix is unexplored, so the
  record says "not reached" — correctly — and says nothing about the game's
  quality.
- **Not the live settlement.** Weights, the noise band, the comeback, the
  buzz, `paid_legs` and the bounty are named but not specified here; a
  re-implementation from this page would reproduce the archived core, not
  season 38.
- **No claim the economy is well-tuned.** The live cap of 1 makes the buys
  inert; whether that is good is a season-level judgement this capture does
  not make.
- **No Counter-Strike.** The name is the money model. Nothing here analyses
  gameplay, demos or servers.
- **No portability proof.** The archived constants are portable as code; the
  live ones are bound to a repo whose metrics, scopes and referee live outside
  this capture (see the separate target-profile capture).
