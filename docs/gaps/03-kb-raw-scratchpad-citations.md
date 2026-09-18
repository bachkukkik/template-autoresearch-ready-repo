# 03 — kb/raw articles cite scratchpad paths as their evidence

**Layers:** kb ↔ prd
**Status:** open
**Opened:** 2026-09-18

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `kb/raw/articles/mcp-autoresearch-service-conclusions.md:2` | provenance frontmatter routes the reader to `scratchpads/mcp-autoresearch-mcp/results/*.json` for the per-item source list |
| A | `kb/raw/articles/mcp-autoresearch-service-conclusions.md:15` | the synthesis blockquote places the research artifacts (outline, `fields.yaml`, 10 per-item JSON snapshots, `report.md`) in `scratchpads/mcp-autoresearch-mcp/` "(gitignored)" |
| A | `kb/raw/articles/autoresearch-template-research-conclusions.md:2` | provenance frontmatter routes the reader to `scratchpads/autoresearch-research/` for the artifacts |
| A | `kb/raw/articles/autoresearch-template-research-conclusions.md:15` | the synthesis blockquote places structured results, per-item snapshots and raw notes in `scratchpads/autoresearch-research/` "(gitignored)" |
| B | `AGENTS.md:103-104` (funnel rule 6) | "**`scratchpads/` is never cited.** No tracked document may reference a scratchpad path as evidence — promote the content to `kb/raw/` first." |

The README admits only two gap kinds and neither fits a stage-2-vs-doctrine divergence;
`kb ↔ prd` is used here in the sense of *KB material against the tracked intent that
governs it* (rule 6 in `AGENTS.md`, the stage-4-side authority for provenance). There is
no code side, so `prd ↔ code` does not apply.

Not a violation in the same grep: `kb/raw/articles/autoresearch-template-research-conclusions.md:94`
(`"document funnel: scratchpads → kb/raw → kb → PRD → gaps → docs/NN → issues"`) names the
funnel stages as an analogy for the upstream keep/discard loop. It cites no scratchpad path
as evidence, so it is reported here only to show the grep was read in full.

## Evidence

```bash
git grep -n "scratchpads/" -- kb/raw/
# kb/raw/articles/autoresearch-template-research-conclusions.md:2:source_url: https://github.com/karpathy/autoresearch (research synthesis: upstream repo + 11 YouTube transcripts + bachkukkik doctrine; artifacts in scratchpads/autoresearch-research/)
# kb/raw/articles/autoresearch-template-research-conclusions.md:15:> `scratchpads/autoresearch-research/` (gitignored). Raw sources ingested here:
# kb/raw/articles/mcp-autoresearch-service-conclusions.md:2:source_url: https://modelcontextprotocol.io (spec + SDK docs, registries, FastMCP docs; full source list per item in scratchpads/mcp-autoresearch-mcp/results/*.json)
# kb/raw/articles/mcp-autoresearch-service-conclusions.md:15:> report.md) live in `scratchpads/mcp-autoresearch-mcp/` (gitignored).

grep -n "never cited" -A2 AGENTS.md
# 103:6. **`scratchpads/` is never cited.** No tracked document may reference a scratchpad
# 104-   path as evidence — promote the content to `kb/raw/` first.

git ls-files -- scratchpads/
# scratchpads/.gitkeep

git check-ignore -v scratchpads/autoresearch-research/README.md scratchpads/mcp-autoresearch-mcp
# .gitignore:65:scratchpads/*	scratchpads/autoresearch-research/README.md
# .gitignore:65:scratchpads/*	scratchpads/mcp-autoresearch-mcp

git ls-files --others --ignored --exclude-standard -- scratchpads/autoresearch-research scratchpads/mcp-autoresearch-mcp | wc -l
# 39
```

Both cited files are tracked stage-2 raw sources (ingested 2026-09-04, frontmatter
`ingested:`), so rule 6 binds them.

## Impact

`scratchpads/` is gitignored and deletable at any time (funnel stage 1), so on a fresh
clone both provenance links resolve to nothing: the repo tracks only `scratchpads/.gitkeep`,
`.gitignore:65` (`scratchpads/*`) hides the two directories and the 39 files inside them, so
a clone neither has the artifacts nor can verify that they ever existed. The two articles are
syntheses, not primaries: a reader following their provenance to check a claim is sent to a
path that cannot exist in a clone, which is exactly the failure rule 6 was written against,
and it is the case that matters most for the article whose sources are per-item JSON
snapshots that were never promoted into `kb/raw/`.

`kb/raw/` is add-only (funnel rule 3, CI `sources-readonly.yml`), so the defect cannot be
edited out in place — an in-place edit would breach the add-only gate, and leaving it means
every clone ships a dangling provenance link in stage-2 material.

## Resolution

`kb/raw/` ingest + `llm-wiki ./kb/` — archive the two raw files out to
`kb/_archive/raw/articles/` (funnel rule 5: archive, never delete), re-ingest corrected
copies whose provenance points at the ingested `kb/raw/` material instead of
`scratchpads/`, then run `llm-wiki ./kb/` so the layer-2 pages that cite them are
re-synthesized from the corrected provenance. That is the only closure that fixes the
tracked text; note it costs a manual hash re-record for the new raw files that the
corpus tests (`AC-EXC-001/002`) sha-verify.

Alternative if the re-ingest is not scheduled now: a GitHub issue #N, with the file left
pointing at it. Not applied in this sync: `kb/**` is add-only and owned by the kb writer,
so this pass reports the divergence rather than editing or archiving raw sources. Until it
lands, **Status: open**, listed in [docs/gaps/README.md](README.md).
