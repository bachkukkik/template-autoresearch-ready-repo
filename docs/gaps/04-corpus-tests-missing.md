# 04 — Corpus-integrity tests do not exist in the pytest tier

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-09-04

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/04-examples-corpus.md:27-34` | SC1–SC4 verify `tests/unit/test_corpus_integrity.py` and `test_kb_synthesis.py` (AC-EXC-*) |
| B | `tests/unit/` | Only `test_routing.py` (AC-EXM-*) exists; no AC-EXC-* tests |

## Evidence

```
$ ls tests/unit/
test_routing.py
```

## Impact

The corpus was verified once (2026-09-04 build: 14/14 pages indexed, no orphans,
sha-verified raw sources) but that verification was a one-off script run, not a
repeatable test. Nothing in CI re-checks raw-source sha drift, index
completeness, wikilink integrity, or tag taxonomy on future PRs — the add-only
gate (`sources-readonly.yml`) covers file edit/delete, not content drift.

## Resolution

Code change + test — next implementation run authors `tests/unit/test_corpus_integrity.py`
and `test_kb_synthesis.py` per the AC-EXC-* IDs in `docs/prd/04`. The 2026-09-04
verification scripts in `scratchpads/autoresearch-research/` are the reference
implementation for these tests. Tracked with gaps `02`, `03` in the same run.