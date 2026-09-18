# 05 — PRD-05 SC8 pointed at upgrade-path docs that did not exist

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — stage-6 doc updated via `coding-agents-docs-guideline`

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md:71-74` (SC8) | "upgrade paths (Postgres/BullMQ, hosted OAuth 2.1) documented in `docs/05-*`" |
| B | `docs/05-mcp-rest-service.md` (before this sync) | no occurrence of postgres, bullmq, oauth or upgrade anywhere in the doc |

## Evidence

```bash
grep -ni "postgres\|bullmq\|oauth\|upgrade" docs/05-mcp-rest-service.md
# (no output — before this sync)
```

SC8's only `_Verify:_` entries were an e2e test for the container
(AC-MCP-103) and "docs checklist in code review" — neither could fail when the
documentation was absent.

## Impact

The deployment-posture intent (v1 is batteries-included, the seams for the named
upgrades are local) was recorded only in stage 4, so the reader of stage 6 could not
find the upgrade story, and review had nothing concrete to check against. Intent
without a home downstream is exactly the divergence this stage records.

## Resolution

Stage-6 doc update — applied 2026-09-18 via `coding-agents-docs-guideline`:
`docs/05-mcp-rest-service.md` *How* gained an **Upgrade paths** sub-section — a
table pairing each v1 mechanism (SQLite job store, in-process scheduler, static
bearer auth, subprocess sandbox, retained workspaces) with its upgrade path
(Postgres, BullMQ/Celery, OAuth 2.1 IdP, Docker/WASM boundary, TTL sweeper) and the
seam that keeps the change local. PRD-05 SC8 now links that sub-section. **Status:
resolved.**
