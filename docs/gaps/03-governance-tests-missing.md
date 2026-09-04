# 03 — Funnel/KB governance unit tests do not exist in the pytest tier

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-04
**Resolved:** 2026-09-04 — AC-FUN-* tests implemented; see [docs/03](../03-funnel-kb-governance.md)

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/03-funnel-kb-governance.md:24-33` | SC1, SC4, SC5 verify `tests/unit/test_funnel_structure.py`, `test_kb_layout.py`, `test_gaps_lifecycle.py` (AC-FUN-*) |
| B | `tests/unit/` | Only `test_routing.py` (AC-EXM-*) exists; no AC-FUN-* tests |

## Evidence

```
$ ls tests/unit/
test_routing.py
```

## Impact

The governance rules (no stray docs, llm-wiki-only KB writes, gap lifecycle) are
documented in `AGENTS.md` + CI (`doctrine`, `sources-readonly` jobs) but were not
hardened in the pytest tier. A regression in those rules would not be caught by
the three-tier suite until CI's structural jobs run, and the `[PLANNED]` SCs could
not be verified.

## Resolution

Code change + test — **DONE 2026-09-04**: `tests/unit/test_funnel_structure.py`,
`test_kb_layout.py`, `test_gaps_lifecycle.py` ship with the AC-FUN-* IDs in
`docs/prd/03`; all pass and run in the CI `unit` job. Verified in
[docs/03-funnel-kb-governance.md](../03-funnel-kb-governance.md).