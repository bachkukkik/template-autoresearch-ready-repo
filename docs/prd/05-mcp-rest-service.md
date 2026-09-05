# PRD 05 — REST + Streamable-HTTP MCP Service for the Autoresearch Loop

> Intent for the service layer: expose the autoresearch loop as **RESTful APIs**
> and as **streamable-HTTP MCP tools** from one process, with a batteries-included
> deployment posture and the whole install+run surface self-contained in
> `service/`.
> Grounded in: [mcp-streamable-http-transport](../../kb/concepts/mcp-streamable-http-transport.md),
> [research-job-pattern](../../kb/concepts/research-job-pattern.md),
> [fastmcp](../../kb/entities/fastmcp.md),
> [rest-vs-mcp-dual-exposure](../../kb/comparisons/rest-vs-mcp-dual-exposure.md),
> [autoresearch-contract](../../kb/concepts/autoresearch-contract.md).

## Context

The repo ships the autoresearch contract (`program.md` / `prepare.py` / `train.py`,
fixed-time budget, `val_bpb`, keep/discard) as its core deliverable. The user
wants that loop consumed two ways: **by programs over REST** and **by agents over
MCP streamable HTTP** ("the same service as streamable, http-able MCP tools").
Deep research (2026-09-04, conclusions in
[kb/raw/articles/mcp-autoresearch-service-conclusions.md](../../kb/raw/articles/mcp-autoresearch-service-conclusions.md))
settled the shape: dual exposure of one core, no duplicated handler syntax.

**Users:** a human researcher / operator (REST, OpenAPI, admin), and agent
harnesses + LiteLLM gateway (MCP). **Constraints:** all code + build logic lives
in `service/` (Docker build context = `service/`); production-managed with `uv`
(`uv.lock`, `uv run --locked uvicorn`); `docker compose up` delivers a working
service with zero external infra.

**Decided posture (user, 2026-09-04):** batteries-included MVP — REST + MCP +
job-id/poll over SQLite/APScheduler + bearer auth + `/health`; documented upgrade
paths to Postgres/BullMQ and a hosted OAuth IdP; Docker/WASM sandboxed loop
execution; security stack introduced fully.

## Success Criteria

- **SC1** — One ASGI app serves **REST** under `/api/v1` and **MCP streamable
  HTTP** under `/mcp` from the same FastAPI/FastMCP process, with **non-duplicated
  handler syntax**: each API endpoint declares whether it is also an MCP tool
  (per-endpoint tool flag), and a handler defined once is reachable as both an
  HTTP route and an MCP tool. _Verify:_ `tests/unit/test_routes.py`
  (AC-MCP-001), `tests/integration/test_mcp_endpoints.py` (AC-MCP-201),
  `tests/integration/test_service_endpoints.py` (AC-MCP-211).
- **SC2** — REST surface: `POST /api/v1/research` (kickoff, returns `job_id`),
  `GET /api/v1/research/{job_id}` (status + results when `completed`),
  `DELETE /api/v1/research/{job_id}` (cancel), `GET /health`; OpenAPI schema
  published at `/openapi.json`. _Verify:_ `tests/integration/test_service_endpoints.py`
  (AC-MCP-211..214), `tests/unit/test_routes.py` (AC-MCP-004..006).
- **SC3** — MCP surface: tools `research_start`, `research_status`,
  `research_results`, `research_cancel` are callable over a streamable-HTTP
  client; a `research_start` call returns a job id immediately and
  `research_status` returns terminal results afterwards (job-id/poll pattern).
  _Verify:_ `tests/integration/test_mcp_endpoints.py` (AC-MCP-201..205).
- **SC4** — Jobs are durable: job-id/poll backed by a **SQLite store via
  APScheduler in-process**, surviving a service restart; dispatch is idempotent
  via an explicit `idempotency_key`. _Verify:_ `tests/unit/test_job_store.py`
  (AC-MCP-011..013), `tests/integration/test_service_endpoints.py` (AC-MCP-215).
- **SC5** — Long-running loop execution is **sandboxed**: the research runner
  executes inside a Docker/WASM sandbox boundary (read-only fs, egress
  allowlist, time/cpu/memory budgets) by default; an unsafe free-form
  code-exec tool is NOT exposed over MCP. _Verify:_ `tests/unit/test_runner.py`
  (AC-MCP-021..023).
- **SC6** — Auth: bearer token required on REST and MCP (FastMCP MultiAuth /
  `Authorization: Bearer`), configurable via env; unauthenticated requests get
  401; `/health` stays unauthenticated by design (FastMCP custom route).
  _Verify:_ `tests/integration/test_auth.py` (AC-MCP-221..223).
- **SC7** — The service is `uv`-managed and the whole surface lives in
  `service/`: `pyproject.toml` + `uv.lock` + `Dockerfile` + sources all under
  `service/`; container starts with `uv run --locked uvicorn`; `docker compose
  up -d --build` yields a healthy container. _Verify:_
  `tests/e2e/service.bats` (AC-MCP-101..103).
- **SC8** — Deployment posture: no external infra required (SQLite + APScheduler
  in-process); upgrade paths (Postgres/BullMQ, hosted OAuth 2.1) documented in
  `docs/05-*`. _Verify:_ `tests/e2e/service.bats` (AC-MCP-103),
  docs checklist in code review.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Dual exposure — one handler, REST + MCP tool | `tests/unit/test_routes.py`, `tests/integration/test_mcp_endpoints.py`, `tests/integration/test_service_endpoints.py` | AC-MCP-001, AC-MCP-201, AC-MCP-211 |
| REST kickoff/status/cancel/health | `tests/integration/test_service_endpoints.py` | AC-MCP-211..214 |
| MCP tools over streamable HTTP | `tests/integration/test_mcp_endpoints.py` | AC-MCP-201..205 |
| Durable SQLite job store + idempotency | `tests/unit/test_job_store.py`, `tests/integration/test_service_endpoints.py` | AC-MCP-011..013, AC-MCP-215 |
| Sandboxed runner, no code-exec tool | `tests/unit/test_runner.py` | AC-MCP-021..023 |
| Bearer auth on REST + MCP, /health open | `tests/integration/test_auth.py` | AC-MCP-221..223 |
| uv-managed container healthy via compose | `tests/e2e/service.bats` | AC-MCP-101..103 |

## Assumptions

- The autoresearch loop runner in v1 is a **bounded reference runner** (a
  CPU-friendly, time-boxed training/eval loop with a `val_bpb`-style metric)
  that exercises the full contract; swapping in a real `train.py`/`prepare.py`
  pair must not change the service API. `[ASSUMPTION]`
- `fastmcp` v4's `from_fastapi`/RouteMap mechanism is present in the pinned
  version; if unavailable, fall back to official `mcp` SDK 2.x with hand-written
  tools — SC3 still holds. `[ASSUMPTION]`
- Bearer auth (FastMCP MultiAuth / static key) is the launch auth; OAuth 2.1
  via hosted IdP is the documented upgrade, not a v1 requirement. `[ASSUMPTION]`

## Confidence

**High** on architecture (grounded in KB pages synthesized from 10-snapshot
deep research); **medium** on the exact FastMCP v4 API surface (version drift —
guarded by SC3's fallback assumption).

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml` via `tests/run.sh`
(unit → integration → e2e; `secret-scan` + `doctrine` run independently).
No PR merges with a red test. The `sources-readonly.yml` gate protects `kb/raw/`
for the ingested conclusions article.