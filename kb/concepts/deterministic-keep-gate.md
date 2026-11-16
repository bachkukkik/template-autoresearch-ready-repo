---
title: Deterministic Keep Gate
created: 2026-10-16
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-16-autoresearch-oss-landscape.md, raw/articles/2026-10-28-autoresearch-real-world-engines.md, raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: high
---

# Deterministic Keep Gate

The keep/discard decision must be a **deterministic, LLM-free function with an
explicit exit-code contract**, never a judgment by the agent that proposed the
change. This is the operational form of the frozen evaluator in
[[autoresearch-contract]]: the loop may *propose* freely, but only a
deterministic comparison may *decide*.

## The contract

`compare --prev/--next` returns **0 keep · 1 discard · 2 invalid**. "Invalid" is
first-class: an unmeasured gate, a NaN/Infinity metric, or a missing pin forces
exit 2 rather than a spurious keep — the loop stops rather than optimising over
an unreadable number. The 19-repo OSS study shows the shape recurring whether or
not it is a literal `0/1/2` process code: ^[raw/articles/2026-10-16-autoresearch-oss-landscape.md]

- **evo** — `compare_scores` is non-strict (ties commit), NaN/Inf rejected, and a
  node commits only if the score improves *and* every inherited gate exits 0.
- **n-autoresearch** — `experiment::complete` computes `improved = val_bpb <
  current best` and returns `action='keep_commit' | 'git_reset'`; crash → `git_reset`.
- **leo-lilinxiao** — a state machine where a `keep` must strictly improve AND
  pass its guard AND carry `revert_commit=null`; anything else is an error.
- **Arbor** — the merge tool runs the held-out split itself and rejects the merge
  unless `test_score >= trunk_score`.
- **uditgoenka** — the `regression` subcommand emits a `STABLE/UNSTABLE` verdict
  with exit 0 STABLE / 1 UNSTABLE / 2 ERROR.

## The margin, not the delta (2026-11-15)

> `[S]` marks a figure self-reported by the downstream repo (PR body or committed record).

A deterministic comparison is necessary but not sufficient: **a keep must clear
`max(configured noise floor, z · SE of the difference)`**, with the SE taken from the
dispersion of the actual repeats and carrying the estimator's consistency factor (a median
point estimate carries `sqrt(pi/2) = 1.2533`). A bare relative floor banks jitter as
progress — the downstream league's 0.01 floor sat *3.8–5× below one standard error* for its
own proportion metrics at n=100 (SE 0.038 at p=0.82 to 0.05 at p=0.5; 0.038/0.01 = 3.8,
0.05/0.01 = 5), so a recorded keep could be pure noise `[S]`.

Three consequences, each a rule:

1. **Three verdicts, not two** — keep / discard / **inconclusive**. A delta inside the
   margin is neither proof nor penalty: revert it, cost nothing, and tell the agent "retry
   only with a larger change". An inconclusive counts as a non-keep for plateau purposes and
   never moves the incumbent.
2. **One repeat is not a measurement** — report `honest: false`, `spread: null` rather than
   inventing a spread, and set the repeat count **where the decision is made** (round plan,
   adapter, CI job), defaulting to `≥ 3`. A statistical gate defaulting to n=1 is *dormant*
   while the docs say it is live, which is worse than no gate.
3. **Replay validates the recorded margin**, not just the delta, or a plausible fabricated
   margin validates. Provenance is mandatory per adjudicated decision: model, route, engine
   version, referee version derived from the scoring command (`'verify:' + sha256(cmd)[:12]`),
   profile content hash, ISO-8601 UTC timestamp.

Backward compatibility of a stricter threshold is **proved over a parameter grid**, not
claimed: because `max(floor, z·SE) ≥ floor`, every new keep is an old keep — brute-force the
equivalence (3,584 metric × direction × floor points, 0 keep mismatches) and report the count.

## The agent's exit code decides nothing: salvage

The other half of a gate that trusts only the measurement is a **candidate that still exists
when the agent dies**. Reverting a tree because `not result.ok` discards exactly what an
overnight run usually holds — work finished after the clock ran out. The downstream league
lost a solved leg that way: `spec_gap` 30 → 0 inside the worktree, the adapter timed out at
570 s (exit 124), the tree was reverted **unread**, and the round recorded `keeps: 0`.

- `dead = not result.ok` falls through the **same** pipeline — ignored-file check, scope,
  protected hashes, commit, guard, measure, margin. A tree clearing the margin banks as
  `keep` with `salvaged: True` and `agent_exit_code`; nothing else about a keep changes.
- A dead tree that clears nothing reports `agent_error` **carrying** the metric it measured
  (an unjudged score is still on the record); scope/protected violations keep their own
  names, because a breach is about the tree, not the score.
- Salvage is not a licence to keep — the tree still has to clear the margin — and the wall
  must be refused *before* an iteration it cannot fund starts, or the measurement (and any
  salvage of it) never happens. That arithmetic is on [[loop-stop-conditions]].

## Why determinism, not a judge

An LLM judge reintroduces exactly the run-to-run variance the loop engineered
out, and makes cycle deltas unattributable. Determinism makes each delta
content-attributable. See [[evaluator-legitimacy]] for the legitimacy thesis and
[[better-cheaper-faster-metrics]] for the T0–T3 tiers that decide which fields a
gate may read.

## Related

- [[autoresearch-contract]] — the frozen-evaluator rule this operationalises.
- [[fixed-time-budget]] — the other half of the evaluator's invariants.
- [[autoresearch-oss-landscape]] — the 19 implementations the evidence comes from.
- [[verify-guard-contract]] — how the metric and the guard are actually produced, and the
  parse surfaces that make exit 2 detectable instead of silent.
- [[script-owned-keep-revert]] — who executes the decision; the 2026-10-28 study found the
  systems that survive scale put it in the control script, not the agent.
- [[autoresearch-engines-real-world]] — the 15-system follow-up study.
