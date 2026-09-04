---
title: Autonomous Research Systems
created: 2026-09-04
updated: 2026-09-04
type: comparison
tags: [autoresearch, research-method]
sources: [raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Autonomous Research Systems

The landscape positioned by the 2026 survey paper *"The Foundation Is the
Bottleneck"* (Badkur & Dak), with karpathy/autoresearch as the paradigm
originator. Each system adds a different capability to the loop.

| System | What it adds | Evidence / notes |
|---|---|---|
| karpathy/autoresearch | Original loop: program.md + train.py + prepare.py, 5-min budget, val_bpb | ~100 experiments/night; 20 stacked optimisations; 11% training speedup (per Fortune, secondhand) |
| SkyPilot parallelisation | Factorial grid waves across 16 GPUs; heterogeneous tiering (screen on cheap, validate on premium) | ~910 experiments/8h, val_bpb 1.003 → 0.974, ~9× faster; captures interaction effects |
| Bilevel Autoresearch | Outer loop code-generates search mechanisms instead of tuning prompts | ~5× ablation gain (single-source, high variance) |
| Centaur | Hybrid HPO: CMA-ES + LLM sharing full optimizer state | best reported val_bpb 0.9739 |
| Sibyl | Self-evolving trial-and-error harnesses on Claude Code; trial→behaviour conversion | arXiv 2026-05 |
| AutoResearchClaw | 23-stage pipeline: debate, self-healing Pivot/Refine, VerifiedRegistry, HITL, cross-run evolution | +54.7% vs AI Scientist v2 on ARC-Bench; CoPilot 87.5% accept rate vs full-auto |

## Verdict

All systems enrich the search prior and fix the execution evaluator; the open
problem is [[evaluator-legitimacy]] — research-evaluator validity and
judgment preservation across agent interfaces. Cautionary case: a Shopify/liquid
optimization (53% faster parse+render, 93 commits) stayed unmerged — execution
wins are not research wins without production validation.

Related: [[evaluator-legitimacy]] · [[karpathy-autoresearch]] · [[autoresearch-platform-forks]]

^[raw/articles/autoresearch-template-research-conclusions.md]