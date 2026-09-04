---
title: Karpathy Autoresearch
created: 2026-09-04
updated: 2026-09-04
type: entity
tags: [autoresearch, architecture]
sources: [raw/articles/autoresearch-program-md-reference.md, raw/articles/autoresearch-template-research-conclusions.md]
confidence: high
---

# Karpathy Autoresearch

Andrej Karpathy's reference implementation of letting an LLM agent run its own
miniature ML research program on a single GPU: *"AI agents running research on
single-GPU nanochat training automatically."*

## Key facts

- URL: https://github.com/karpathy/autoresearch · created 2026-03-06 · MIT (README; no LICENSE file tracked) · Python
- ~95.2K stars / ~13.4K forks at the 2026-09-04 snapshot; last push 2026-03-26
- Deliberately three files that matter: `prepare.py` (read-only), `train.py` (agent-edited), `program.md` (human-edited skill) — see [[autoresearch-contract]]
- Metric `val_bpb`, fixed 5-minute budget, `results.tsv` log, branch-per-run (`autoresearch/<tag>`), baseline first, NEVER STOP
- Repo is deliberately small/self-contained; MIT; notable forks on other platforms — see [[autoresearch-platform-forks]]
- Karpathy's own overnight run: ~700 autonomous changes, found bugs he'd missed in years of manual tuning (wrong optimizer betas, missing regularization), 11% faster training (as quoted in the video corpus)

## Relations

- Pattern basis for this template repo ([[template-agentic-ready-repo]])
- Positioned by the Badkur & Dak 2026 survey as the paradigm originator — see [[evaluator-legitimacy]] and [[autonomous-research-systems]]
- The video corpus puts the loop through domain adaptations — see [[domain-adaptation]], [[problem-selection]], [[autoresearch-video-corpus]]

Related: [[autoresearch-contract]] · [[val-bpb-metric]] · [[fixed-time-budget]] · [[autoresearch-platform-forks]]

^[raw/articles/autoresearch-program-md-reference.md] ^[raw/articles/autoresearch-template-research-conclusions.md]