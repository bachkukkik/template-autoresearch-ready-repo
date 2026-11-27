---
title: CS-Style Arena
created: 2026-11-27
updated: 2026-11-27
type: concept
tags: [autoresearch, research-method, agentic]
sources: [raw/articles/2026-11-27-cs-arena-rules-capture.md]
confidence: medium
---

# CS-Style Arena

Two seats, one evaluator, one round at a time. Each seat gets a copy of the same
tree and a bounded amount of work; a referee measures both against a trunk; a
settlement turns the round into bank, a payoff cell and (sometimes) a loser.
"CS-style" is the downstream league's name for this protocol, and the name is
about money, not shooting.

> Markers follow the capture this page is built from: `[M]` read in the code,
> `[S]` self-reported by the downstream record, `[I]` inference.

## The name is the economy

The downstream PRD's heading is literal: *"Counter-Strike's economy, ported."*
Four things travel `[M]`:

- a **starting bank** (4 points), so round 1 is not free;
- **income for losing** (+1 iteration), so a losing seat can still act;
- a **purchase** (2 points per extra iteration, at most 2 points' worth), so a
  seat can trade bank for work;
- a **hard cap** (6 in the portable game), so no grant escapes the arithmetic.

Nothing in either the archived runner or the live league reads a game server, a
demo or a frame. The measured object is a git worktree and a metric. What is
being copied is the *round-based budget model* — buy, save, eco, cap — which is
why the idea transfers to any two-attempt comparison with a fixed allowance.

A useful consequence: if you give two attempts the same fixed budget and score
them on the same metric, you are already playing a degenerate version of this
game. The protocol adds the parts that make the comparison fair and auditable.

## Four roles

| Role | Owns | Must not |
|---|---|---|
| **Team A / Team B** | one editable scope in its own copy; its keeps | read the rival's tree, edit the referee |
| **Referee** | the metric, the guard, the trunk, the trunk snapshot | live inside the tree it measures |
| **Captain** | one sealed JSON object: `{strategy, buy, reason}` | see the round's outcome before committing |
| **Settlement** | bank, payoff row, cost cell, loser | pay for work that did not land |

The referee's position is the load-bearing one: an evaluator inside the measured
tree is editable by the seat it scores. The league solves that with a
target-relative profile and a hash of the evaluator surface — see
[[target-profile-contract]].

## The rules that decide a round

1. **Compute the grant from the economy, once.** `base + loss bonus`, clamped to
   the cap, then buys fill only what is left under it, limited by bank. The cap
   bounds *every* grant, not only the purchases; the version that capped buys
   alone handed out 4 under a stated cap of 3.
2. **Price the round on relative improvement.** `100 × (baseline − best) /
   |baseline|` for a lower-is-better metric; the audit leg is paid as a transfer,
   never as a 100× improvement, or one hit would be worth 110.
3. **Seal the choice before the round.** Canonical JSON (sorted keys, compact
   separators) plus its sha256, committed first. A malformed reply falls back to
   the previous strategy with a named reason; an over-limit `buy` is clamped and
   the strategy is kept.
4. **Equal slots, alternating opener.** Each seat has its own wall; a seat with
   less than the usefulness floor left is *not launched*; the opener alternates
   by round number so neither seat systematically spends the other's time.
5. **Void, not scored.** A round that serves only one seat pays nobody: one
   writer zeroes every component, payoff is `[0,0]`, no loser is named, and cost
   is 0. Every consumer must skip void rows through one shared predicate.
6. **Pay only landed work.** The pot, the location bonus and the buzz all ride
   one gate: the keep reached the trunk. A worktree reading is not evidence.
7. **A tie goes to the opener.** Equal profit is not a merit order; the merge
   order breaks it with the rotating opener, so the same seat is not the one
   reverted every time.
8. **A missing reading is not a zero.** No baseline means `no_reading`, which
   pays nothing and says so — an unreadable leg must never look like a leg that
   read zero.
9. **Equilibrium is claimed over the explored matrix only.** Regret is measured
   against known alternatives and the verdict is `false` while any strategy is
   unexplored, however small the regret.

## What a record looks like

The downstream VOD run: five rounds, trunk metric `259 → 232 → 226 → 220 → 220
→ 220`, floors `0.01 → 0.035`, banks `A 16.67 / B −5.0`. Seat A took rounds 1–3;
round 4 tied at −2 apiece and named no winner; B took round 5 by a point (−1
against −2). The equilibrium verdict was `false` in all five — correctly,
because both teams still had unexplored strategies. Five rounds demonstrate the
record shape; they are not evidence about the game's quality.
^[raw/articles/2026-11-27-cs-arena-rules-capture.md]

## Which shapes fit

| Shape | Fits? | Why |
|---|---|---|
| Frozen evaluator + one editable file | **yes** | The canonical case: both seats edit one file, the referee runs the same frozen script, keeps are comparable |
| Live LLM transcript (ex4-style) | **no** | No two-seat transcript exists; a replay would be invented, not captured |
| Timing metric (ex3-style) | **gates only** | Wall-clock noise makes a winner meaningless; assert the gate, not the ranking |
| Single-metric game | **no jackpot** | The pot requires every declared leg to beat the floor; one leg makes it impossible, not hard |
| Two seats over two different repos | **not this** | The protocol compares seats on one trunk; different subjects are a different experiment |
| Three or more seats | **not yet** | Slots and the opener are written for two; a third needs its own arithmetic |

The asymmetry is deliberate: a worked example that says *no* to a shape it
cannot play honestly is worth more than one that pretends. The two refusals
above (live transcript, three seats) are why the template documents them instead
of shipping a hollow counterpart.

## Why the rules exist

Each rule is a repaired failure, not a principle. The round-61 case — one shared
deadline left the second seat 235 s, below the 240 s floor, so it was never
launched — is the family's origin story; the slot, opener and void rules are its
consequences. [[fair-competition-invariants]] holds the arithmetic.
[[adversarial-optimization-layer]] holds the other half: a game is only as good
as the adversary it can survive, and a referee outside the measured tree is part
of that surface. Where the metric itself comes from — and why "better, cheaper,
faster" is three legs rather than one score — is
[[better-cheaper-faster-metrics]].

## In this repo

The template runs one seat, so this is a **reference game**, not a core layer:
a worked example that an adopter can read, replay and discard. The distillation
rule is to keep the portable preset (the archived constants, not the live
league's season-38 preset), keep the three fairness rules above, and play
scripted teams so a replay is deterministic in CI. Seasons, weights, the noise
band, the bounty and the media layer stay downstream and are named here only as
things this page does not cover.

The distinction matters for adoption: a repo with one agent and one metric does
not need an arena. A repo that fans out two attempts over one evaluator does —
and then the rules above are cheaper to inherit than to rediscover. The
register that records why each was earned is [[veteran-decision-register]]; the
decision to move the evaluator out rather than play around it is
[[relocation-not-play]].

## Related

- [[fair-competition-invariants]] — slots, opener, void and the agent contract.
- [[target-profile-contract]] — where the referee lives and how it is hashed.
- [[adversarial-optimization-layer]] — the adversary the game is built to face.
- [[better-cheaper-faster-metrics]] — the multi-leg metric the pot needs.
- [[veteran-decision-register]] — the rules' provenance, one failure per row.
- [[deterministic-keep-gate]] — the per-decision keep/revert this game banks on.
