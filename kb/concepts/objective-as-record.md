---
title: Objective as Record
created: 2026-11-15
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method, data-model]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: medium
---

# Objective as Record

**Whatever you would edit to change what you optimise is data, not a constant.** A code edit
can only describe the objective the code now ships with; every earlier result stays recorded
against an objective that no longer exists anywhere to be read — so no earlier period can be
resumed from what it actually played, and its numbers are not comparable to a later one. The
downstream league hit this at season 17: every leg of its only game sat at a measured floor or
was structurally unwinnable (`better` and `fresh` closed at 0, `cheaper` proved unmovable) and
there was no way to say "this game is exhausted, here is its successor" without editing the
constant that also described seasons 1–17 `[S]`.

> **Evidence.** `[S]` marks a figure or a failure mode **self-reported by the downstream repo**
> — read from a PR body, a committed record, or the code it cites.

## Two files, two shapes

| File | Shape | Answers |
|---|---|---|
| `metrics.json` | **registry** — every metric a leg may name, each a nine-field contract | what can be measured, and how |
| `games.json` | **lineage** — `parent`, `status`, priced legs + weights, readings played without pricing, prize keys, periods owned, `reason`, `notes` | what this period is optimising, and what it was forked from |

Records live beside the module that reads them, **never in a measured checkout** (a record
*about* a tree must not be an input *to* it).

## The nine-field metric contract

`name · direction · unit · command · repeats · noise_floor · exploit · cheat_probe · guard`

A metric with no `command` cannot be re-measured next season; one with no `exploit` has not
been told what could game it; one with no `cheat_probe`/`guard` is a number a faker can move.
This is the documentation form of [[verify-guard-contract]] and the contractual form of the
probes in [[reward-hacking-countermeasures]].

## Invariants a validator must return as a list

- **Directions are refused, never defaulted** (`('lower','higher')`): a silent default turns
  every regression into a win for a metric that should only fall, and nothing downstream can
  tell.
- **Exactly one objective is active**, and every period is owned by exactly one record. Two
  active objectives mean two weights for the same round and no way to say which settled it; a
  period listed twice has two accounts of the same numbers.
- Unique metric names; every priced leg registered; parent exists; the chain is acyclic and
  rooted; an active record has ≥ 1 leg.
- Loaders **raise** on unreadable input (operator error); `validate()` returns **every**
  contradiction as a short list so a hand-edited record is fixed in one pass instead of one
  error per run. Measured failure modes that still loaded and still played `[S]`: a duplicate
  metric name made `direction_of` answer from whichever row came first — it returns the first
  registry entry whose name matches — a missing direction read a rise as a win, a leg naming
  an unregistered metric was paid and never measured.

## Fork on exhaustion, retire by status

- Write the fork's `reason` against the **parent's measured exhaustion** — which leg closed at
  its floor, which band is wider than any achievable win. A fork with no floor evidence is a
  rewrite, not a fork.
- A prize keyed on a leg with no headroom is a rule that can never fire: narrow the prize to
  the legs with measured headroom and intersect it with the legs the period actually pays. A
  leg retired at a fork is `archived` in the record, never deleted, and the prompt offers only
  priced legs while marking the rest *reading only* — the parser stays permissive, so
  narrowing what is **offered** never narrows what is **accepted**.
- **Archive, never delete**: archived records keep old periods readable and comparable long
  after the code that played them has changed. The next fork adopts the previous
  `weights_after`, so a period's close is the next period's opening.

## Pricing only what the measurement can resolve

`metric_profit = 100 · weight · relative_improvement`, where a leg whose measured band ≥ its
improvement pays **0.0** (the reading is never rewritten — the band is what it was measured
against), weights are clamped (`0.5 … 3.0`), and a leg that never cleared its band prices
*down* to the floor, never up. A missing reading is never a zero. The band is the noise floor
of [[better-cheaper-faster-metrics]]; the floor-leg schedule rule is on
[[fair-competition-invariants]].

## In this repo

The template's ledger already records a baseline with its commit; this page is the shape to
**extend**, not a second store. Single `metric_name`/`direction` on a run config is the
degenerate case: it dies at its floor and cannot describe what to optimise next.

^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

## Related

- [[verify-guard-contract]] — how each metric's command and guard are produced.
- [[run-record-contract]] — the period record that owns the game id and the weights.
- [[better-cheaper-faster-metrics]] — metric tiers and the noise floor a leg's band is measured from.
- [[fair-competition-invariants]] — never schedule a leg at its floor; rotation = option count.
- [[reward-hacking-countermeasures]] — why every metric carries an exploit and a probe.
