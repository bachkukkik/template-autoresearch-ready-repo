# 07 — The CodeGraph knowledge base has no stage-4 PRD

**Layers:** kb ↔ prd
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-19 — PRD-07 written; see [docs/prd/07-codegraph-adoption.md](../../prd/07-codegraph-adoption.md)

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `kb/raw/articles/codegraph-mcp-code-intelligence.md` (ingested 2026-09-16) → `kb/concepts/agent-code-graph-search.md`, `kb/entities/codegraph.md`, `kb/comparisons/codegraph-vs-graphify.md` | CodeGraph — a local-first, deterministic tree-sitter → SQLite symbol/edge graph served over MCP — is the subject of a raw source plus three synthesized pages: one-tool MCP surface by design, CLI twins for harnesses without an MCP client, `codegraph sync`/`affected` workflow, `DO_NOT_TRACK` |
| B | `AGENTS.md` `## codegraph` + Harness-Adapter row "Code graph (structural search)" | the repo's canonical instruction doc adopts CodeGraph as the primary code-graph search, with install/init commands per harness |
| B | `PRD.md` + `docs/prd/01..06` | no stage-4 PRD mentions code graph search at all |

## Evidence

```bash
grep -rni "codegraph" docs/prd/ PRD.md
# (no output)
grep -c "codegraph" AGENTS.md
# 8
ls kb/entities kb/concepts kb/comparisons | wc -l
# 21 layer-2 pages, three of them CodeGraph
git status --short --untracked-files=all
# ?? kb/entities/codegraph.md, kb/concepts/agent-code-graph-search.md,
# ?? kb/comparisons/codegraph-vs-graphify.md,
# ?? kb/raw/articles/codegraph-mcp-code-intelligence.md
```

## Impact

Stage 3 holds a capability that stage 4 never asks for, so:

- no success criterion and no test covers the adoption — `codegraph` appears in no
  `_Verify:` annotation and in no CI job, so a later removal of the `## codegraph`
  section, the `.codegraph/` placeholder or the kb pages fails nothing;
- the grounding direction is broken upward: KB → PRD is the direction the doctrine
  requires, and here the PRD is silent while the KB is explicit;
- the three pages are untracked in the working tree, so a fresh clone reads a KB
  that does not mention CodeGraph at all — the same divergence one level down.

Nothing here says the adoption is wrong; it says stage 4 has not been told about it.

## Resolution

PRD edit — applied 2026-09-19: `docs/prd/07-codegraph-adoption.md` created (the
CodeGraph adoption at stage 4: SCs for the one-tool MCP surface, the CLI-twins
fallback, the deterministic gitignored `.codegraph/` index, `codegraph sync`,
`codegraph affected` test selection and the `DO_NOT_TRACK=1` opt-out), with its
stage-6 counterpart [docs/07-codegraph-adoption.md](../../07-codegraph-adoption.md)
and the `07` rows in `PRD.md` + `docs/README.md`. **Status: resolved.**
