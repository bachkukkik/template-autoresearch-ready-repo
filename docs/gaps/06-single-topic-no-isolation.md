# 06 — Single-topic, shared-workspace runner (no isolation)

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-05
**Resolved:** 2026-09-05

## Observation

PRD-05 SC2/SC3 (as built, docs/05) exposes one research loop per job token —
but the *topic* carried by the job never reaches the workload, and every job
executes in the same shared directory.

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md:43-47` | `POST /api/v1/research` kickoff returns a job; job model has `topic`; per-job lifecycle queued→running→completed. |
| B | `service/src/main.py:78-88,114-130` | `research_start` stores `topic` in the job but `_run_job` calls `_runner.run_loop()` with **no topic and no per-job directory**. |
| B | `service/src/runner.py:70-127` | `run_loop()` always executes `prepare.py`/`train.py` in the single `DEFAULT_WORKLOAD_DIR` (`service/workload/`); `prepare.py` writes `data.txt` *next to itself* — two concurrent jobs race on the same `data.txt` and produce byte-identical output for different topics. |

## Evidence

```bash
grep -n "topic" service/src/main.py          # topic only appears in ResearchRequest + create_job
grep -n "run_loop" service/src/main.py       # _run_job -> _runner.run_loop()  (no args)
grep -n "DEFAULT_WORKLOAD_DIR" service/src/runner.py   # single shared workload dir
# AC-MCP-021 (tests/unit/test_runner.py) exercises only the shared default workload
```

## Impact

- Two concurrent researchers cannot run different topics: results are
  identical regardless of `topic`, and concurrent execution races on the
  shared `data.txt` write (prepare step).
- The template's "serve autoresearch concurrently, multiple topics at once"
  promise (user request 2026-09-05) is unmet.

## Resolution

Code change + tests — new per-job workspace isolation, corpus delivery
(inline texts + files under `RESEARCH_CORPUS_ROOT`), and a
`RESEARCH_MAX_CONCURRENT_JOBS` cap, per
[docs/prd/06-multi-topic-concurrent-service.md](../prd/06-multi-topic-concurrent-service.md).
Verified in [docs/06-multi-topic-concurrency.md](../06-multi-topic-concurrency.md).
Status flips to resolved; archive after merge.