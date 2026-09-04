---
title: Fixed Time Budget
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/autoresearch-template-research-conclusions.md]
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

Related: [[autoresearch-contract]] · [[val-bpb-metric]] · [[problem-selection]]