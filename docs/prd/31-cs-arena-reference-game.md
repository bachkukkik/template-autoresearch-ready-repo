# PRD 31 — CS-Style Arena: One Reference Game, Shipped as an Example

> Intent: PRD 28 located the game layer and said *configure downstream, never
> fork*. That is a boundary, not a shape — an adopter who has never seen a game
> still has to invent one. This PRD ships **one worked example**: a scripted
> two-team arena, replayed deterministically from an archived portable rule
> set, under `autoresearch/contract/examples/arena/`. It is an example an
> adopter reads and copies from, not a layer the template inherits: no engine
> module imports it, and an adopter's real game is still configured downstream,
> never forked.
> **Domain:** `arn` — the arena reference game.
> **Canonical tests:** `tests/unit/test_arena_rules.py`
> (`AC-ARN-001..019`), `tests/unit/test_arena_examples.py`
> (`AC-ARN-020..032`), `tests/integration/test_arena_ex3.py`
> (`AC-ARN-201..203`).
> **Stage 6:** [docs/31](../31-cs-arena-reference-game.md) — verdict `works`.
> **Grounding:** [cs-style-arena](../../kb/concepts/cs-style-arena.md),
> [raw capture](../../kb/raw/articles/2026-11-27-cs-arena-rules-capture.md).
> **Amends:** PRD 28 § *The layer model*; **narrows** the *no scoring layer*
> claim in PRD 20 § *Out of Scope* and PRD 22 § *Scope*.
> **Builds on:** PRD 02 (the contract), PRD 11 (examples corpus), PRD 22
> (target profile: one referee command, an evaluator hash at both ends).

## Context

A game layer is five moving parts: two seats on one frozen evaluator, a referee
that measures the trunk, a bank that funds each seat's attempts, a captain whose
choice is sealed before it plays, and a settlement that decides who keeps what.
PRD 28 named that layer, gave it a fate — *configure downstream, never fork* —
and listed the three things any game must declare: a target profile, a referee
command that prints one parseable number per leg, and the evaluator hash taken
at both ends of a round. Then it stopped.

A boundary with no shape is how a fork happens. The downstream instance PRD 28
describes did not rebuild its game out of carelessness; it rebuilt it because
nothing here showed what one looked like. Prose states invariants. An example
states them with numbers, in code, where a reader can run it. The archived
arena that holds those numbers is 1,387 lines and the live league is larger
again; both are the wrong thing to port and the right thing to distil.

This PRD distils them into one kit and three counterparts:

- `autoresearch/contract/examples/arena/` — `rules.py` (pure economy, seats,
  settlement, equilibrium, seal), `play.py` (a stdlib replay and settle CLI),
  and a `README.md` that carries the rules table, the live-mode recipe, and the
  CAN / CANNOT contract below.
- `ex1-music-abc-cs/` and `ex2-iris-knn-cs/` — two scripted four-round
  replays with their scoreboards vendored, so a reader sees a loss bonus, a
  buy, a void round, a clamped captain, an exact tie and an honest
  not-yet-reached equilibrium.
- `ex3-hotpath-speedup-cs/` — the same kit over a timing metric, where the
  gate and the audit do the deciding and **no timing value is compared**.

The kit is stdlib only, pure where it can be (`rules.py` opens nothing, spawns
nothing, reads no clock), and imported by no engine module. Three fairness
rules are the reason the numbers are worth reading: equal slots with an
alternating opener, an unserved round voided rather than scored zero, and
payment only for work that landed.

## Scope

In:

- the kit above (`rules.py`, `play.py`, `README.md`), stdlib only;
- the two economy presets — `PORTABLE` (bank 4, base 4 iterations, loss bonus
  1, buy 2 at cost 2, cap 6, audit transfer 10, event penalty 1, loc bonus 2,
  jackpot factor 3, ratchet 0.005, floor 0.01) and `LEAGUE_S38` (base 2, cap 1:
  one deep attempt per seat, cost 0), each with the comment that says why;
- three counterparts (ex1-cs, ex2-cs, ex3-cs), their `game.py` declarations,
  vendored scoreboards for ex1/ex2, a `.gitignore` per counterpart for seat
  scratch, and the story each one tells;
- the AC set below, in three test files.

Out, explicitly: an ex4 or ex5 counterpart (no two-seat transcript exists for
the live LLM example, and the real-OSS example's setup is heavy — a documented
absence, not a promise); a live LLM captain in CI; seasons, a 13-leg league,
bounty, films or a supervisor (PRD 28 layer 2, downstream); a referee placed
inside the measured tree of a real repository (that is what PRD 22's target
profile is for); any change to the engine, the contract ledger, the command
registry or an existing example; any new dependency.

