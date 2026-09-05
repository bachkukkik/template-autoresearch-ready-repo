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

## Verification

```bash
# tiers 1+2 (no container)
python3 -m pytest tests/unit tests/integration -q   # 59 + 13 passed

# tier 3 (needs the stack up — run.sh does NOT start it)
docker compose up -d --build
docker compose ps --format '{{.Health}}' service    # healthy
bats tests/e2e/                                      # 3 ok
docker compose down

# everything (CI-shaped; install tests/requirements.txt into system python first)
bash tests/run.sh --with-e2e                         # RESULT: PASSED

# local CI (never -j e2e on a deployment host, AGENTS.md §6)
act push -j unit && act push -j integration && act push -j secret-scan && act push -j doctrine
```

Verified 2026-09-05: 66 unit + 16 integration + 4 e2e green (counts include
PRD-06 additions — see [docs/06-multi-topic-concurrency.md](06-multi-topic-concurrency.md));
all four act jobs succeeded; container healthy in ~8s.

## What Works

- Full job lifecycle over REST and over an MCP client: start → queued → running
  → completed with `result.val_bpb ≈ 3.795` (canonical contract loop, ~0.1s)
- Single source of truth: the service runs `contract/` directly — the runner
  resolves `repo/contract` on the host and `/app/contract` in the container via
  the compose read-only bind mount; no vendored workload copy. Custom workloads
  override via `RESEARCH_WORKLOAD_DIR` (or the legacy `service/workload` drop-in).
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
