---
title: Fixed Time Budget
created: 2026-09-04
updated: 2026-10-16
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/autoresearch-template-research-conclusions.md, raw/articles/2026-10-16-autoresearch-oss-landscape.md, raw/articles/2026-10-16-template-self-audit.md]
confidence: high
---

# Fixed Time Budget

The loop runs each experiment for a **fixed wall-clock budget**
(5 minutes of training time, excluding startup/compilation) regardless of
platform or what the agent changes.

## Why it exists

- **Comparability** — the agent cannot win by training longer; model size,
  batch size, and architecture changes are measured under identical time.
- **Platform-optimal** — the loop finds the best model *for your platform in
  that budget*; ~12 experiments/hour, ~100 overnight.
- **Anti-cheat** — "the only raw idea that matters is the one that trains
  faster per unit time."

## Consequences

- Results are **platform-bound**: an H100 result is not comparable to a MacBook
  one — record the platform and budget with any claim.
- The budget must be adapted to the problem: a large TSP instance benefited
  from relaxing 5 → 10 minutes (~another improvement jump). See
  [[problem-selection]].
- `TIME_BUDGET = 300` seconds lives in `prepare.py` (fixed constants).

## Enforced in code, not declared

A declared constant is not an enforced budget. In this template the shipped
baseline finishes in ~0.06 s, so `TIME_BUDGET` never gates any candidate
^[raw/articles/2026-10-16-template-self-audit.md]. The OSS study's recurring
hardening is to **enforce** the budget: import the constant and break the loop on
it, and wrap the run in a hard kill — n-autoresearch's Rust worker wraps the
training command in `tokio::time::timeout(kill_timeout, …)`, autokernel enforces a
~90 s ceiling in-band with `SIGALRM`, and TheGreenCedar's budget contract is
cumulative (a restart does not reset accumulated cost)
^[raw/articles/2026-10-16-autoresearch-oss-landscape.md].

## Noise floor

A budget bounds *how long* a candidate may run, not *whether* a delta is real.
Pair it with a minimum-delta / confidence rule (autokernel's explicit 1% rule;
MAD-based confidence in davebcn87 and Bilevel) before trusting a strict
improvement — see [[deterministic-keep-gate]] and [[evaluator-legitimacy]].

Related: [[autoresearch-contract]] · [[val-bpb-metric]] · [[problem-selection]] ·
[[deterministic-keep-gate]]
