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
upstream `program.md` reference, and the deep-research conclusions, all ingested
into `kb/raw/` and synthesized into `kb/` layer-2 pages.

**Target users:** humans reading the repo to set expectations; agents orienting in
`kb/` before acting. **Constraints:** raw sources are immutable (`kb/raw/` add-only);
synthesis pages are written only by llm-wiki; claims trace to raw sources via
wikilinks + `^[source]` footers.

## Success Criteria

- **SC1** — All 11 requested transcripts are ingested to `kb/raw/transcripts/` with
  valid frontmatter (`source_url`, `ingested`, `sha256`) and no sha drift.
  _Verify:_ `tests/unit/test_corpus_integrity.py` (AC-EXC-001..003). `[PLANNED]`

- **SC2** — The upstream `program.md` reference and the research-conclusions
  article are ingested to `kb/raw/articles/` with valid frontmatter and sha stamp.
  _Verify:_ `tests/unit/test_corpus_integrity.py` (AC-EXC-011). `[PLANNED]`

- **SC3** — Layer-2 synthesis is complete and cataloged: 8 concepts, 2 entities, 4
  comparisons, all listed in `kb/index.md`, no orphans, no broken wikilinks, all
  tags in the SCHEMA taxonomy. _Verify:_ `tests/unit/test_kb_synthesis.py`
  (AC-EXC-021..023). `[PLANNED]`

- **SC4** — Every layer-2 claim traces to a raw source (`sources:` frontmatter +
  `^[raw/...]` footers), so no assertion floats unsupported.
  _Verify:_ `tests/unit/test_kb_synthesis.py` (AC-EXC-024). `[PLANNED]`

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Raw transcripts + articles frontmatter/sha valid | `tests/unit/test_corpus_integrity.py` | AC-EXC-001..003, AC-EXC-011 |
| Layer-2 pages complete, indexed, linked, tagged | `tests/unit/test_kb_synthesis.py` | AC-EXC-021..024 |
| Claims trace to raw sources | `tests/unit/test_kb_synthesis.py` | AC-EXC-024 |

## Assumptions

- The corpus as ingested in the 2026-09-04 build is the normative "examples"
  deliverable; deeper guided walkthroughs (per-example "how to follow this")
  are a future extension, not part of this PRD. `[ASSUMPTION]`
- The 11 transcripts cover the 6 requested videos + 5 playlist videos; the
  playlist itself is 9 videos and the remaining 4 are not ingested.
  `[ASSUMPTION]` — see [autoresearch-video-corpus](../../kb/comparisons/autoresearch-video-corpus.md).

## Confidence

**High** — the corpus is already ingested and synthesized (verified 2026-09-04:
14/14 pages indexed, no orphans, no broken wikilinks, all 13 raw sources
sha-verified). The `[PLANNED]` tests harden that verification inside the pytest
tier.

## CI/CD Gate

The `sources-readonly.yml` job guards `kb/raw/**` on every PR; `secret-scan`
guards `kb/` content. When the `[PLANNED]` corpus-integrity tests are written they
join the `unit` job in `.github/workflows/ci.yml`. No PR merges with a red test.