**Amendment to PRD 28.** Layer 2 stays *configured downstream, never forked*,
and an adopter's real game is still theirs to configure — the phrase keeps its
meaning, and nothing here becomes a core layer. What changes is that the
template now ships **one reference game as a worked example**, under
`autoresearch/contract/examples/arena/`, beside the examples it already ships.
PRD 28 § *Out of scope* therefore reads "the game layer" as *no league, no
seasons, no seats in the engine* — and one example that demonstrates the shape.

**Narrowing PRD 20 and PRD 22.** Both said this repo has *no arena or scoring
layer*, and both were right about the engine: it still has none, and PRD 20's
referee half (A/A noise floor, drift canary, cheat probes, seeded-defect audit
rate) is still not ported. The narrowing is exact: an example under
`autoresearch/contract/examples/` is not a layer, no engine module imports it,
and an adopter's scoring stays downstream. PRD 20 gains one sentence pointing
here, so a reader cannot conclude the example contradicts it.

## CAN / CANNOT

This section is the contract. An example that quietly does more than this is a
defect; a request that asks for more is answered here rather than improvised.

### CAN

- two scripted teams on one frozen evaluator;
- an economy: bank, loss bonus, buy, iteration cap, two presets;
- sealed captains with a fallback and a two-sided clamp;
- an audit transfer — a seat that re-runs the rival's landed work is paid for
  hits, and pays for the rival's;
- a jackpot when a game declares two or more legs;
- equal slots with an alternating opener;
- a void round when a seat is not served;
- payment only for work that landed;
- an honest equilibrium verdict over the matrix actually explored;
- a live-mode recipe through the template engine (documented; untested in CI).

### CANNOT

- replay ex4 as a two-team game — no two-seat transcript exists, so a replay
  would be invented, not replayed;
- play ex5 here — heavy setup and timing noise; a follow-up issue, not a
  promise;
- pay a jackpot on a single-metric game;
- produce a deterministic outcome on a timing metric (ex3 checks gates, not
  winners);
- claim an equilibrium while a strategy is still unexplored;
- judge a round with an LLM referee;
- put the referee inside the measured tree of a real repository (use PRD 22's
  target profile);
- capture or analyse actual Counter-Strike gameplay — video, demos, game
  servers. "CS-style" names the economy, not the video game;
- ship seasons, a 13-leg league, a bounty, films or a supervisor; they stay
  downstream (PRD 28 layer 2).

## Requests that make no sense

Each of these is refused by name in the example's `README.md`, so the refusal
travels with the code:

- *"Make it play actual Counter-Strike."* — the example is an economy over a
  measured number; there is no game client, no map and no demo reader.
- *"Replay ex4 as a two-team game."* — one live transcript exists, not two
  seats; a two-seat replay would be fabricated.
- *"Add a jackpot to a one-metric game."* — a jackpot needs two legs to be a
  jackpot; with one key the rule returns false, by design.
- *"Pick a timing winner deterministically."* — a median seconds value cannot
  decide a round in CI; ex3 checks the guard, never the winner.
- *"Declare equilibrium early."* — the verdict is false while any strategy is
  unexplored, and the vendored ex2 record shows it staying false.
- *"Move the referee into the measured tree."* — a referee inside the measured
  tree is a seat grading itself; PRD 22's profile and its evaluator hash exist
  for that reason.
- *"Have an LLM judge the round."* — a judge is a second nondeterministic
  measurement; the settlement must be arithmetic.
- *"Run the live recipe in CI."* — it needs a model, a wall clock and a
  network; CI runs the scripted replay instead.

## Success Criteria

- **SC-arn-1 — The rules module is pure and the presets are stated once.**
  `rules.py` imports only the standard library, calls no `open`, `subprocess`,
  `os` or clock function, and both presets carry the values above, with
  `LEAGUE_S38` documented as the season-38 collapse to one attempt.
  _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-001, AC-ARN-002,
  AC-ARN-019).
- **SC-arn-2 — The economy arithmetic is the league's clamp.** With
  `PORTABLE`: base 4, 5 after a loss, up to 2 iterations bought at 2 bank each,
  never above 6, and a bank at or below zero buys nothing. With `LEAGUE_S38`:
  one iteration at cost 0, always. _Verify:_ `tests/unit/test_arena_rules.py`
  (AC-ARN-003).
- **SC-arn-3 — A round pays only what it measured.** Metric profit is 100 ×
  the relative improvement, the audit transfer pays both directions, a penalty
  is charged once per event in the penalty set — and never for an event that is
  merely recorded, such as `anchor_miss` — and an audit round pays the transfer
  alone. A seat with no baseline is `no_reading` — never a zero. _Verify:_
  `tests/unit/test_arena_rules.py` (AC-ARN-004, AC-ARN-007).
