---
title: Evaluator Legitimacy
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, research-method, decision]
sources: [raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Evaluator Legitimacy

The research-evaluator legitimacy / judgment-preservation thesis (Badkur & Dak
2026 survey): autonomous research systems reliably fix the **search prior** and
the **execution evaluator**, but none fully solves two persistent bottlenecks.

## The four-part model

1. **Search prior** — knowledge shaping which modifications get proposed (pretrained weights, `program.md`, experiment memory, optimizer state).
2. **Execution evaluator** — did the run succeed and how good is the metric?
3. **Research evaluator** — does the metric actually capture the research objective?
4. **Judgment-preservation channel** — do failed trials, mechanistic context, and structural insight survive compression across agent interfaces?

Scaling helps (1) and (2) far more than (3) and (4). Optimizing a frozen metric
too literally narrows discovery — declining edit entropy is the early warning.

## Implications for the loop

- Fixed-metric loops **Goodhart-converge**: the metric drifts from the objective.
- Humans add the most value at **high-leverage evaluator-design points**
  (AutoResearchClaw CoPilot: 87.5% accept rate vs full-auto).
- Adjacent systems push on this: [[autonomous-research-systems]].
- Run-to-run noise (~0.03 val_bpb) means naive keep/discard chases noise;
  statistical gates (e.g. the MLX fork's `rigor.py`) help. See
  [[autoresearch-platform-forks]].

Related: [[autoresearch-contract]] · [[val-bpb-metric]] · [[autonomous-research-systems]]