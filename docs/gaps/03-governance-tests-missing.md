# 03 — Funnel/KB governance unit tests do not exist in the pytest tier

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-09-04

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
documented in `AGENTS.md` + CI (`doctrine`, `sources-readonly` jobs) but are not
hardened in the pytest tier. A regression in those rules would not be caught by
the three-tier suite until CI's structural jobs run, and the `[PLANNED]` SCs
cannot be verified.

## Resolution

Code change + test — next implementation run authors `tests/unit/test_funnel_structure.py`,
`test_kb_layout.py`, `test_gaps_lifecycle.py` per the AC-FUN-* IDs in
`docs/prd/03`. Legal per `AGENTS.md` §5: the governance rules are real behaviour
(the CI jobs already encode them); the pytest tier makes them first-class.
Tracked with gap `02` in the same implementation run.