- **SC-arn-4 — The pot is a bonus for landed, multi-leg work.** A jackpot is
  false with no keys, false unless `landed` is true, and when it fires it
  scales only a positive subtotal — a penalty stays a penalty. The location
  bonus is paid for a smaller diff and withheld when `landed` is false.
  _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-005, AC-ARN-006).
- **SC-arn-5 — Equal slots, alternating opener.** The seat order alternates by
  round number, so each team opens about half the time; a first seat spending
  its whole slot still leaves the second a full one, and a grant under the
  minimum seat wall is 0 (the seat is not served). The round wall equals two
  seat walls plus the reserve: 2400 s. _Verify:_
  `tests/unit/test_arena_rules.py` (AC-ARN-008, AC-ARN-009, AC-ARN-010).
- **SC-arn-6 — An unserved round is void, not a zero.** `settle_teams` is the
  single writer of that zero: both profits are the void record, cost 0, banks
  unchanged, no loser, and the reason is recorded on the row. Void rows are
  skipped by the played-row reader, the cell payoff and the equilibrium.
  _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-011, AC-ARN-012).
- **SC-arn-7 — Banks are the sum of settled rows.** Each round applies
  `bank += profit - cost` and records both, with the round's last loser, so the
  final bank equals the opening bank plus the sum of every row's payoff minus
  cost. _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-013).
- **SC-arn-8 — An exact tie goes to the opener.** Higher profit wins; equal
  profit goes to the seat that had to move first, so a round always has one
  winner and the trunk advance is never ambiguous. _Verify:_
  `tests/unit/test_arena_rules.py` (AC-ARN-014).
- **SC-arn-9 — The equilibrium verdict is honest.** It is reached only when
  both teams have no unexplored strategy and regret is within the threshold; an
  unexplored cell blocks it, an over-threshold regret blocks it, and the
  returned record names the threshold and the current strategies it judged.
  _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-015).
- **SC-arn-10 — The floor ratchets one step.** Each settled round raises the
  floor by the preset's step, rounded to six places, so the bar is never
  reused unraised. _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-016).
- **SC-arn-11 — A captain's choice is sealed.** The seal is a canonical JSON
  text plus its sha256, and two dicts with the same content but a different key
  order seal to the same digest. _Verify:_ `tests/unit/test_arena_rules.py`
  (AC-ARN-017).
- **SC-arn-12 — A captain reply is parsed, not trusted.** `parse_captain`
  falls back on no object, an unknown strategy, `audit` in round one, a
  non-integer buy and an empty reason; an over-limit integer buy is clamped
  with `clamped: true` rather than dropped; the reason is stripped and
  truncated. _Verify:_ `tests/unit/test_arena_rules.py` (AC-ARN-018).
- **SC-arn-13 — A replay reproduces the vendored record byte for byte.**
  Replaying ex1-cs and ex2-cs into a temporary directory yields exactly the
  vendored `scoreboard.json`; no output carries an absolute path, a timestamp
  or a wall-clock second, so the file is the same on every machine.
  _Verify:_ `tests/unit/test_arena_examples.py` (AC-ARN-020, AC-ARN-025,
  AC-ARN-029).
- **SC-arn-14 — The record verifies without being trusted.** Every vendored
  captain `.sha256` equals the sha256 of its `.json` text, seat copies keep
  frozen files byte-identical to the base example, and each vendored bank
  equals the opening bank plus the sum of `payoff - cost` over its rows.
  _Verify:_ `tests/unit/test_arena_examples.py` (AC-ARN-022, AC-ARN-023,
  AC-ARN-024).
- **SC-arn-15 — The stories are honest.** Ex1's void round is labelled
  `injected` with the banks unchanged that round; ex2 records a fallback and a
  clamp, resolves its exact tie by the opener, and reports its equilibrium as
  not reached while a cell is unexplored. _Verify:_
  `tests/unit/test_arena_examples.py` (AC-ARN-021, AC-ARN-026, AC-ARN-027,
  AC-ARN-028).
- **SC-arn-16 — The README states the contract and the limits.** The arena
  `README.md` carries the rules table, the live-mode recipe, the CAN and CANNOT
  sections naming ex4 and ex5 and why, and a *Requests that make no sense*
  section with at least six entries; `examples/README.md` links to it.
  _Verify:_ `tests/unit/test_arena_examples.py` (AC-ARN-030, AC-ARN-031).
- **SC-arn-17 — What has no counterpart says so.** No `ex4-*-cs` or
  `ex5-*-cs` directory exists, and the README's CANNOT section names both and
  the reason, so an absent directory never reads as unfinished work.
  _Verify:_ `tests/unit/test_arena_examples.py` (AC-ARN-032).
