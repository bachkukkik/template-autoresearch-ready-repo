---
title: Methodology Registration (the reusable template pattern)
created: 2026-09-26
updated: 2026-09-26
type: concept
tags: [autoresearch, research-method, doctrine]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md, raw/articles/autoresearch-program-md-reference.md]
confidence: high
---

# Methodology Registration (the reusable template pattern)

The registered, domain-independent distillation of the autoresearch pattern,
grounded by deep research (2026-09-26) on the upstream repo and the
slash-commerce real-world instance. The transferable pattern is NOT the ML
training loop.

## The invariant core

- **Three mutability classes in one loop:** a NOBODY-edits evaluator that owns
  the metric, eval inputs, and budget (upstream `prepare.py`); a HUMAN-edited
  policy file (`program.md`); an AGENT-edited artifact (`train.py`) — the only
  file allowed to change. See [[autoresearch-contract]].
- **Fixed resource budget per candidate** — iso-compare; no candidate wins by
  spending more. See [[fixed-time-budget]].
- **Append-only keep/discard ledger** (`results.tsv`, untracked) — every
  decision auditable and re-derivable; the metric is read from the run LOG,
  never the agent's self-report.
- **Loop:** tune → commit → run → metric → strict improvement ⇒ advance branch,
  else reset. Baseline first; NEVER STOP.

Evaluator/optimizer separation makes the objective exogenous: "make the metric
easier" is removed from the action space, and residual risk moves from cheating
(supervisable) to proxy-legitimacy ([[evaluator-legitimacy]], designable).

## Portability proof

The slash-commerce instance's `contract/` is byte-identical to this template's
(zero bytes changed) and met its objective by re-instantiating the same shape
one layer down. Only the DATA side of an instantiation ever moves.

## Instantiation recipe (any "optimize X better/cheaper/faster")

Preconditions: scalar metric with known direction; automated evaluation (no
human in the loop); one editable artifact. Refuse otherwise. Then: name X + the
one artifact → freeze evaluator (+ CI object-identity anti-cheat test) →
policy-as-data YAML → fixed budget → ledger + compare exit contract (0 keep /
1 discard / 2 invalid) → `program.md` → baseline first → tier metrics
T0–T3 → add queue/adversary/optimizer/watchdog layers only on observed failure.

Related: [[karpathy-autoresearch]] · [[domain-adaptation]] ·
[[better-cheaper-faster-metrics]] · [[kanban-factory]]

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
