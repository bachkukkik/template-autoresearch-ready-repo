# 04 — Examples Corpus

## What

The examples deliverable: 13 immutable raw sources in `kb/raw/` (11 YouTube
transcripts of autoresearch-in-practice + 2 articles: upstream `program.md`
reference + the deep-research conclusions) and 14 synthesized layer-2 pages in
`kb/` (8 concepts, 2 entities, 4 comparisons), with integrity tests that keep the
corpus trustworthy.

## Why

The repo's second stated purpose: *"extensive examples to achieve objectives."*
Humans must set expectations from the template; agents must orient in `kb/`
before acting. Raw sources are immutable (add-only) and layer-2 pages are
llm-wiki-written — so the corpus needs machine-checked integrity (sha256 stamps,
index coverage, wikilink resolution, tag taxonomy) rather than trust
(PRD 04, grounded in `kb/comparisons/autoresearch-video-corpus.md`).

## How

- **Raw sources (`kb/raw/`):** `transcripts/*.txt` (11) and `articles/*.md` (2),
  each with YAML frontmatter `source_url` (http(s)), `ingested` (ISO date),
  `sha256` over `body.strip()` (the STRIP convention used at ingest). Add-only,
  enforced by `sources-readonly.yml`.
- **Layer-2 pages (`kb/`):** 8 concepts, 2 entities, 4 comparisons — each with
  `sources:` frontmatter pointing to raw paths, `^[raw/...]` footers, tags from
  the SCHEMA taxonomy, and wikilinks to sibling pages.
- **Integrity tests (new):** `test_corpus_integrity.py` (AC-EXC-001..003, 011 —
  every raw file's frontmatter/keys/sha; counts ≥11 transcripts / ≥2 articles;
  value shape) and `test_kb_synthesis.py` (AC-EXC-021..024 — page counts,
  index coverage/no orphans, wikilink resolution, sources/tag traceability).

## Verification

```bash
python3 -m pytest tests/unit/test_corpus_integrity.py tests/unit/test_kb_synthesis.py -v
# 8 passed (AC-EXC-001..003, 011, 021..024); full unit tier 34 passed
```

The corpus tests are read-only, stdlib-only, and fast — they run on every CI
`unit` job, so a sha drift or a new orphaned page fails the PR.

## What Works

- All 13 raw sources sha-verified against the STRIP convention (verified 2026-09-04
  both at ingest and by the tests).
- All 14 layer-2 pages indexed in `kb/index.md`; no orphans; no broken wikilinks;
  every page traces to `raw/`; all tags are in the SCHEMA taxonomy.
- Count checks are lower-bounded (≥) so the corpus can grow without breaking CI.
- The tests catch real drift: during verification they flagged a concurrently
  ingested `kb/raw/articles/mcp-autoresearch-service-conclusions.md` whose sha256
  stamp mismatched its body — the gate worked as designed.

## What Fails

- **Concurrent-ingest sha drift:** a raw file added by a parallel research wave
  (`mcp-autoresearch-service-conclusions.md`, untracked) carries a sha256 stamp
  that does not match its body, so `AC-EXC-002` fails while that file sits in the
  working tree. The gate is behaving correctly; the file's owner must re-stamp
  the sha (or re-ingest) before committing it.
- **Not a content checker:** the tests verify integrity (stamps, links, tags),
  not the accuracy of the synthesized claims — claim correctness still comes
  from the llm-wiki workflow + the `sources:` traceability.

## Resolution

- **Concurrent-ingest sha drift:** re-record `sha256: <sha256(body.strip())>` in
  the file's frontmatter (or move it to `kb/_archive/` and re-ingest). This is a
  one-line metadata fix on an untracked file; do it before any PR that carries
  the file.
- **Not a content checker:** by design — keep claim review in the llm-wiki
  stage; AC-EXC-024 verifies traceability, which is what makes review possible.

## Verdict

**works** — the corpus is ingested, synthesized, cataloged, and now machine-gated:
8 integrity tests pass on the committed corpus and catch real sha drift. One
uncommitted, concurrently-ingested file has a stale sha stamp that must be fixed by
its owning workstream before it is committed.