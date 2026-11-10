# PRD 20 — AutoResearch as a Service: One Engine, Four Surfaces

> Intent: one codebase drives the autoresearch loop from every surface an adopter
> reaches for — **agent mode** (slash commands / skill), **CLI**, **REST API** and
> **MCP** — so the template demonstrates autoresearch *as a service* without a second
> or third copy of the keep/discard loop.
> Grounded in: [script-owned-keep-revert](../../kb/concepts/script-owned-keep-revert.md),
> [headless-harness-invocation](../../kb/concepts/headless-harness-invocation.md),
> [autoresearch-engines-real-world](../../kb/comparisons/autoresearch-engines-real-world.md);
> builds on PRD-05 (REST + MCP service), PRD-06 (multi-topic service) and PRD-17 (engine).
> Gap: [20-three-loops-one-name](../gaps/20-three-loops-one-name.md).

## Context

Before this PRD the repo carried three loops under one name: `service/` ran the toy
`val_bpb` contract through its own `runner.py`; `autoresearch/engine/` was the real-code
engine reachable only from a CLI; the vendored `.agents/skills/autoresearch` is a
prompt-only loop an agent runs by hand. The REST/MCP surface therefore could not target
real code, and the CLI could not be reached as a service.

## Scope

In: package layout under `autoresearch/`; the service re-founded on the engine; an
engine-backed agent skill and slash commands; an API harness allowlist. Out: changing the
engine's loop semantics (PRD-17 owns them); removing the vendored uditgoenka skill (it
stays as a documented, separate methodology); multi-host job distribution.

## Success Criteria

- **SC1 — One package, one lock.** `service/` no longer exists at the repo root. The
  engine (`autoresearch/engine/autoresearch/`), the contract (`autoresearch/contract/`)
  and the service (`autoresearch/service/`) ship from ONE `autoresearch/pyproject.toml`
  (engine core is stdlib-only; the service is the `[service]` optional extra) with one
  `uv.lock`; `docker compose build` builds from it.
  _Verify:_ `tests/unit/test_service_layout.py` (AC-SVC-001..003) + the `e2e` CI job.
- **SC2 — One loop.** Every surface reaches keep/discard through the engine package
  (`autoresearch.loop` / `autoresearch.measure`); the service carries no loop or metric
  parser of its own.
  _Verify:_ `tests/unit/test_service_layout.py` (AC-SVC-004, static import check with a
  negative control).
- **SC3 — One handler per operation on REST and MCP.** `run_start`, `run_status`,
  `run_report`, `run_cancel` and `doctor` are each one Python handler, registered both as a
  REST route under `/api/v1/runs` and as an MCP tool of the same name. The PRD-05/06
  `research_*` operations keep their contract (job id, poll, `val_bpb` numeric, corpus
  fail-fast) and are now served by an engine baseline measurement of the bundled
  `contract` workload.
  _Verify:_ `tests/unit/test_routes.py` (AC-MCP-*), `tests/unit/test_service_engine.py`
  (AC-SVC-010..016), `tests/integration/test_service_endpoints.py`,
  `tests/integration/test_mcp_endpoints.py`, `tests/e2e/service.bats` (AC-MCP-101..104,
  AC-SVC-101..102).
- **SC4 — Safe by default.** Over REST/MCP the only agent allowed without configuration is
  `replay`; `claude`, `opencode`, `hermes`, `dsh` require listing in
  `RESEARCH_ALLOWED_AGENTS`; `command` (arbitrary shell) is refused over the API even when
  listed. Every run executes on a per-job copy of a bundled workload under the service's
  workspaces dir, never on a caller-supplied host path. Auth (bearer) is unchanged.
  _Verify:_ `tests/unit/test_service_engine.py` (AC-SVC-020..024, negative controls).
- **SC5 — Agent mode everywhere.** A repo-native `autoresearch-engine` skill at
  `.agents/skills/autoresearch-engine/SKILL.md` drives the engine CLI; slash commands
  `/ar-init`, `/ar-run`, `/ar-status`, `/ar-report` live once in `.agents/commands/` and
  resolve through `.claude/commands` and `.opencode/commands` symlinks. Hermes and dsh
  reach the same flow through the skill.
  _Verify:_ `tests/unit/test_harness_neutrality.py` (AC-HRN-019..020).
- **SC6 — Demonstrated live.** From a clean pull and a `docker compose up`, one bundled
  workload is driven through each surface (CLI, REST, MCP, a slash command) with recorded
  commands and outputs.
  _Verify:_ `docs/20-autoresearch-as-a-service.md` (empirical; commands reproduced there).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| single package + lock; no root `service/`; compose builds from `autoresearch/` | `tests/unit/test_service_layout.py` | AC-SVC-001..003 |
| service imports the engine; no private loop/metric parser | `tests/unit/test_service_layout.py` | AC-SVC-004 |
| `run_*`/`doctor` dual-registered; per-job workspace; engine baseline for `research_*` | `tests/unit/test_service_engine.py` | AC-SVC-010..016 |
| agent allowlist, `command` refused, no host-path workloads | `tests/unit/test_service_engine.py` | AC-SVC-020..024 |
| REST + MCP live over a socket / container | `tests/integration/*`, `tests/e2e/service.bats` | AC-MCP-*, AC-SVC-101..102 |
| skill + slash commands resolve for every harness | `tests/unit/test_harness_neutrality.py` | AC-HRN-019..020 |

## CI/CD Gate

Unit and integration tiers run in the existing `unit` / `integration` jobs; the container
tier in `e2e`. The `doctrine` job's tracked-root list gains `.agents/commands` via its
parent `.agents`; no new job.

## Assumptions

- [ASSUMPTION] A baseline-only engine run (`--max-iterations 0` equivalent) of the toy
  contract is a faithful replacement for the old `prepare.py && train.py` runner: same
  `val_bpb` metric, same time budget.
- Real-harness runs over the API need host credentials and binaries inside the container;
  the shipped image carries none, so the live demo of a real harness runs through the CLI
  and the API demo uses `replay`.

## Confidence

**Medium-high.** The engine and the service each already pass their own tiers; the work is
re-wiring, not new loop semantics.
