# 04 — PRD-04 records stale corpus counts

**Layers:** kb ↔ prd
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — PRD edit applied; see [docs/04](../04-examples-corpus.md)

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `kb/concepts/` × 11, `kb/entities/` × 4, `kb/comparisons/` × 6; `kb/raw/` = 11 transcripts + 4 articles | The KB holds **21** layer-2 pages and **15** raw sources (the CodeGraph ingest landed 2026-09-16, synthesized 2026-09-18) |
| B | `docs/prd/04-examples-corpus.md:36` (SC3) | "Layer-2 synthesis is complete and cataloged: 8 concepts, 2 entities, 4 comparisons" |
| B | `docs/prd/04-examples-corpus.md:64-66` (Confidence) | "verified 2026-09-04: 14/14 pages indexed, no orphans, no broken wikilinks, all 13 raw sources sha-verified" |

## Evidence

```bash
for d in concepts entities comparisons queries; do echo "$d $(ls kb/$d/*.md | wc -l)"; done
# concepts 11, entities 4, comparisons 6, queries 0
ls kb/raw/transcripts/*.txt | wc -l && ls kb/raw/articles/*.md | wc -l
# 11 / 4
python3 -m pytest tests/unit/test_kb_synthesis.py tests/unit/test_corpus_integrity.py -q
# 8 passed  (AC-EXC-021 asserts the floor ≥8/≥2/≥4; AC-EXC-001/002 sha-verify all 15 raw files)
```

The floor test is why this drift survived: AC-EXC-021 passes at 8/2/4, so nothing
in CI forces the PRD's recorded counts back in line with the KB.

## Impact

Stage 4 understated the corpus it governs by seven pages and two raw sources. A
reader of SC3 could not tell whether the CodeGraph pages were sanctioned output or
unreviewed drift, and the Confidence paragraph asserted a 14-page / 13-source state
that no longer exists — the grounding direction (KB → PRD) was stale in the
direction that matters for review.

## Resolution

PRD edit — applied 2026-09-18: SC2 now names 4 articles, SC3 records 11/4/6 (21
pages) and documents that AC-EXC-021 is a lower bound, Confidence cites the
2026-09-18 state (21/21 pages, 15 raw sha-verified, tracked corpus 14/18 until the
CodeGraph ingest is committed), and the Assumptions note the corpus is not frozen.
**Status: resolved.**
