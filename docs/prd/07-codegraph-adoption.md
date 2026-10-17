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
Node (engines ≥20 <25); `.codegraph/` is a local artifact ignored **wholesale** — the
`.gitignore` rule is the directory itself, so nothing under it is tracked (upstream's
rule); the MCP surface is **one tool by design** (`codegraph_explore`); telemetry is
anonymous, default-on, opt-out; no live credentials anywhere in the wiring.

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

- **SC3** — **Deterministic local graph under an ignored `.codegraph/`.**
  `codegraph init` builds a tree-sitter → SQLite (WAL) symbol/edge graph inside
  `.codegraph/`; the directory is ignored wholesale and nothing under it is tracked,
  so the index never leaves the machine and never enters a diff.
  _Verify:_ `tests/unit/test_codegraph_adoption.py` (AC-CG-004 — asserts the single
  `.gitignore` `.codegraph/` directory rule and that the git index holds no path
  under `.codegraph/`; its `git` read sits behind the `tests/conftest.py` preflight).

- **SC4** — **`codegraph sync` before trusting a fresh graph.** A session whose
  working tree has moved past the index runs `codegraph sync` (the resident file
  watcher otherwise auto-syncs); `codegraph status` reports pending changes and
  points at the command. _Verify:_ `tests/integration/test_codegraph_live.py`
  (AC-CG-201 — **opt-in**: the module resolves the `codegraph` binary through the
  `tests/conftest.py` `require_tool` preflight and skips, naming the tool, on a host
  without one, as the CI runners are) against a hermetic tmp git project;
  instruction surface `AGENTS.md` `## codegraph`.

- **SC5** — **Test selection via `codegraph affected`.** `git diff --name-only |
  codegraph affected --stdin` maps changed files to the test files that cover them,
  so a change targets its own tier instead of running everything. A test-file glob
  is required on this layout (`-f 'tests/**/*.py'`). _Verify:_
  `tests/integration/test_codegraph_live.py` (AC-CG-202 — **opt-in**, same
  preflight; asserts a test-file glob maps a changed source file to its test, and
  that the default filter maps nothing). See *Assumptions* for the filter
  requirement.

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
| `.codegraph/` ignored wholesale; git tracks nothing under it | `tests/unit/test_codegraph_adoption.py` | AC-CG-004 |
| `codegraph sync` brings a stale index current (opt-in: skips without the binary) | `tests/integration/test_codegraph_live.py` | AC-CG-201 |
| `codegraph affected --stdin` maps changed files to test files (opt-in: skips without the binary) | `tests/integration/test_codegraph_live.py` | AC-CG-202 |
| `DO_NOT_TRACK=1` set on scripted/CI runs — stated for every scripted run | `tests/unit/test_codegraph_adoption.py` | AC-CG-003 |
| Stage-3 grounding present (3 layer-2 kb pages + the raw article) | `tests/unit/test_codegraph_adoption.py` | AC-CG-005 |
| Stage-4/stage-6 doc pair present and listed in `PRD.md` | `tests/unit/test_codegraph_adoption.py` | AC-CG-006 |

## Assumptions

- The adoption is **instruction-surface plus tests at two tiers**: `AGENTS.md`
  `## codegraph`, the `.gitignore` `.codegraph/` rule and the three `kb/` pages are
  the footprint, and `tests/unit/test_codegraph_adoption.py` (AC-CG-001..006)
  asserts that footprint directly. **SC4** (`codegraph sync`) and **SC5**
  (`codegraph affected`) describe live tool behaviour the unit tier cannot reach
  (the tool is Node and not guaranteed on a CI runner), so they carry an **opt-in
  integration test**, `tests/integration/test_codegraph_live.py` (AC-CG-201..202),
  which drives the real CLI against a hermetic tmp git project and **skips, naming
  the tool,** where `codegraph` is absent — as on the CI runners. A skip never fails
  the tier, so the CI verdict does not depend on an ambient binary. SC1/SC2/SC3/SC6
  point at test IDs that assert the documented surface; the live tool result behind
  each stays hand-verified in [docs/07](../07-codegraph-adoption.md).
  `[ASSUMPTION]`
- The unit tier's `tests/unit/test_codegraph_adoption.py` stays an **instruction/file
  assertion** — stdlib file reads plus one `git` read of the index in AC-CG-004,
  behind the `require_tool` preflight — and never invokes the `codegraph` binary. The
  live half sits in the integration tier and is opt-in, so the `unit` tier's verdict
  never moves onto the host. `[ASSUMPTION]`
- `codegraph affected --stdin` maps **nothing by default** on this repo's Python
  layout: the default test-file filter does not match `tests/*.py`, so `echo
  service/src/runner.py | codegraph affected --stdin` prints "No test files affected
  by the changed files." **A test-file glob fixes it** — `echo contract/prepare.py |
  codegraph affected --stdin -f 'tests/**/*.py' -q` prints
  `tests/unit/test_domain_hooks.py`, and `service/src/main.py` prints
  `tests/unit/test_routes.py` + `tests/unit/test_workspace.py`. SC5 therefore
  requires `-f <glob>`, and AC-CG-202 asserts both halves (the glob maps, the
  default stays empty). Test selection is also available from the
  `codegraph_explore` blast radius. `[ASSUMPTION]`
- The index is a **per-clone artifact**: a fresh clone has no `.codegraph/` at all
  until `codegraph install` + `codegraph init`; codegraph then writes its own
  `.codegraph/.gitignore` (a `*` + `!.gitignore` pair) on validating commands. The
  directory is ignored wholesale, so none of that reaches `git status` — never
  commit anything under `.codegraph/`. `[ASSUMPTION]`
- v1.6.0 (research of 2026-09-16) is the reference version; the vendor A/B numbers
  (−35% cost, −57% tokens, Claude-Code arm) are vendor-run and not re-measured here.
  `[ASSUMPTION]`

## Confidence

**Medium** — the mechanism and its instruction surface are verified by hand (MCP
`tools/list` returns exactly one tool; a live `codegraph_explore` call returns source
+ blast radius; CLI twins answer) and by tests at two tiers:
`tests/unit/test_codegraph_adoption.py` (AC-CG-001..006 — hermetic, no `codegraph`
binary) pins the surface, and `tests/integration/test_codegraph_live.py`
(AC-CG-201..202) drives the real CLI for SC4/SC5. All six SCs now point at a test
ID. What is not CI-asserted: the two live tests **skip** wherever the `codegraph`
binary is absent, which is every CI runner, so remote CI stays green without
exercising them; and `codegraph affected` needs an explicit `-f` test glob on this
layout.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml`. No PR merges with a red test.
This PRD adds **no CI job** — it records an instruction-surface adoption plus tests
in the existing tiers: the `unit` tier's `tests/unit/test_codegraph_adoption.py`
(AC-CG-001..006), which runs everywhere without the Node tool, and the `integration`
tier's opt-in `tests/integration/test_codegraph_live.py` (AC-CG-201..202), which the
`require_tool` preflight skips — naming `codegraph` — where the binary is absent, so
a runner without the tool reports a skipped test, never a red one. The integration
job's junit guard still passes: a partial skip is not a whole-tier skip. A red CI run
fails when the adoption surface is removed; the live calls behind SC4/SC5 execute
wherever a developer has `codegraph` installed.