- **SC-arn-18 — A timing metric is gate-checked, not timed.** The ex3-cs
  replay completes; its attack candidate is gate-rejected every time and never
  lands; the final trunk passes ex3's frozen gate; banks reconcile to
  `start + Σ(payoff - cost)`; and no timing value is compared anywhere in the
  test. _Verify:_ `tests/integration/test_arena_ex3.py` (AC-ARN-201,
  AC-ARN-202, AC-ARN-203).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-arn-1 | AC-ARN-001, AC-ARN-002, AC-ARN-019 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-2 | AC-ARN-003 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-3 | AC-ARN-004, AC-ARN-007 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-4 | AC-ARN-005, AC-ARN-006 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-5 | AC-ARN-008, AC-ARN-009, AC-ARN-010 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-6 | AC-ARN-011, AC-ARN-012 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-7 | AC-ARN-013 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-8 | AC-ARN-014 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-9 | AC-ARN-015 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-10 | AC-ARN-016 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-11 | AC-ARN-017 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-12 | AC-ARN-018 | `tests/unit/test_arena_rules.py` | unit |
| SC-arn-13 | AC-ARN-020, AC-ARN-025, AC-ARN-029 | `tests/unit/test_arena_examples.py` | unit |
| SC-arn-14 | AC-ARN-022, AC-ARN-023, AC-ARN-024 | `tests/unit/test_arena_examples.py` | unit |
| SC-arn-15 | AC-ARN-021, AC-ARN-026, AC-ARN-027, AC-ARN-028 | `tests/unit/test_arena_examples.py` | unit |
| SC-arn-16 | AC-ARN-030, AC-ARN-031 | `tests/unit/test_arena_examples.py` | unit |
| SC-arn-17 | AC-ARN-032 | `tests/unit/test_arena_examples.py` | unit |
| SC-arn-18 | AC-ARN-201, AC-ARN-202, AC-ARN-203 | `tests/integration/test_arena_ex3.py` | integration |

## CI/CD Gate

- Unit ACs run in the existing `unit` job; the three integration ACs replay
  two rounds of a scripted local metric in the existing `integration` job. No
  new job, no network, no model call, no Docker.
- Every replay copies into `tmp_path` and runs there — never inside the
  worktree, so a test cannot leave a seat directory behind.
- ex3-cs is bounded: two rounds, no buys, small strategy pools, targeting
  roughly 120 s of wall clock. If the integration job measures it slower, the
  example shrinks; the tier does not grow.
- `scripts/audit_pyramid.py` applies to `rules.py` and `play.py` unchanged
  (stdlib, no subprocess without a timeout, no `shell=True`);
  `scripts/audit-chars.py` and `scripts/audit-size.py` apply to the new
  markdown and tests.
- No new tracked root and no new dependency: everything lands under the
  existing `autoresearch/` root, under `tests/`, or in `docs/`.

## Assumptions

- [ASSUMPTION] **Two presets are the honest form of "portable versus live".**
  The archived arena's numbers (bank 4, base 4, cap 6) are portable because the
  kb capture records them as the codified rules; the live league's one-attempt
  preset exists because an LLM call dies at the wall, so its cap collapsed.
  Shipping both, named, is cheaper than arguing which one is "the" economy.
- [ASSUMPTION] **Scripted teams exercise the same code a live round would.**
  CI cannot afford a model call per round or tolerate its variance, so captain
  replies are fixed text: the reader, the fallback, the clamp, the seal and the
  settlement all run unchanged. The live recipe is documented and untested —
  stated, not implied.
- [ASSUMPTION] **An exact tie going to the round's opener is this template's
  rule, not the live league's.** The league's `round_winner` returns no winner
  on a tie; the example needs one deterministic winner so the trunk advance is
  unambiguous, and the seat that had to move first is the defensible owner. The
  rule is stated as local, never attributed downstream.
- [ASSUMPTION] **ex4 and ex5 are absences with reasons, not gaps.** No two-seat
  transcript exists for the live LLM example, and the real-OSS example's setup
  and timing noise make a replay a different artefact. A documented absence
  with a named follow-up beats a fabricated counterpart.
- [ASSUMPTION] **An example cannot fork the template.** Because no engine
  module imports the kit, deleting `examples/arena/` would change no behaviour
  outside its own tests — which is the mechanical test of "worked example, not
  layer", and the reason this amendment narrows PRD 20/22 rather than reversing
  them.

## Confidence

**High** for the rules arithmetic: every constant and every branch is ported
with its semantics intact and its own AC id, and the settled rows are checked
against their own banks. **Medium** for the examples' stories: they are
scripted, so they prove the mechanism works, not that a team plays well.
**Medium-low** for the live-mode recipe: it is written from the engine's
existing surface and deliberately not exercised in CI.
