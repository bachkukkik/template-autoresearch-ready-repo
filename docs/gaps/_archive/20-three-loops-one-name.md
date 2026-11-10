# 20 — Three loops under one name; the service cannot reach the engine

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-11-10

## Observation

The template ships three independent implementations of "autoresearch", and each surface
reaches a different one.

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md`, `docs/prd/17-autoresearch-engine.md` | REST/MCP serve "the autoresearch loop"; the engine is "a generic loop for real code" |
| B | `autoresearch/service/autoresearch_service/runner.py`, `autoresearch/engine/`, `.agents/skills/autoresearch/` at `6cb04cb` | the service runs only `prepare.py && train.py` of the toy contract via its own runner; the engine has a CLI and no API; the vendored skill is a prompt loop with neither |

## Evidence

- `autoresearch/service/autoresearch_service/runner.py` `run_loop` executes
  `python3 prepare.py && python3 train.py` and parses `val_bpb` with its own regex; it
  imports nothing from `autoresearch/engine/`.
- `autoresearch/engine/autoresearch/cli.py` exposes `init/run/status/report/doctor`; no
  module under `autoresearch/service/` references it.
- Packaging is unified as of the PRD-20 W1 layout move (`autoresearch/pyproject.toml`
  ships `autoresearch` + `autoresearch_service`), but only the packaging: the service
  still carries its own loop and metric parser.

## Impact

An adopter cannot point the REST/MCP service at real code, and cannot drive the engine
from an agent's slash command or an MCP client — "autoresearch as a service" is not
demonstrable from this template.

## Resolution

Code change + tests — PRD-20 (`docs/prd/20-autoresearch-as-a-service.md`), delivered in
four waves on `feat/autoresearch-as-a-service`:

1. **W1 one package.** `service/` folded into `autoresearch/service/`; engine, contract
   and service ship from one `autoresearch/pyproject.toml` and one `uv.lock`; the import
   `src` became `autoresearch_service` (`AC-SVC-001..003`,
   `tests/unit/test_service_layout.py`).
2. **W2 one loop.** The service re-founded on the engine: `runner.py` deleted, the
   `research_*` family served by one engine baseline measurement, `run_start` /
   `run_status` / `run_report` / `run_cancel` / `doctor` dual-registered on `/api/v1/runs*`
   and as MCP tools, per-job repo copies, and the `RESEARCH_ALLOWED_AGENTS` allowlist with
   `replay` the default and `command` always refused (`AC-SVC-004`, `AC-SVC-010..016`,
   `AC-SVC-020..024`, `AC-SVC-101..102`, `AC-SVC-201..202`).
3. **W2.5 tier fix.** The integration tier runs venv-free against the engine path, so the
   re-founded surface is measured, not skipped.
4. **W3 agent mode.** `/ar-init`, `/ar-run`, `/ar-status`, `/ar-report` live once in
   `.agents/commands/` (symlinked from `.claude/commands` and `.opencode/commands`) and
   `.agents/skills/autoresearch-engine/SKILL.md` drives the engine CLI
   (`AC-HRN-019..020`).

Reality is recorded in [docs/20](../../20-autoresearch-as-a-service.md): unit 353 passed,
integration 26 passed, `verify-clone.sh` 33 checks passed, one image, and a live temp
container showing a CLI replay run, `research_*` `val_bpb 3.795531`, a `run_*` engine
summary, `report` 200, and 9 MCP tools with `command` refused.
