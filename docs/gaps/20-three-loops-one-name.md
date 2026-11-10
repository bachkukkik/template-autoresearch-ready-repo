# 20 — Three loops under one name; the service cannot reach the engine

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-11-10

## Observation

The template ships three independent implementations of "autoresearch", and each surface
reaches a different one.

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/05-mcp-rest-service.md`, `docs/prd/17-autoresearch-engine.md` | REST/MCP serve "the autoresearch loop"; the engine is "a generic loop for real code" |
| B | `service/src/runner.py`, `autoresearch/engine/`, `.agents/skills/autoresearch/` at `6cb04cb` | the service runs only `prepare.py && train.py` of the toy contract via its own runner; the engine has a CLI and no API; the vendored skill is a prompt loop with neither |

## Evidence

- `service/src/runner.py` `run_loop` executes `python3 prepare.py && python3 train.py` and
  parses `val_bpb` with its own regex; it imports nothing from `autoresearch/engine/`.
- `autoresearch/engine/autoresearch/cli.py` exposes `init/run/status/report/doctor`; no
  module under `service/` references it.
- `service/` and `autoresearch/` are separate roots with separate packaging
  (`service/pyproject.toml`; the engine is unpackaged and reached by `sys.path` inserts).

## Impact

An adopter cannot point the REST/MCP service at real code, and cannot drive the engine
from an agent's slash command or an MCP client — "autoresearch as a service" is not
demonstrable from this template.

## Resolution

Code change + tests — PRD-20 (`docs/prd/20-autoresearch-as-a-service.md`): `service/`
folds into `autoresearch/service/` under one `autoresearch/pyproject.toml`; the service
re-founds on the engine; slash commands + an engine skill provide agent mode.
