# PRD 06 — Concurrent Multi-Topic Autoresearch Service

> Intent for the service layer: the autoresearch service must serve **multiple
> research topics concurrently out-of-the-box** — one requestor runs topic A
> from `kb/raw/transcripts/A.txt` while another runs topic B from
> `kb/raw/transcripts/B.txt`, in the same process, with per-job isolation.
> Grounded in: [research-job-pattern](../../kb/concepts/research-job-pattern.md),
> [autoresearch-contract](../../kb/concepts/autoresearch-contract.md),
> [fastmcp](../../kb/entities/fastmcp.md),
> [mcp-streamable-http-transport](../../kb/concepts/mcp-streamable-http-transport.md).
>
> Decision record 2026-09-05 (user-approved): corpus sources = **inline texts
> AND files under a corpus root** (`RESEARCH_CORPUS_ROOT`, compose mounts
> `./kb/raw` read-only at `/kb-raw`); concurrency cap =
> `RESEARCH_MAX_CONCURRENT_JOBS` (default 4); REST/MCP stay **sync def**
> (threadpool + scheduler/subprocess — no `async` rewrite needed, see SC4).

## Context

PRD-05 shipped the dual-exposure service: a durable job-id/poll loop over
SQLite/APScheduler, bearer auth, and a subprocess runner executing
`prepare.py` → `train.py` under a time budget. What it did NOT ship is
**isolation and topic wiring**: `ResearchRequest.topic` is stored in the job
row but never reaches the runner, and every job executes in the same shared
`service/workload/` directory — two concurrent jobs would race on the same
`data.txt` cwd and produce byte-identical output regardless of topic. See
[docs/gaps/06-single-topic-no-isolation.md](../gaps/06-single-topic-no-isolation.md)
for the recorded divergence.

**Users:** concurrent researchers/agents — user1 runs topic A from
`kb/raw/transcripts/A.txt`, user2 runs topic B from `B.txt`, at the same time,
through the same service (REST or MCP). **Constraints:** batteries-included
(single process, zero external infra), per-job sandbox posture (subprocess +
time budget, no shell), all run/install/build code self-contained in
`service/` per the service convention.

**Decided design (2026-09-05):** each job gets an **isolated workspace**
`<workspaces_root>/<job_id>/` — a copy of the **canonical autoresearch
contract** (`contract/`, the single source of truth; the service consumes it
directly via the `/app/contract:ro` mount and copies it per-job) plus
`topic.txt`, `corpus/` (inline texts and/or files copied from the corpus
root), and `context.json`. The runner executes inside that workspace. Inline
corpus texts work everywhere; corpus files resolve under `RESEARCH_CORPUS_ROOT`
(default `<repo>/kb/raw` in dev, `/kb-raw` in the compose container) and are
validated **fail-fast at submit** (400). Concurrency is bounded by a
ThreadPoolExecutor on the scheduler sized from `RESEARCH_MAX_CONCURRENT_JOBS`
(default 4). Workspaces are retained after terminal jobs (observable runtime
artifacts; `data/` is gitignored).

## Success Criteria

- **SC1** — Every research job runs in an **isolated per-job workspace**:
  `<workspaces_root>/<job_id>/` contains a copy of the canonical autoresearch
  contract (`contract/`), `topic.txt`, and `context.json`; two jobs never share
  a working directory and never race on `data.txt`. _Verify:_
  `tests/unit/test_workspace.py` (AC-MCP-031, AC-MCP-035).
- **SC2** — **Multi-topic out-of-the-box**: `POST /api/v1/research` and the
  `research_start` MCP tool accept `params.corpus` with `texts`
  (list of `{title, content}`) and/or `files` (paths relative to
  `RESEARCH_CORPUS_ROOT`); the job result carries `topic` and corpus stats;
  the contract's `train.py` (copied into the workspace) echoes topic + corpus
  in its output. _Verify:_
  `tests/unit/test_workspace.py` (AC-MCP-032..034),
  `tests/integration/test_multi_topic.py` (AC-MCP-231..232),
  `tests/e2e/service.bats` (AC-MCP-104).
