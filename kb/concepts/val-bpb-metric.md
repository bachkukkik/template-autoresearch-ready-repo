---
title: Val-BPB Metric
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/autoresearch-program-md-reference.md, raw/articles/autoresearch-template-research-conclusions.md]
confidence: high
---

# Val-BPB Metric

`val_bpb` (validation bits per byte) is the ground-truth metric of the
autoresearch loop: total per-token cross-entropy in nats ÷ (log 2 × total
utf-8 byte length of the targets), with special tokens masked.

## Why it is the metric

- **Vocab-size-independent** — byte normalization means architectural changes
  (vocab size, tokenizer, depth) are compared fairly. Lower is better.
- **Owned by the evaluator** — `evaluate_bpb` lives in `prepare.py`, which the
  agent cannot edit (anti-cheat). The agent's only job is "lowest val_bpb within
  budget".
- **Domain-agnostic** — transfers to non-text domains (ABC sheet music, code)
  because it is a byte-level loss; a monotonic ladder (e.g. 2.08 → 0.978) lets
  the agent greedily keep improvements. See [[domain-adaptation]].

## Caveat

Metrics can lie. In a code-generation run the metric improved ~55% while
generation degraded into repetition loops — evaluation uses teacher forcing,
generation is autoregressive, and tiny models exploit high-frequency tokens.
Always sample generated output, not just the loss. See [[problem-selection]].

Related: [[autoresearch-contract]] · [[fixed-time-budget]] · [[karpathy-autoresearch]]

^[raw/articles/autoresearch-program-md-reference.md] ^[raw/transcripts/U4kZ0t7Onhw.txt]