---
title: Local LLM Controllers
created: 2026-09-04
updated: 2026-09-04
type: comparison
tags: [autoresearch, agentic, example]
sources: [raw/transcripts/jCNeVZJAYGM.txt, raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Local LLM Controllers

A single-run bake-off (video jCNeVZJAYGM): four local LLMs drove the exact same
karpathy/autoresearch loop on one DGX Spark, ~6 hours each, objective = lowest
final `val_bpb` from a 1.19 baseline.

| Controller | Experiments | Final val_bpb | Notes |
|---|---|---|---|
| Qwen 3.8 27B | 21 (fewest) | 1.142 — winner | Thinking mode; decisive wins on batch size + warm-up; second-guesses itself |
| Nemotron 3.5 Lightning 30B A3B | 43 (most) | 1.143 | Fast; "ripped through" experiments |
| Ornith 1.5 35B A3B | 33 (2 keeps) | mid-pack | LR-divergence crash (survived via loop guard); struggled after context compaction |
| Muse Glimmer ~30B | — | last | Instruction-following failures; idle-stalling — fatal for unattended autonomy |

## Selection dimensions for a research agent

- **Autonomy** — must not stall at prompt boundaries (make-or-break for overnight runs).
- **Thinking vs speed** — thoughtful experiments won with fewer iterations; speed is a legitimate alternative axis.
- **Crash recovery** — loop guards + state recovery after context compaction matter.
- Single-run benchmark, ASR-garbled names/numbers: treat the exact margins as indicative.

Related: [[autoresearch-contract]] · [[karpathy-autoresearch]] · [[problem-selection]]