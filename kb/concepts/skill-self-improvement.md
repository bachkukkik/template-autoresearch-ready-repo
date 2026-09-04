---
title: Skill Self-Improvement
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, agentic, example]
sources: [raw/transcripts/qKU-e0x2EmE.txt, raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Skill Self-Improvement

Applying the autoresearch contract to agent skills: instead of hand-fixing a
Claude skill that fails ~30% of the time, let the loop improve it.

## The mapping

| Autoresearch | Skill loop |
|---|---|
| `train.py` (mutable artifact) | the skill's `SKILL.md` (prompt) |
| `program.md` (human-edited objective) | the optimizer agent's instruction file |
| `prepare.py` + `evaluate_bpb` | a binary yes/no eval suite (agent-written test suite) |
| 5-minute re-run loop | mutate-and-keep-winner every 2–5 minutes |

## Loop mechanics

- **Binary evals preferred** — Likert scales compound per-step model variance.
- **Aggregate runs** (mode + median) — a single run is a sample from a noisy distribution.
- **Keep the winner, mutate, repeat** — scheduled, unattended.
- **The eval suite is the human's lever** — criteria quality pays back loop quality.
- **Watch Goodhart** — over-narrow evals get "parroted back"; the metric drifts
  from intent.

## Reported results

- Diagram-generator skill: 32/40 → 39/40.
- Website (same recipe, Google Lighthouse): ~1100ms → 67ms (~81% improvement, ~67 tests).
- Cost reported ~$0.02/generation.

Related: [[autoresearch-contract]] · [[problem-selection]] · [[template-agentic-ready-repo]]

^[raw/transcripts/qKU-e0x2EmE.txt]