---
title: Kanban Factory (the generative research process)
created: 2026-09-26
updated: 2026-09-26
type: concept
tags: [autoresearch, agentic, ops]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md]
confidence: high
---

# Kanban Factory (the generative research process)

When wall-time/cost are themselves objectives, autoresearch candidates become
cards on a queue: the loop stops being one agent in a repo and becomes a
card-graph factory (the slash-commerce instance's operating mode).

## Mechanics

- **Card flow:** todo → ready → running → done, plus blocked/triage; blocked
  counts LIVE for cycle presence; hard per-card ceiling (7200 s); ≤3 concurrent
  LLM workstreams; a cycle = DAG run keyed by idempotency prefix.
- **Closure:** the board graph is a DAG, so an un-reseeded chain terminates;
  the re-seed cron + chain-orchestrator is the closure operator that makes the
  loop continuous (new cycle on upstream-terminal, backstop idle, or never-ran).
- **Self-healing is deterministic and LLM-free:** watchdog classification +
  digest, janitor zombie reclaim, default-deny policy resolver (dry-run
  default, `--apply --max-actions`), blocked-resolution predictor.

## Why a card-graph beats one agent loop

Parallelism under the shared cap (zero-token queueing), separation of concerns
/ anti-Goodhart (one writer per track, context rationing, independent arbiter),
resumability (DB as durable job store), audit trail (handoff + exec-summary
comments), human-free operation.

Related: [[autoresearch-contract]] · [[adversarial-optimization-layer]] ·
[[methodology-registration]] · [[research-job-pattern]]

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
