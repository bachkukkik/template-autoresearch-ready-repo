---
title: Fair-Competition Invariants
created: 2026-11-15
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method, agentic]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: medium
---

# Fair-Competition Invariants

When **two or more attempts compete for one budget** — two agent seats in a round, two
parallel fan-outs, A/B arms — fairness stops being a sentiment and becomes arithmetic that
can be checked per launch. The downstream league learned every one of these from a live
season, not from a stub: the defects below are recorded with the round that produced them,
and the repairs are numbered rules (R28–R31, R36–R39). ^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

> **Evidence.** `[S]` marks a figure **self-reported by the downstream repo** — quoted from a
> PR body or a committed season record, with its number. Unmarked arithmetic is checkable
> from the constants beside it.

## The round-61 failure that names the whole family

Two staggered seats shared one 1,800 s deadline. Seat A was granted **1,679 s** and used
~1,445 s; seat B was left **235 s**, below the 240 s floor at which anything can run, so B
was never launched and recorded rc **199** (`SEAT_NOT_SERVED`). Banks: A **4.0 → 86.857142**,
B **4.0 → 4.0** `[S]`. Both seats ran the same model route, season 18's fresh-token spend was
measured equal (234k vs 216k of a 300k budget) and banks reset each season — so the entire
spread was *seat order plus one deadline*. The referee could not see it either: its
circumstance counter judged a seat by whether its row named a **penalty event**, and an
unserved seat logs none — so the season's weight review was computed from seat A's rows
alone `[S]`. R37 later scored the referee on void rows as penalties; the invisibility is
older than the rule that fixed it.

## Slots and clocks

| Invariant | Arithmetic | What breaks without it |
|---|---|---|
| **Equal slot per competitor, allocated up front** | slot *i* closes at `started + (i+1)·WALL`; grant `min(WALL, remaining)` | the first competitor spends the second's time (1,679 s vs 235 s) |
| **Derive the aggregate from the slot** | `round = n·slot + reserve`; `season = cap × round-start budget` | the same number restated twice drifts (`cap 8 → 7` as the two-seat round's wall grew 1,800 → 2,400 s — eight rounds would have cost 24,000 s against a 21,600 s season) |
| **Never launch below the floor of usefulness** | below it, record *not served* with an out-of-band exit code (`199` — no wrapper, shell or signal returns it) | "we declined to run it" reads as "it died" (124) |
| **Clock starts at first work** | stamp at the first round, not at admission | an idle six-hour window refused round 1 at `37,479s > 21,600s` and the whole season played zero rounds |
| **Alternate the opener** | pure `seat_order(round)`; results travel as `(team, result)` pairs, order recorded per round | a stable launch order decides outcomes; a reorder re-maps results |

## Schedule

- **Never schedule a leg the state cannot pay.** A season-start reading at the metric's
  mathematical floor (0 for every lower-is-better count) is unwinnable: the seat is handed
  a free zero. An *unmeasured* snapshot is unknown, never zero; an all-at-floor set falls
  back to the unfiltered list rather than an empty schedule.
- **Rotation length = option count.** `n` options → `n` rounds. A 3-round rotation over 2
  playable legs gave one seat the only jackpot leg twice (+46.24 vs 0.0) `[S]`.
- **Explore only paid options** — a rotation that hands one competitor a paid leg and the
  other an unpaid one is unfair by construction, not by intent.

## Void, not scored

A round that cannot serve every competitor is **void**: single-writer settlement, every
scoreboard component zeroed, payoff `[0,0]`, **no loser named**, unserved seats named, real
work still merged. The half that is easy to miss: **every consumer** — estimates, payoff
matrices, audit rates, dashboards, season review — must skip void rows through *one shared
predicate*, or a zero masquerades as an observation. See [[deterministic-keep-gate]] for the
per-decision analogue.

## The agent contract

- **Clamp the agent's numbers, reject only its integrity.** An over-limit integer (`buy: 3`
  against a cap of 2) is clamped two-sidedly with the agent's qualitative choice kept; only a
  constitutional violation — scope, protected file, unparsable reply — forfeits the decision.
  The un-clamped version discarded a sound `spec_gap` strategy and replayed a crashing leg.
- **State every limit in the prompt, formatted from the constant that enforces it.** The
  prompt said *6* while the referee clamped at *2*; a literal in prose drifts from the
  constant and the agent pays for the drift.
- **Grant = charge, cap = cap.** Anything granted must be charged and anything charged
  granted: bank `profit − cost`, write the cost cell on every row, charge nothing for a round
  never served. For five rounds (r65–r69) eight rows carried `cost: 4` while the banks moved
  by `profit` alone — `4 + Σpayoffs` exactly — so every buy of that stretch was free `[S]`.
- **Grant only what the wall can fund.** Size from one measured trial plus tail:
  `100 + 2·(330+30) = 820 s` fits a 1,020 s slot, a 570 s timeout does not — **seven rounds
  (r63–r69) granted seats 2–6 iterations apiece and every one of the fourteen seat-rounds
  ran a single trial** `[S]`.
- **Every grant bounded by one cap** — base, loss bonus, comeback bonus and buys; the
  unchecked version granted 4 under a cap of 3, breaking the cap its own prompt promised.
- **Tell the agent its history and forbid it to look.** Last-N outcome rows plus "do not
  read files or run commands, answer now"; a captain with no history ran `ls`, dumped
  `state.json` and died at its timeout.

## Settlement order and referee accountability

- **Guard before bank.** Any check over the *combined* result runs between the merge and
  the settlement that pays for it; the reverted competitor settles `landed=False` so prize,
  bonus and location credit fall together; the revert **names the commit it removes** rather
  than resetting `HEAD~1`. Measured: both seats `81 → 73` paid **+51.63**, then the trunk
  guard failed on a duplicate id and one cherry-pick was reset *after* payment — replay
  reads 177/177 before the fix, 177/50 after `[S]`.
- **Score the referee on its own job**, separately from the players: voids, unreadable
  readings, rounds where nothing moved, seasons actually played — one named reason per
  point, and a negative score has teeth (a `long_leash` next season). Without it a season
  could serve one seat for seven rounds and still close clean.
- **Disjoint briefs for parallel agents.** Identical ranked lists produce identical fixes
  and identifier collisions (both seats covered the same 8 ids, both picked the next free
  e2e number). Split interleaved (`rows[0::2]` / `rows[1::2]`) so both halves are equally
  hard, and say so in the brief.
- **A tie is not a verdict.** With equal improvement the profit ties and a sort order decides
  who is penalised; break it with the rotating opener so the same competitor is not
  systematically the reverted one.

## Why this page is in this repo

The template runs one agent, not two seats — but it fans out (`delegate_task`, kanban) and it
will grow A/B arms. Every invariant above is stated target-agnostically: pure functions of
(slots, now, deadline), (round number) and (n options), ~150–250 lines, testable without a
league. The engine-side half of the same doctrine — a bound that may never kill the run it
bounds, and the wall restated in every layer — is on [[loop-stop-conditions]]; the
reward-side half is [[reward-hacking-countermeasures]].

^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

## Related

- [[deterministic-keep-gate]] — the per-decision contract this page's settlement half protects.
- [[loop-stop-conditions]] — the wall arithmetic and the refuse-to-start rule.
- [[objective-as-record]] — what the schedule is allowed to price.
- [[run-record-contract]] — where the void row, the guard revert and the referee score land.
- [[reward-hacking-countermeasures]] — the adversary the referee score exists against.
