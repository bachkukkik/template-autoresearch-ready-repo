# 05 — Dual REST + MCP service not implemented

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-04
**Resolved:** 2026-09-05

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md` | The service must serve REST (`/api/v1`) + MCP streamable HTTP (`/mcp`) from one ASGI app, non-duplicated handlers, SQLite/APScheduler job store, bearer auth, all under `service/` (SC1–SC8). |
| B | `service/src/main.py` (pre-PRD) | The service was a two-route stdlib HTTP stub (`/health`, `/`) — no REST research API, no MCP, no job store, no auth, no uv packaging. |

## Evidence

```bash
cat service/src/main.py   # was: routes /health and / only
ls service/               # was: Dockerfile, src/{__init__,main}.py only
```

## Impact

PRD-05 was entirely intent: consumers (agents via MCP, programs via REST) had no
surface to reach the autoresearch loop.

## Resolution

Code change + tests — `service/` rebuilt per PRD-05 (SC1–SC8) via delegated
build waves; verified 2026-09-05 in [docs/05-mcp-rest-service.md](../05-mcp-rest-service.md):
`bash tests/run.sh --with-e2e` → RESULT: PASSED (59 unit + 13 integration +
3 e2e), `act push -j unit|integration|secret-scan|doctrine` all green. Status
flipped to resolved; archive after merge.
