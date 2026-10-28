---
title: Deterministic Keep Gate
created: 2026-10-16
updated: 2026-10-28
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-16-autoresearch-oss-landscape.md, raw/articles/2026-10-28-autoresearch-real-world-engines.md]
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
