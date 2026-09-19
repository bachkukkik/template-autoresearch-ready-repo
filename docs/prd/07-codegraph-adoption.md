# PRD 07 — CodeGraph Adoption

> Intent for agent code-graph search: the repo adopts
> [CodeGraph](https://github.com/colbymchenry/codegraph) — a local, deterministic
> tree-sitter → SQLite symbol/edge graph served over MCP — as the **primary
> graph search for coding agents**, with CLI twins for harnesses that have no MCP
> client.
> Grounded in: [codegraph](../../kb/entities/codegraph.md),
> [agent-code-graph-search](../../kb/concepts/agent-code-graph-search.md),
> [codegraph-vs-graphify](../../kb/comparisons/codegraph-vs-graphify.md)
> (synthesized from `kb/raw/articles/codegraph-mcp-code-intelligence.md`).
>
> Decision record 2026-09-18 (kb comparison verdict, recorded in `AGENTS.md`
> `## codegraph`): CodeGraph is the primary agent graph search; graphify is
> demoted to the optional **non-code** knowledge graph (docs/SQL/PDFs), conditional
> on `graphify-out/graph.json`. Closed gap:
> [docs/gaps/_archive/07-codegraph-no-prd.md](../gaps/_archive/07-codegraph-no-prd.md).

## Context

The knowledge base settled a decision stage 4 never recorded. `kb/` holds the
CodeGraph raw source plus three synthesized pages (one-tool MCP surface by design;
CLI twins for non-MCP harnesses; a gitignored local `.codegraph/` index; the
`sync`/`affected` workflow; the `DO_NOT_TRACK` opt-out), and `AGENTS.md`
`## codegraph` — with the Harness-Adapter row "Code graph (structural search)" —
adopts it as the repo's primary graph search with per-harness install commands.
But `PRD.md` and `docs/prd/01..06` were silent: no success criterion, no `_Verify:_`
test and no CI job mentioned code graph search at all, so a later removal of the
`## codegraph` section, the `.codegraph/` placeholder or the three kb pages failed
nothing. That KB → PRD divergence is
[docs/gaps/_archive/07-codegraph-no-prd.md](../gaps/_archive/07-codegraph-no-prd.md),
resolved by this PRD.

**Target users:** coding agents working in this repo across harnesses — Hermes,
opencode, Claude Code, Copilot (MCP-native) and CLI-only harnesses with no MCP
client (e.g. a DeepSeek harness) — plus maintainers reviewing structural changes.

**Constraints:** local-first (the index never leaves the machine); the tool is MIT,
Node (engines ≥20 <25); `.codegraph/` is a local artifact whose contents are
gitignored with only `.codegraph/.gitkeep` tracked; the MCP surface is **one tool by
design** (`codegraph_explore`); telemetry is anonymous, default-on, opt-out; no live
credentials anywhere in the wiring.

## Success Criteria

- **SC1** — **One-tool MCP surface.** A configured MCP client sees exactly one
  CodeGraph tool, `codegraph_explore` (symbol-bag / natural-language query → call
  path + relevant source + blast-radius summary in one call); the other seven tools
  stay unlisted by default. _Verify:_ `tests/unit/test_codegraph_adoption.py`
  (AC-CG-001 — asserts the documented one-tool surface and the stage-4 pointer in
  `AGENTS.md` `## codegraph`); the live MCP call stays hand-verified 2026-09-19:
  `tools/list` → 1 tool, `codegraph_explore` (see [docs/07](../07-codegraph-adoption.md)).

- **SC2** — **CLI twins are the fallback for harnesses with no MCP client.** Every
  MCP tool has a CLI twin — `codegraph explore|node|callers|callees|impact|query|affected`
  — so a CLI-only harness answers the same structural questions without an MCP
  client, and `CODEGRAPH_MCP_TOOLS` re-enables any of the seven hidden tools on the
  MCP surface. _Verify:_ `tests/unit/test_codegraph_adoption.py` (AC-CG-002 —
  asserts the CLI-twins fallback in `AGENTS.md` `## codegraph` and in the
  Harness-Adapter per-harness row); the twins themselves stay hand-verified in
  [docs/07](../07-codegraph-adoption.md).

- **SC3** — **Deterministic local graph under a gitignored `.codegraph/`.**
  `codegraph init` builds a tree-sitter → SQLite (WAL) symbol/edge graph inside
  `.codegraph/`; the directory's contents are ignored and only `.codegraph/.gitkeep`
  is tracked, so the index never leaves the machine and never enters a diff.
  _Verify:_ `tests/unit/test_codegraph_adoption.py` (AC-CG-004 — asserts the
  `.codegraph/.gitkeep` placeholder and the `.gitignore` ignore-then-unignore pair,
  lines 88–93); the git-index outcome is a CI check
  (`git check-ignore .codegraph/codegraph.db` → ignored,
  `git ls-files .codegraph` → `.codegraph/.gitkeep`).

- **SC4** — **`codegraph sync` before trusting a fresh graph.** A session whose
  working tree has moved past the index runs `codegraph sync` (the resident file
  watcher otherwise auto-syncs); `codegraph status` reports pending changes and
  points at the command. _Verify:_ (no test yet — tracked as a gap); instruction
  surface `AGENTS.md` `## codegraph`; `codegraph status` / `codegraph sync` output.

- **SC5** — **Test selection via `codegraph affected`.** `git diff --name-only |
  codegraph affected --stdin` maps changed files to the test files that cover them,
  so a change targets its own tier instead of running everything. _Verify:_ (no test
  yet — tracked as a gap); command `codegraph affected --stdin` — see *Assumptions*
  for its current gap-mapping limitation on this layout.

- **SC6** — **Telemetry opt-out.** Any CI or scripted codegraph run sets
  `DO_NOT_TRACK=1`, so the anonymous rollups (default-on) are off — off means off.
  _Verify:_ `tests/unit/test_codegraph_adoption.py` (AC-CG-003 — asserts the
  `DO_NOT_TRACK=1` opt-out is stated for any CI or scripted codegraph run); no CI
  job sets or asserts the env itself.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| MCP surface exposes exactly one tool (`codegraph_explore`) — documented surface | `tests/unit/test_codegraph_adoption.py` | AC-CG-001 |
| CLI twins answer without an MCP client; `CODEGRAPH_MCP_TOOLS` re-enables hidden tools — documented fallback | `tests/unit/test_codegraph_adoption.py` | AC-CG-002 |
| `.codegraph/` contents gitignored; only `.gitkeep` tracked — placeholder + `.gitignore` pair | `tests/unit/test_codegraph_adoption.py` | AC-CG-004 |
| `codegraph sync` brings a stale index current | — (no test yet — tracked as a gap) | — |
| `codegraph affected --stdin` maps changed files to test files | — (no test yet — tracked as a gap) | — |
| `DO_NOT_TRACK=1` set on scripted/CI runs — stated for every scripted run | `tests/unit/test_codegraph_adoption.py` | AC-CG-003 |
| Stage-3 grounding present (3 layer-2 kb pages + the raw article) | `tests/unit/test_codegraph_adoption.py` | AC-CG-005 |
| Stage-4/stage-6 doc pair present and listed in `PRD.md` | `tests/unit/test_codegraph_adoption.py` | AC-CG-006 |

## Assumptions

- The adoption is **instruction-surface plus a hermetic surface test**:
  `AGENTS.md` `## codegraph`, the `.codegraph/.gitkeep` placeholder, `.gitignore`
  lines 88–93 and the three `kb/` pages are the footprint, and
  `tests/unit/test_codegraph_adoption.py` (AC-CG-001..006) now asserts that
  footprint directly. Two SCs still carry `_Verify:_ (no test yet — tracked as a
  gap)` — **SC4** (`codegraph sync`) and **SC5** (`codegraph affected`) describe
  live tool behaviour the unit tier cannot reach hermetically (the tool is Node and
  not guaranteed on a CI runner), and `codegraph affected` currently maps nothing
  on this repo's layout. SC1/SC2/SC3/SC6 point at test IDs that assert the
  documented surface; the live tool result behind each stays hand-verified in
  [docs/07](../07-codegraph-adoption.md). `[ASSUMPTION]`
- A test that a red PR could actually fail on is an **instruction/file assertion**
  — exactly what `tests/unit/test_codegraph_adoption.py` is: stdlib-only, file
  reads only, no subprocess and no `codegraph` binary (it asserts the `## codegraph`
  section, the `.codegraph/.gitkeep` placeholder with its `.gitignore` pair, the
  three kb pages + raw article, and the doc pair listed in `PRD.md`). The
  git-index outcome (`git ls-files .codegraph`) stays asserted by the `doctrine`
  CI job, which names `.codegraph` among its tracked roots. `[ASSUMPTION]`
- `codegraph affected --stdin` returned "No test files affected by the changed
  files." for `service/src/runner.py` on this repo's Python layout even though the
  call edges exist (`codegraph callers run_loop` lists `tests/unit/test_runner.py`
  and `tests/unit/test_workspace.py`, and `codegraph_explore`'s blast radius names
  the same tests). Test selection is therefore also available from the explore
  blast radius until upstream's matcher covers this layout. `[ASSUMPTION]`
- The index is a **per-clone artifact**: a fresh clone has an empty `.codegraph/`
  until `codegraph install` + `codegraph init`; `codegraph` re-creates an ignored
  `.codegraph/.gitignore` on validating commands (never commit it, never blanket-add
  `.codegraph/`). `[ASSUMPTION]`
- v1.6.0 (research of 2026-09-16) is the reference version; the vendor A/B numbers
  (−35% cost, −57% tokens, Claude-Code arm) are vendor-run and not re-measured here.
  `[ASSUMPTION]`

## Confidence

**Medium** — the mechanism and its instruction surface are verified by hand (MCP
`tools/list` returns exactly one tool; a live `codegraph_explore` call returns source
+ blast radius; CLI twins answer; `.codegraph/codegraph.db` is ignored with
`.codegraph/.gitkeep` tracked), and the adoption surface is now pinned by
`tests/unit/test_codegraph_adoption.py` (AC-CG-001..006 — hermetic, no `codegraph`
binary). What stays untested: the **live** tool calls — no CI job runs `codegraph`,
so SC4 and SC5 keep the explicit no-test marker — and `codegraph affected` does not
yet map this repo's layout. Four of the six SCs point at a real test ID; the other
two say why they do not.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml`. No PR merges with a red test.
This PRD adds **no CI job** — it records an instruction-surface adoption plus a
hermetic test in the existing `unit` tier, `tests/unit/test_codegraph_adoption.py`
(AC-CG-001..006). That test is an instruction/file assertion (see *Assumptions*), so
it runs everywhere without the Node tool installed, and a red CI run now fails when
the adoption surface is removed. The live `codegraph` calls are not CI-exercised;
SC4 and SC5 stay hand-verified in [docs/07](../07-codegraph-adoption.md).
