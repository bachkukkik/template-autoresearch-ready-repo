---
title: Autoresearch Contract
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, research-method, agentic]
sources: [raw/articles/autoresearch-program-md-reference.md, raw/articles/autoresearch-template-research-conclusions.md]
confidence: high
---

# Autoresearch Contract

The transferable pattern behind Karpathy's autoresearch: **one human-edited
instruction file, one agent-edited artifact, one immutable evaluator** — plus a
fixed-time budget and a keep/discard loop.

## The three files

| File | Who edits | Role |
|------|-----------|------|
| `program.md` | human | The "super lightweight skill": setup (run tag, branch `autoresearch/<tag>`, baseline first), CAN/CANNOT rules, simplicity criterion, VRAM soft constraint, output format, NEVER STOP |
| `train.py` | agent | The artifact being optimized (model, hyperparameters, loop). Everything is fair game; it must run within the time budget |
| `prepare.py` | nobody | Immutable: constants, data, tokenizer, dataloader, and the ground-truth evaluator (`evaluate_bpb`) |

## The loop

1. Setup: agree a date-based run tag, create `autoresearch/<tag>` branch, verify data, initialize `results.tsv`.
2. Baseline first: run as-is, record the baseline.
3. Repeat: hypothesize → edit `train.py` → run ≤5 min → measure → keep/discard → commit or reset.
4. NEVER STOP: after setup the agent keeps iterating until manually stopped — the human may be asleep.

Results log to `results.tsv`: commit, val_bpb, memory_gb, status (keep/discard/crash), notes.

## Why it transfers

Porting to a new domain only changes the data side of `prepare.py` plus notes in
`program.md` — the loop, the metric, and the selection rules stay the same. See
[[domain-adaptation]] and [[problem-selection]]. On a skill-based repo, the same
contract maps `SKILL.md` ↔ `train.py` and an eval suite ↔ `prepare.py` — see
[[skill-self-improvement]].

Related: [[karpathy-autoresearch]] · [[val-bpb-metric]] · [[fixed-time-budget]] ·
[[document-funnel-doctrine]] · [[template-agentic-ready-repo]]

^[raw/articles/autoresearch-program-md-reference.md]