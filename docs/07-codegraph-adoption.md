# 07 — CodeGraph Adoption

## What

The repo's primary code-graph search for coding agents: [CodeGraph](https://github.com/colbymchenry/codegraph)
— a local, deterministic tree-sitter → SQLite symbol/edge graph served over MCP —
adopted in the `## codegraph` section of `AGENTS.md`, with CLI twins for harnesses
that have no MCP client, and grounded in three `kb/` pages.

## Why

- Structural questions ("how does X reach Y?", "what breaks if I change Z?", "which
  tests are affected?") are answered from a pre-built index in one call, instead of a
  grep/read loop the agent re-derives every session.
- Local-first: the index under `.codegraph/` never leaves the machine; telemetry is
  anonymous, default-on, opt-out (`DO_NOT_TRACK=1`).
- The template ships the *decision*, not just a suggestion: `AGENTS.md` names
  CodeGraph the primary graph search and demotes graphify to the optional non-code
  knowledge graph (kb verdict: coexist, not replace).

## How

```bash
npm i -g @colbymchenry/codegraph   # once per machine (per-user, not root)
codegraph install                  # once per machine: wires agent MCP configs (auto-detects hermes/opencode/claude/…)
codegraph init                     # once per clone: builds .codegraph/ (ignored wholesale — nothing tracked)
```

| Surface | Detail |
|---|---|
| MCP | one tool by design — `codegraph_explore` (symbol-bag query → call path + source + blast radius in one call). The other 7 (`node`/`search`/`callers`/`callees`/`impact`/`files`/`status`) are unlisted by default |
| Re-enable hidden tools | `CODEGRAPH_MCP_TOOLS=explore,node,search,callers` |
| CLI twins (no MCP client) | `codegraph explore\|node\|callers\|callees\|impact\|query\|affected` |
| Index | `.codegraph/` SQLite (WAL), local, ignored wholesale — nothing under it is tracked |
| Fresh session | `codegraph sync` before trusting the graph (resident watcher otherwise auto-syncs) |
| Test selection | `git diff --name-only \| codegraph affected --stdin -f 'tests/**/*.py'` (a test glob is required here — see *What Fails*) |
| Telemetry | anonymous rollups, default ON, opt out with `DO_NOT_TRACK=1` (or `CODEGRAPH_TELEMETRY=0`) |

Harness wiring is per harness (Hermes `$HERMES_HOME/config.yaml` `mcp_servers` +
`platform_toolsets.cli` `mcp-codegraph`; opencode `opencode.jsonc`; Claude
`./.mcp.json`; any other MCP client → stdio `codegraph serve --mcp`). The stage-4
intent and success criteria are in [docs/prd/07-codegraph-adoption.md](prd/07-codegraph-adoption.md).

## Verification

Run from the repo root, 2026-09-19; the ignore, test-selection and test-coverage
entries re-run 2026-10-17. CodeGraph v1.6.0 installed at
`~/.npm-global/bin/codegraph`.

```bash
grep -c codegraph AGENTS.md
# 20   (the ## codegraph section + Harness-Adapter row + inline mentions)

codegraph --version
# 1.6.0

DO_NOT_TRACK=1 codegraph status
# CodeGraph Status — Project: <repo>
#   Files: 35   Nodes: 413   Edges: 796   DB Size: 1.05 MB
#   Backend: node:sqlite — built-in (full WAL) | Journal: wal
#   Files by Language: python 32, yaml 3

git check-ignore -v .codegraph/codegraph.db
# .gitignore:93:.codegraph/        .codegraph/codegraph.db        # ignored (2026-10-17)
git ls-files .codegraph
# (no output — nothing under .codegraph/ is tracked)            # 2026-10-17

# a fresh clone's own codegraph state stays out of git status (2026-10-17)
DO_NOT_TRACK=1 codegraph init          # 66 files, 1,088 nodes
git status --porcelain | grep -c codegraph/
# 0   (codegraph.db AND the .codegraph/.gitignore it writes are both ignored)

# MCP one-tool surface (stdio JSON-RPC probe)
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | DO_NOT_TRACK=1 codegraph serve --mcp | grep -o '"name":"codegraph_[a-z_]*"' | sort -u
# "name":"codegraph_explore"
# prefix CODEGRAPH_MCP_TOOLS=explore,node,search,callers on the `codegraph serve` line:
# "name":"codegraph_callers" "name":"codegraph_explore" "name":"codegraph_node" "name":"codegraph_search"

DO_NOT_TRACK=1 codegraph node run_loop
# **run_loop** (method) — service/src/runner.py:147  (+ verbatim source)
DO_NOT_TRACK=1 codegraph callers run_loop
# Callers of "run_loop" (6): _run_job (service/src/main.py:130),
#   test_default_workload_completes_with_metric + test_timeout_kills_slow_train (tests/unit/test_runner.py), …
DO_NOT_TRACK=1 codegraph files
# Project Structure (37 files): .github/…, contract/…, service/…

echo service/src/runner.py | DO_NOT_TRACK=1 codegraph affected --stdin
# ℹ No test files affected by the changed files.                # the DEFAULT filter matches nothing

echo contract/prepare.py | DO_NOT_TRACK=1 codegraph affected --stdin -f 'tests/**/*.py' -q
# tests/unit/test_domain_hooks.py                               # a test glob maps it (2026-10-17)
# tests/unit/test_prepare_py.py
echo service/src/main.py | DO_NOT_TRACK=1 codegraph affected --stdin -f 'tests/**/*.py' -q
# tests/unit/test_routes.py
# tests/unit/test_workspace.py

DO_NOT_TRACK=1 codegraph sync
# Syncing CodeGraph → Already up to date → Done

ls -a .codegraph
# .  ..  .gitignore  codegraph.db                               # neither is tracked (2026-10-17)
```

A live MCP `tools/call` with `{"query":"run_loop"}` returns "Found 36 symbols
across 4 files" plus blast-radius lines that name the dependent tests
(`tests/unit/test_runner.py`, `tests/unit/test_workspace.py`).

The adoption *surface* is verified hermetically, with no `codegraph` binary present;
SC4/SC5 run in the opt-in integration tier (2026-10-17):

```bash
python3 -m pytest tests/unit/test_codegraph_adoption.py -q
# 6 passed   (AC-CG-001..006: AGENTS.md ## codegraph + its stage-4 pointer, the
# CLI-twins fallback, DO_NOT_TRACK=1, the wholesale `.codegraph/` ignore rule with
# nothing tracked under it, the three kb pages + raw article, the stage-4/stage-6
# pair listed in PRD.md)

python3 -m pytest tests/integration/test_codegraph_live.py -q
# 2 passed   (AC-CG-201: init → status → sync → query; AC-CG-202: `affected --stdin
# -f 'tests/*.py'` maps the changed source to its test, the default filter stays empty)

# the skip path the CI runners take — no codegraph on PATH:
PATH=<dir-with-a-python3-and-no-codegraph>:/usr/bin:/bin python3 -m pytest \
  tests/integration/test_codegraph_live.py -q
# 2 skipped  ("ambient tool 'codegraph' is not on PATH (shutil.which)")
```

## What Works

- **One-tool MCP surface, live:** `tools/list` over `codegraph serve --mcp` returns
  exactly `codegraph_explore`, and a `tools/call` for `run_loop` returns the blast
  radius + verbatim source — the design intent in the kb pages reproduces.
- **The re-enable path works:** with `CODEGRAPH_MCP_TOOLS=explore,node,search,callers`,
  `tools/list` returns those four tools, so the hidden seven are opt-in, not lost.
- **CLI twins answer without an MCP client:** `codegraph files` (37-file structure),
  `codegraph node run_loop` (definition + source at `service/src/runner.py:147`),
  `codegraph callers run_loop` (6 callers, including two test functions).
- **The index is local and ignored:** `.codegraph/codegraph.db` (~1.05 MB) and the
  `.codegraph/.gitignore` codegraph writes for itself are both ignored by the single
  `.codegraph/` directory rule, so `codegraph init` in a fresh clone leaves
  `git status` clean — the graph never enters a diff, yet a clone can rebuild it.
- **The adoption is documented where agents read it:** `AGENTS.md` carries 20
  `codegraph` mentions (the `## codegraph` section + the Harness-Adapter row), and
  three `kb/` pages (entity/concept/comparison) ground the decision.
- **The adoption surface is test-covered:** `tests/unit/test_codegraph_adoption.py`
  (AC-CG-001..006) asserts, hermetically and without the Node tool, the
  `## codegraph` section and its stage-4 pointer, the CLI-twins fallback, the
  `DO_NOT_TRACK=1` opt-out, the wholesale `.codegraph/` ignore rule with nothing
  tracked under it, the three `kb/` pages + the raw article, and the stage-4/stage-6
  pair listed in `PRD.md` — removing any of them is red.
- **SC4/SC5 run against the real CLI where it exists:** the opt-in integration module
  `tests/integration/test_codegraph_live.py` (AC-CG-201..202) drives a hermetic tmp
  git project through `codegraph init` → `status` → `sync` → `query` and
  `affected --stdin -f 'tests/*.py'`. It skips, naming the tool, where `codegraph` is
  absent, so the CI runners report skips and never a red tier.

## What Fails

- **`codegraph affected` maps nothing with its default filter:** `echo
  service/src/runner.py | codegraph affected --stdin` returns "No test files affected
  by the changed files." on this Python layout, even though the call edges exist.
  A test-file glob (`-f 'tests/**/*.py'`) is what maps a changed file to its tests.
- **The index is per-clone:** a fresh clone has no `.codegraph/` until
  `codegraph install` + `codegraph init`; `codegraph status` flags pending changes
  and the graph cannot be trusted before `codegraph sync`.
- **Dynamic dispatch is silent:** static analysis cannot see reactive/reconciler
  runtimes (Halo, MediatR, Vue Proxy); the tool is silent, not wrong — partial
  bridging is worse than none.
- **Telemetry is default-on and opt-out is instruction-only:** `DO_NOT_TRACK=1` is
  documented in `AGENTS.md` and set by the opt-in integration helper, but no CI job
  asserts that a scripted run sets it.

## Resolution

- **`codegraph affected` maps nothing with its default filter:** pass a test glob —
  `codegraph affected --stdin -f 'tests/**/*.py'` maps `contract/prepare.py` to
  `tests/unit/test_domain_hooks.py` and `service/src/main.py` to
  `tests/unit/test_routes.py` + `tests/unit/test_workspace.py`. The default filter
  stays a limitation, so always give the recipient tier a glob.
- **The index is per-clone:** run `codegraph install` then `codegraph init`, and
  `codegraph sync` in a fresh session — both are stated in `AGENTS.md` `## codegraph`
  and the root `README.md`.
- **Dynamic dispatch is silent:** accepted class limit; route those questions to
  source reading — recorded in `kb/concepts/agent-code-graph-search.md` ("Known
  limits of the class").
- **Telemetry default-on:** set `DO_NOT_TRACK=1` on every scripted/CI codegraph run
  (the instruction surface already says so); the opt-in integration helper does it
  for its own calls, and a CI assertion over a scripted wrapper stays a future test.

## Verdict

**partial** — the adoption works where it is verifiable by hand: the one-tool MCP
surface, the CLI twins, the re-enable path, the ignored local SQLite index and
`codegraph sync` all reproduce on this machine (2026-09-19, re-run 2026-10-17). The
surface is pinned by the hermetic unit test `tests/unit/test_codegraph_adoption.py`
(AC-CG-001..006), and SC4/SC5 by the opt-in integration test
`tests/integration/test_codegraph_live.py` (AC-CG-201..202), which skips wherever the
Node tool is absent. Two seams stay open: `codegraph affected` needs an explicit
test-file glob on this layout, and no CI job exercises the live calls — read the doc
for the mechanism and those seams.
