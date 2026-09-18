# 05 — AC-MCP-031..033 are claimed by two unit suites

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — test IDs renumbered, PRD-05 mapping added

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `tests/unit/test_auth.py:1` (before this sync) | "Unit tier — bearer auth core. IDs: AC-MCP-031..033" |
| B | `tests/unit/test_workspace.py:3` | "IDs: AC-MCP-031..037 — spec: docs/prd/06-multi-topic-concurrent-service.md" |
| B | `docs/prd/06-multi-topic-concurrent-service.md:52-56` (SC1) | AC-MCP-031 = per-job workspace isolation |

## Evidence

```bash
grep -rhoE "AC-MCP-03[0-9]" tests/ | sort | uniq -c
# 3 AC-MCP-031   (test_auth.py + test_workspace.py)
# 3 AC-MCP-032   (test_auth.py + test_workspace.py)
# 3 AC-MCP-033   (test_auth.py + test_workspace.py)
grep -rn "AC-MCP-03" docs/prd/
# docs/prd/06-multi-topic-concurrent-service.md: all 031..037 assigned to workspace/corpus tests
```

The workspace suite's ownership is published in PRD-06; the auth suite's IDs were
published nowhere — PRD-05 SC6 mapped auth to the integration block only
(AC-MCP-221..223).

## Impact

Two different behaviours answered to the same three IDs. A failing AC-MCP-031 gave
no way to tell whether job isolation or token verification broke, and the unit auth
tests — the only fail-closed coverage of `verify_token` and `AUTH_DISABLED` — were
traceable to no success criterion at all.

## Resolution

Code change + test — applied 2026-09-18: `tests/unit/test_auth.py` renumbered to
**AC-MCP-041..043** (docstring updated to say why), and PRD-05 SC6 plus its Test
Mapping table now name the unit auth block as the fail-closed core coverage.
`bash tests/run.sh` → `RESULT: PASSED`. **Status: resolved.**