- **SC3** — **Concurrent topics**: up to `RESEARCH_MAX_CONCURRENT_JOBS`
  (default 4) jobs run concurrently in one process; overlapping execution is
  proven at the unit tier and two topics complete concurrently over the live
  service. _Verify:_ `tests/unit/test_workspace.py` (AC-MCP-035..036),
  `tests/integration/test_multi_topic.py` (AC-MCP-231).
- **SC4** — **Async decision locked**: REST and MCP handlers remain **sync
  `def`** — FastAPI runs them on its threadpool and the research loop runs in
  APScheduler threads as subprocesses, so no handler blocks the event loop;
  a structural guard asserts no research handler is a coroutine (preventing a
  future refactor from moving `run_loop` inline). Rationale recorded in this
  PRD and in `service/README.md`. _Verify:_ `tests/unit/test_workspace.py`
  (AC-MCP-037), `service/README.md` review checklist.
- **SC5** — **Corpus files fail fast**: a missing corpus file is rejected at
  submit with a clear 400 (REST) / tool error (MCP), not discovered mid-run.
  _Verify:_ `tests/unit/test_workspace.py` (AC-MCP-033),
  `tests/integration/test_multi_topic.py` (AC-MCP-233).
- **SC6** — **Agent-facing runbook**: `service/README.md` exists as the
  service runbook template — what the service is, how to run it (uv +
  compose), env vars (including the three new ones), REST + MCP API, job
  lifecycle, concurrency + multi-topic model, workspace layout, security, and
  the convention that agents update it whenever service behaviour changes.
  _Verify:_ file exists with the required sections; referenced from
  `AGENTS.md` funnel table; `tests/unit/test_funnel_structure.py` allowlist
  still green (AC-FUN-001).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Per-job workspace isolation (scripts + topic.txt + context.json, disjoint dirs) | `tests/unit/test_workspace.py` | AC-MCP-031 |
| Corpus delivery: inline texts + files under corpus root | `tests/unit/test_workspace.py` | AC-MCP-032, AC-MCP-033 |
| Runner executes in workspace; report carries topic + corpus stats; legacy default unchanged (val_bpb 1.234) | `tests/unit/test_workspace.py` | AC-MCP-034 |
| Concurrent jobs overlap (wall < 2× single) + scheduler cap honors env | `tests/unit/test_workspace.py` | AC-MCP-035, AC-MCP-036 |
| All research handlers are sync def (async decision guard) | `tests/unit/test_workspace.py` | AC-MCP-037 |
| Two topics concurrently over live REST, distinct results | `tests/integration/test_multi_topic.py` | AC-MCP-231 |
| Corpus files from `kb/raw/transcripts` via corpus root | `tests/integration/test_multi_topic.py` | AC-MCP-232 |
| Missing corpus file → 400 fail-fast | `tests/integration/test_multi_topic.py` | AC-MCP-233 |
| Multi-topic loop in the container | `tests/e2e/service.bats` | AC-MCP-104 |

## Assumptions

- The workload source is the **canonical autoresearch contract** (`contract/`,
  bigram baseline, real `val_bpb` ≈ 3.7); it runs in milliseconds and is
  copied into every job workspace. The old vendored `service/workload/` copy
  was removed in the same window (single source of truth). `[ASSUMPTION]`
- Workspaces are retained after terminal jobs; a TTL/cleanup job is a
  documented upgrade path, not a v1 requirement. `[ASSUMPTION]`
- `RESEARCH_CORPUS_ROOT` defaults to `<repo>/kb/raw` on the host and `/kb-raw`
  in the compose container (read-only bind mount); the compose default is the
  out-of-the-box "research from `kb/raw/transcripts`" story. The container
  also mounts `./contract:/app/contract:ro` so per-job workspaces can copy the
  contract in-process. `[ASSUMPTION]`

## Confidence

**High** on concurrency architecture (threads + per-job subprocess workspaces;
matches the existing sandbox posture) and on corpus wiring (both paths are
unit-testable without a container). **Medium** on the exact APScheduler
executor wiring at `BackgroundScheduler(executors=...)` — guarded by
AC-MCP-036.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml` via `tests/run.sh`
(unit → integration → e2e; `secret-scan` + `doctrine` run independently).
No PR merges with a red test. `sources-readonly.yml` is unaffected (no
`kb/raw/` edits in this change).