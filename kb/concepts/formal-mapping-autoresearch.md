---
title: Formal Mapping (optimization theory, Markov chains, game theory)
created: 2026-09-26
updated: 2026-09-26
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md]
confidence: medium
---

# Formal Mapping

Non-metaphorical formal readings of the autoresearch machinery (canonical
sources cited in the raw registration page).

- Keep/discard loop = elitist **(1+1)-ES** / stochastic hill climbing; as an
  **MDP**: state = codebase+ledger, action = edit, reward = Δmetric, policy =
  the LLM; NEVER STOP = infinite undiscounted horizon; simplicity criterion =
  complexity-regularized reward. The mutation operator is a bias-guided LLM
  proposal, not an isotropic Gaussian "ask".
- Board chain = finite **Markov chain**: statuses are states, the dispatcher is
  the transition kernel, done/blocked are absorbing; the re-seed cron is the
  closure operator that makes the chain irreducible/aperiodic (ergodic). See
  [[kanban-factory]].
- Defender×attacker = **Stackelberg security game**, scored by the minimax
  exploitability gap; the per-cycle campaign set = mixed strategy. See
  [[adversarial-optimization-layer]].
- Optimizer λ/μ = **Lagrange multipliers** / projected dual ascent.
- League seasons = **population-based training** (Jaderberg 2017) + AlphaStar
  league selection.
- Metric risk = **Regressional Goodhart** (arXiv:1803.04585) — sample real
  output on-policy; never trust the frozen scalar alone (the −55% loss /
  collapsed-output incident). See [[evaluator-legitimacy]].

Honesty markers: three of five layers are structural readings, not measured
dynamics — the dual regulator is implemented-but-inert, the season loop is
designed-not-observed, and the transition matrix was never estimated from data.

Related: [[autoresearch-contract]] · [[methodology-registration]]

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
