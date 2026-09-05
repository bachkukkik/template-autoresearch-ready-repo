---
title: Research Job Pattern
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, data-model, decision]
sources: [raw/articles/mcp-autoresearch-service-conclusions.md]
confidence: high
---

# Research Job Pattern

How a long-running autoresearch loop ([[autoresearch-contract]], 5-minute
experiments, multi-hour loops) is exposed to both agents (MCP tools) and humans
(REST). Core decision: **durable job-id/poll first, Tasks extension as opt-in
augmentation**.

## Job-id/poll (universal)

- `research_start` (or `POST /api/v1/research`) returns `job_id` immediately.
- `research_status` / `research_results` poll the durable store.
- Works with *every* MCP client and with plain REST — no client-side opt-in.
- Dispatches are idempotent via an explicit `idempotency_key`; task IDs bound to
  the auth context; TTL + concurrency caps per requestor; progress via
  `notifications/progress` (`progressToken` in `_meta`).

## Tasks extension (opt-in)

- 2026-07-28 spec, SEP-2663 (graduated from the experimental 2025-11-25 Tasks).
- Server-directed: on a long `tools/call`, server durably creates a task
  (`CreateTaskResult`, `resultType:"task"`, `taskId`/`ttlMs`/`pollIntervalMs`);
  client drives `tasks/get`, `tasks/update`, `tasks/cancel`.
- Statuses: `working → input_required | completed | failed | cancelled`.
- Client support is uneven (2026-09-04) → never required for the template.

## Store

Template default: **SQLite + APScheduler in-process** (batteries-included, survives
restarts, zero infra). Documented upgrade path: Postgres (pg-boss) / Redis
(BullMQ) when multi-instance or high volume. True partial-result token streaming
is still a draft (SEP-2998) — status progress, not token streams, for v1.

Related: [[mcp-streamable-http-transport]] · [[fixed-time-budget]] · [[fastmcp]]

^[raw/articles/mcp-autoresearch-service-conclusions.md]