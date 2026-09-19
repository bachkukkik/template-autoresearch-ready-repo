# 03 — kb/raw articles cite scratchpad paths as their evidence

**Layers:** kb ↔ prd
**Status:** resolved
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

`kb/raw/` ingest — **applied 2026-09-19** (funnel rule 3: add-or-archive; rule 5:
archive, never delete). The four steps, in order:

1. **Archived the superseded revisions before any edit** — copied verbatim to
   `kb/_archive/raw/articles/autoresearch-template-research-conclusions.md` and
   `kb/_archive/raw/articles/mcp-autoresearch-service-conclusions.md`. Both archive
   copies are byte-identical to the previous revisions:
   `git show HEAD:kb/raw/articles/<f> | diff - kb/_archive/raw/articles/<f>` → empty
   for both.
2. **Re-ingested the corrected revisions at the original paths.**
   `source_url` now names exactly one canonical source
   (`https://github.com/karpathy/autoresearch` / `https://modelcontextprotocol.io`);
   the rest of the provenance moved into a *Sources* table in the body pointing at
   material that actually survives a clone. For the first article that is
   `kb/raw/articles/autoresearch-program-md-reference.md` (upstream `program.md`) and
   the 11 files under `kb/raw/transcripts/`; the doctrine and the 2026 survey are
   tabled as external. For the second, the 10 per-item JSON snapshots were consulted
   during the run and **deliberately not retained** — the body says so outright,
   because the snapshot workspace was machine-local and deletable by design; no
   in-repo path was invented for them and no source was invented. Substantive
   sections are unchanged: `git diff --stat` is 30 and 36 changed lines, all in the
   frontmatter and the synthesis blockquote/`Sources` table.
3. **Re-stamped.** `ingested: 2026-09-04` kept, `reingested: 2026-09-19` added,
   `sha256` recomputed over the new body with the corpus test's own convention
   (`sha256(body.strip())`, frontmatter split by
   `tests/unit/test_corpus_integrity.py::_split_frontmatter`):

   | File | sha256 before | sha256 after |
   |---|---|---|
   | `kb/raw/articles/autoresearch-template-research-conclusions.md` | `9fda3a6e53dc8a696f6fa5c51d7332d15a4398cbd393ec5054e46fc56bbe8f0e` | `3f2a722385c870929cd205f571c87f4bfed9058260a98e553538df247c57b3db` |
   | `kb/raw/articles/mcp-autoresearch-service-conclusions.md` | `72ca641fccce734cdd1e7227d42af8ac5a9d6b13e7ecce2ceba87a33129bab15` | `aa81016fc3ee00d3456293d3e931b52835bdf615661a4ed4af3f3002b101dacb` |

   `python3 -m pytest tests/unit/test_corpus_integrity.py -v` → 4 passed;
   `python3 -m pytest tests/unit -q` → no regression.
4. **Layer-2 re-synthesis: no-op.** `git grep -n "scratchpads/" -- kb/concepts
   kb/entities kb/comparisons kb/queries` returns one hit —
   `kb/concepts/document-funnel-doctrine.md:20`, the funnel-chain stage name
   (`0 Prompt → 1 scratchpads/ → 2 kb/raw/ → 3 kb/ (llm-wiki) → …`), which cites no
   scratchpad path as evidence. No layer-2 page cites a scratchpad path, and no
   layer-2 `sources:` entry changed (both raw paths are unchanged), so an
   `llm-wiki ./kb/` run would have no input change and is a no-op here. Layer-2 pages
   are never hand-edited (rule 4) — nothing under `kb/concepts|entities|comparisons|queries`
   was touched.

After `git grep -n "scratchpads/" -- kb/` the only surviving hits are the prohibition
itself (`kb/SCHEMA.md:207-208`) and the funnel-chain stage name above; **zero** hits
under `kb/raw/`.

Bookkeeping: `kb/log.md` records the two archive and two re-ingest actions (append-only,
entries added, nothing else changed). `kb/index.md` rows 55–56 for both articles carry a
title and an ingest date only — no scratchpad path and no superseded provenance — so both
rows stay valid and `index.md` was **not** edited (llm-wiki-maintained). The `PR` requires
the `ingest` label, since `.github/workflows/sources-readonly.yml` gates any `kb/raw/**`
change on it. Closure kind: **`kb/raw/` ingest** (the `llm-wiki ./kb/` half is a no-op,
as established in step 4).
