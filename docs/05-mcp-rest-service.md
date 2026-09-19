# 05 — MCP REST Service

## What

A dual-exposure autoresearch service in `service/`: one ASGI app serving REST
under `/api/v1` and MCP streamable HTTP at `/mcp`, wrapping the autoresearch
contract loop (`prepare.py` → `train.py`, `val_bpb`, time budget) with a durable
job store, bearer auth, and a uv-managed container.

## Why

- The loop needs two consumers: programs (REST/OpenAPI) and agent harnesses +
  LiteLLM (MCP tools) — PRD-05 SC1.
- Non-duplicated handler syntax: each operation is defined once and flagged into
  MCP via `TOOL_FLAG` — an endpoint is a tool or not by one boolean.
- Batteries-included posture: `docker compose up` works with zero external infra
  (SQLite job store, auth disabled by default for dev).

## How

| Component | File | Notes |
|-----------|------|-------|
| FastAPI app + FastMCP mount | `service/src/main.py` | `TOOL_FLAG`, `ROUTE_TO_OPERATION`, `_BearerGuard` on `/mcp`, APScheduler in lifespan |
| Job store | `service/src/jobs.py` | SQLite WAL, idempotency keys, transitions `queued→running→completed\|failed\|cancelled\|timeout` |
| Runner | `service/src/runner.py` | executes the canonical contract at `contract/` directly (prepare.py then train.py), explicit args, timeout; parses `val_bpb` from the summary line (`val_bpb: 3.795531`) or legacy `RESULT val_bpb=`; workload dir resolved via `RESEARCH_WORKLOAD_DIR` → `repo/contract` (dev) → `/app/contract` (compose ro mount) |
| Auth | `service/src/auth.py` | `hmac.compare_digest`, fail-closed, `AUTH_DISABLED=1` opt-out, `/health` open |
| Packaging | `service/pyproject.toml`, `service/uv.lock` | fastapi, uvicorn, fastmcp 4.x, apscheduler, pydantic |
| Image | `service/Dockerfile`, `service/.dockerignore` | pinned `ghcr.io/astral-sh/uv:0.12.9`, two-stage `uv sync`, venv binary CMD |
| Env | `.env.example`, compose passthrough | `AUTH_BEARER_TOKEN`, `AUTH_DISABLED`, `RESEARCH_JOBS_DB`, `RESEARCH_RUN_TIMEOUT` |

REST surface: `GET /health` (no auth), `POST /api/v1/research` (202 + job),
`GET /api/v1/research/{id}`, `GET /api/v1/research/{id}/results`,
`DELETE /api/v1/research/{id}`. MCP tools: `research_start`, `research_status`,
`research_results`, `research_cancel` at `/mcp` (FastMCP v4 streamable HTTP,
stateless 2026-07-28 path).

### Upgrade paths

None of the upgrades below are implemented — v1 is the batteries-included
posture. Each names the seam that keeps the upgrade local (PRD-05 SC8).

| Area | v1 (implemented) | Upgrade path | Seam |
|------|------------------|--------------|------|
| Job durability | SQLite WAL file via `RESEARCH_JOBS_DB` (`service/src/jobs.py`) | Postgres — same table shape, swap the connection + DDL | `JobStore` is the only writer of job rows; handlers call it, never SQL directly |
| Scheduling | `BackgroundScheduler` in-process, `ThreadPoolExecutor(max_workers=RESEARCH_MAX_CONCURRENT_JOBS)` | BullMQ / Celery / an external queue worker | `_run_job` is the single dispatch entry point; the scheduler only calls it |
| Auth | Static bearer token, `hmac.compare_digest`, fail-closed (`service/src/auth.py`) | OAuth 2.1 via a hosted IdP (FastMCP MultiAuth); per-sender keys | `require_bearer` is the one FastAPI dependency; `/health` stays outside it |
| Loop sandbox | Subprocess (`prepare.py` → `train.py`), explicit argv, always a timeout, per-job cwd | Docker/WASM boundary with read-only fs, egress allowlist, cpu/memory budget | `ResearchRunner.run_loop` owns process creation; no handler spawns processes |
| Workspace lifetime | Workspaces retained under `data/workspaces/` after terminal jobs | TTL sweeper over `data/workspaces/` | Provisioner + runner address workspaces by `job_id` path only |

