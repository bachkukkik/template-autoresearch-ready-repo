---
title: Adversarial Optimization Layer (defender x attacker x optimizer x conductor)
created: 2026-09-26
updated: 2026-09-26
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md]
confidence: medium
---

# Adversarial Optimization Layer

The game layer added ON TOP of the autoresearch loop when the metric saturates
or lies — the structural answer to [[evaluator-legitimacy]]'s Goodhart problem.

## Roles (game-theoretic)

- **Defender** (Stackelberg leader) commits first: verifier-first topology,
  failing test written before the fix; only released claims are in scope.
- **Attacker** (best responder) hunts with point-of-view campaigns; the PoV
  contract (no proof-of-violation, no points) + context rationing (reads only
  released claims, no KB-layer authority) make its failing PoVs external ground
  truth the defender cannot fabricate — a holdout set that stops fixed-metric
  Goodhart convergence.
- **Optimizer** (mechanism designer, not a competitor) prices the shared budget:
  `max Q_d s.t. Y_a ≥ τ, d+a ≤ 3`; λ = shadow price of the attacker-yield floor,
  μ = shadow price of one LLM slot; `λ←max(0, λ+η(τ−Y_a))` is projected dual
  ascent.
- **Conductor** (referee) polices information asymmetry, pinning/pin abuse, and
  layered hot-fixes (never bypasses the janitor; byte-identity read-back).
- **Survivor ledger + league:** declined attack classes seed the next cycle's
  campaign prompts; Pareto-dominance league (PBT + AlphaStar-style selection)
  renders PROMOTE/KEEP/RETIRE per variant.

## Measured caveat (honest)

In 22 live cycles the dual regulator never bound: λ=μ=0 and slot_mix constant
— under the recorded parameterization (τ saturated above realized yield; d+a
always at cap) the multipliers CANNOT move. A regulator that cannot bind is
dead code: verify the multipliers move before trusting the mechanism.

Related: [[kanban-factory]] · [[autoresearch-contract]] · [[methodology-registration]]

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
