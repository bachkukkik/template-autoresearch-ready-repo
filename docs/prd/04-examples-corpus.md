# PRD 04 — Examples Corpus

> Intent for the "extensive examples to achieve objectives" deliverable: the
> ingested YouTube corpus + upstream program.md reference + research conclusions,
> synthesized into KB pages that humans and agents can follow.
> Grounded in: [autoresearch-video-corpus](../../kb/comparisons/autoresearch-video-corpus.md),
> [domain-adaptation](../../kb/concepts/domain-adaptation.md),
> [problem-selection](../../kb/concepts/problem-selection.md),
> [skill-self-improvement](../../kb/concepts/skill-self-improvement.md),
> [local-llm-controllers](../../kb/comparisons/local-llm-controllers.md).

## Context

The repo's second stated purpose (user goal, 2026-09-04 kickoff): *"this repo also
will provide extensive examples to achieve objectives."* Humans must understand
what to expect from the template; agents must understand what to do and follow
examples. The examples corpus is the empirical layer: 11 YouTube transcripts, the
upstream `program.md` reference, two deep-research conclusions articles, and the
CodeGraph MCP code-intelligence article — 15 raw sources, all ingested into
`kb/raw/` and synthesized into 21 `kb/` layer-2 pages.

**Target users:** humans reading the repo to set expectations; agents orienting in
`kb/` before acting. **Constraints:** raw sources are immutable (`kb/raw/` add-only);
synthesis pages are written only by llm-wiki; claims trace to raw sources via
wikilinks + `^[source]` footers.

## Success Criteria

- **SC1** — All 11 requested transcripts are ingested to `kb/raw/transcripts/` with
  valid frontmatter (`source_url`, `ingested`, `sha256`) and no sha drift.
  _Verify:_ `tests/unit/test_corpus_integrity.py` (AC-EXC-001..003). ✅ implemented 2026-09-04

- **SC2** — The upstream `program.md` reference, the two research-conclusions
  articles, and the CodeGraph MCP code-intelligence article are ingested to
  `kb/raw/articles/` (4 articles) with valid frontmatter and sha stamp.
  _Verify:_ `tests/unit/test_corpus_integrity.py` (AC-EXC-011). ✅ implemented 2026-09-04;
  article count refreshed 2026-09-18

- **SC3** — Layer-2 synthesis is complete and cataloged: 11 concepts, 4 entities,
  6 comparisons (21 pages in total), all listed in `kb/index.md`, no orphans, no
  broken wikilinks, all tags in the SCHEMA taxonomy. _Verify:_
  `tests/unit/test_kb_synthesis.py` (AC-EXC-021..024 — AC-EXC-021 asserts the
  lower bound `≥8/≥2/≥4`, so corpus growth never breaks CI). ✅ implemented
  2026-09-04; counts refreshed 2026-09-18

- **SC4** — Every layer-2 claim traces to a raw source (`sources:` frontmatter +
  `^[raw/...]` footers), so no assertion floats unsupported.
  _Verify:_ `tests/unit/test_kb_synthesis.py` (AC-EXC-024). ✅ implemented 2026-09-04

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Raw transcripts + articles frontmatter/sha valid | `tests/unit/test_corpus_integrity.py` | AC-EXC-001..003, AC-EXC-011 |
| Layer-2 pages complete, indexed, linked, tagged | `tests/unit/test_kb_synthesis.py` | AC-EXC-021..024 |
| Claims trace to raw sources | `tests/unit/test_kb_synthesis.py` | AC-EXC-024 |

## Assumptions

- The corpus is not frozen: the 2026-09-04 build plus the 2026-09-16 ingest /
  2026-09-18 synthesis of the CodeGraph article are the normative "examples"
  deliverable, and later ingests grow it without breaking CI (AC-EXC-021 is a
  lower bound). Deeper guided walkthroughs (per-example "how to follow this")
  are a future extension, not part of this PRD. `[ASSUMPTION]`
- The 11 transcripts cover the 6 requested videos + 5 playlist videos; the
  playlist itself is 9 videos and the remaining 4 are not ingested.
  `[ASSUMPTION]` — see [autoresearch-video-corpus](../../kb/comparisons/autoresearch-video-corpus.md).

## Confidence

**High** — the corpus is ingested and synthesized (re-verified 2026-09-18: 21/21
layer-2 pages indexed, no orphans, no broken wikilinks, all 15 raw sources
sha-verified in the working tree; the tracked corpus reads 14 raw / 18 pages
until the CodeGraph ingest is committed — see [docs/04](../04-examples-corpus.md))
and the `AC-EXC-*` tests now harden that verification inside the pytest tier.

## CI/CD Gate

The `sources-readonly.yml` job guards `kb/raw/**` on every PR; `secret-scan`
guards `kb/` content. The `AC-EXC-*` corpus-integrity tests run in the `unit`
job of `.github/workflows/ci.yml`. No PR merges with a red test.