## Verification

```bash
# tiers 1+2 (no container)
python3 -m pytest tests/unit tests/integration -q   # 68 + 16 passed (2026-09-18)

# tier 3 (needs the stack up — run.sh does NOT start it)
docker compose up -d --build
docker compose ps --format '{{.Health}}' service    # healthy
bats tests/e2e/                                      # 4 ok
docker compose down

# everything (CI-shaped; install tests/requirements.txt into system python first)
bash tests/run.sh --with-e2e                         # RESULT: PASSED

# local CI — run the pre-PR chain stated in AGENTS.md §6
# (never -j e2e on a deployment host)
```

Verified 2026-09-18: 68 unit + 16 integration + 4 e2e green
(`bash tests/run.sh --with-e2e` → `RESULT: PASSED`), all four act jobs report
`Job succeeded` — verified with (as of this run): `act push -j unit && act push
-j integration && act push -j secret-scan && act push -j doctrine`; container
healthy under `docker compose ps`; the unit count grew from 66 by the
runbook-coverage test added with the PRD-06 SC6 fix — see
[docs/06-multi-topic-concurrency.md](06-multi-topic-concurrency.md).
Originally verified 2026-09-05 at 66 + 16 + 4.

## What Works

- Full job lifecycle over REST and over an MCP client: start → queued → running
  → completed with `result.val_bpb ≈ 3.795` (canonical contract loop, ~0.1s)
- Single source of truth: the service runs `contract/` directly — the runner
  resolves `repo/contract` on the host and `/app/contract` in the container via
  the compose read-only bind mount; no vendored workload copy. Custom workloads
  override via `RESEARCH_WORKLOAD_DIR`; `resolve_workload_dir()` otherwise falls
  back to `<service-root>/workload`, a directory this repo does not ship.
- Idempotent dispatch (same `idempotency_key` returns the existing job)
- Cancel on queued and running jobs (queued→cancelled added, AC-MCP-014)
- Bearer auth on REST and the `/mcp` guard: 401 + complete JSON body when
  unauthenticated; `AUTH_DISABLED=1` for dev
- Container boots healthy with `uv run --no-sync` after two-stage `uv sync`
- `tools/list` over the stateless JSON-RPC path names all four tools

## What Fails

- **run.sh does not start the stack:** `bash tests/run.sh --with-e2e` fails the
  e2e tier with "service is not running" unless compose is up first.
- **Host venv poisons the image:** without `service/.dockerignore`, `COPY . .`
  ships the host `.venv` whose scripts carry host-path shebangs; `uv run
  uvicorn` then cannot spawn ("Failed to spawn: uvicorn", exit 2).
- **Runtime `uv run --locked` re-syncs:** it can uninstall/restore the project
  mid-boot; non-deterministic startup.
- **e2e under act:** running `act push -j e2e` on a host that serves this
  compose project replaces the live containers (AGENTS.md §6) — run the tier
  directly instead.

## Resolution

- **run.sh stack:** start compose first (`docker compose up -d --build`) or run
  tiers separately; CI's e2e job already starts the stack itself.
- **Host venv:** `service/.dockerignore` excludes `.venv`, `data`,
  `__pycache__` — keep it when adding build-context content.
- **Re-sync at boot:** CMD runs the venv binary via `uv run --no-sync --no-dev`;
  the image's final `uv sync --locked --no-editable` is the single source.
- **act e2e:** unchanged policy — local jobs are unit/integration/secret-scan/
  doctrine only.

## Verdict

**works** — all three tiers and all four local CI jobs are green as of
2026-09-05; the service exposes the autoresearch loop over both REST and MCP
from one process. Remote CI on the PR is the remaining gate (this doc records
local verification only).
