# 04 — Corpus-integrity tests do not exist in the pytest tier

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-04
**Resolved:** 2026-09-04 — AC-EXC-* tests implemented; see [docs/04](../04-examples-corpus.md)

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

Code change + test — **DONE 2026-09-04**: `tests/unit/test_corpus_integrity.py`
and `test_kb_synthesis.py` ship with the AC-EXC-* IDs in `docs/prd/04`; all pass
and run in the CI `unit` job (the 2026-09-04 verification scripts in
`scratchpads/autoresearch-research/` were the reference implementation). Verified
in [docs/04-examples-corpus.md](../04-examples-corpus.md).