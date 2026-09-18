# 07 — The CodeGraph knowledge base has no stage-4 PRD

**Layers:** kb ↔ prd
**Status:** open
**Opened:** 2026-09-18

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

PRD edit — stage 4 must carry the CodeGraph adoption: either a new PRD-07
("Agent code-graph search" — SCs for the MCP surface, the CLI fallback, the
deterministic local graph and the telemetry opt-out, each with a `_Verify:` test)
with the matching `docs/07-slug.md` stage-6 doc, or an added SC in a PRD that owns
agent tooling (PRD-03). Not applied in this sync: creating a topic PRD means
creating its stage-6 counterpart too, and the surrounding surfaces (`AGENTS.md`,
`PRD.md`, `.gitignore`, `kb/`) are owned by another writer — the decision needs to
be taken once, not split across writers. Until it lands, **Status: open**, listed in
[docs/gaps/README.md](README.md).
