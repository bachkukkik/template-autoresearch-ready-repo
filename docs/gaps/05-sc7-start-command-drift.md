# 05 — PRD-05 SC7 names a start command the image does not run

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — PRD edit applied; see [docs/05](../05-mcp-rest-service.md)

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md:66-70` (SC7) | "container starts with `uv run --locked uvicorn`" |
| B | `service/Dockerfile:27` | `CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]` |
| B | `docs/05-mcp-rest-service.md` *What Fails* → *Resolution* | a runtime `uv run --locked` re-syncs and can uninstall the uvicorn entrypoint mid-boot; the CMD therefore runs `--no-sync` |

## Evidence

```bash
grep -n "CMD" service/Dockerfile
# 27:CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
grep -n "uv sync\|uv run" service/Dockerfile
# 12:RUN uv sync --locked --no-install-project --no-editable
# 21:RUN uv sync --locked --no-editable
# 27:CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", ...]
```

`--locked` appears only at image-build time; the runtime command is `--no-sync`.

## Impact

An operator or agent following SC7 literally would reproduce the exact failure the
stage-6 doc records as fixed ("Failed to spawn: uvicorn", exit 2). The PRD also
contradicted the doc the same PRD points at for verified reality.

## Resolution

PRD edit — applied 2026-09-18: SC7 now states that the image installs with
`uv sync --locked` and the container starts with `uv run --no-sync --no-dev
uvicorn`, linking *What Fails* in [docs/05](../05-mcp-rest-service.md) for the
rationale. **Status: resolved.**
