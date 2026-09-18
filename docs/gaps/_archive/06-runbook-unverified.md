# 06 — The runbook PRD-06 SC6 mandates is verified by no test

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — test added, PRD-06 SC6 now names it

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/06-multi-topic-concurrent-service.md:82-89` (SC6) | `service/README.md` must carry what the service is, how to run it (uv + compose), the env vars (including the three new ones), the REST + MCP API, the job lifecycle, the concurrency/multi-topic model, the workspace layout, security, and the update convention |
| B | `tests/` (before this sync) | no test reads `service/README.md` |
| B | `docs/prd/06` SC6 `_Verify:_` (before this sync) | "file exists with the required sections; … `test_funnel_structure.py` allowlist still green (AC-FUN-001)" — AC-FUN-001 only asserts no stray root-level `.md`, which cannot fail when a runbook section disappears |

## Evidence

```bash
grep -rn "README" tests/
# tests/unit/test_funnel_structure.py:10  ROOT_MD_ALLOWLIST = {"AGENTS.md", "README.md", "PRD.md"}
# tests/unit/test_kb_layout.py:11        RAW_TOP_ALLOWLIST = {"README.md", "SCHEMA.md"}
# tests/unit/test_gaps_lifecycle.py:13   readme = gaps_dir / "README.md"
grep -rn "service/README" tests/
# (no output)
```

Related rot found while writing the missing test: `service/README.md:16` cited
`../../program.md`, a path that no longer exists (the contract moved to
`contract/program.md`). Fixed in the same sync — that file now points at
`../contract/program.md`. It sits outside what the new test asserts, so no test
guards it.

## Impact

SC6's whole content list was review-verified only. The runbook could lose its env
table, its job-lifecycle diagram or its workspace layout — all machine-checkable —
and every tier would stay green, which is the failure mode the PRD's own
verification policy ("every SC carries a `_Verify:` test") exists to prevent.

## Resolution

Code change + test — applied 2026-09-18: `tests/unit/test_service_readme.py` added
(**AC-MCP-044** — file exists and declares itself a runbook; **AC-MCP-045** — every
SC6 section and the three PRD-06 env vars are present). PRD-06 SC6 now names that
file. `bash tests/run.sh` → `RESULT: PASSED` (68 unit). **Status: resolved.**
