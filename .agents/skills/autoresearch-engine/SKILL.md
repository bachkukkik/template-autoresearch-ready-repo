---
name: autoresearch-engine
description: "Drive the repo-native autoresearch engine binary — the script-owned keep/discard loop that commits, guards, verifies and reverts. Use for 'run the autoresearch engine', 'optimize X with autoresearch', '/ar-init', '/ar-run', '/ar-status', '/ar-report', or to set up a keep/discard loop on a real repo."
license: MIT
---

# autoresearch engine

The **engine** is a stdlib-only Python CLI at `autoresearch/engine/` that owns the loop
machinery: it builds a prompt, runs an agent, enforces scope and protected files, commits,
runs `guard`, runs `verify`, then keeps or `git reset --hard`s. The agent never owns the
git history.

## This skill vs the vendored `autoresearch` skill

| | `.agents/skills/autoresearch/` (vendored, upstream) | **this skill** |
|---|---|---|
| What it is | A prompt-driven **methodology** — plan/debug/fix/security/ship subcommands, the agent does the loop by hand | A **binary** — `bin/autoresearch` executes the loop deterministically and writes a replay-validated ledger |
| Loop ownership | The agent edits, measures and reverts | The **script** edits-adjacent: commits, verifies, reverts |
| Evidence | Run logs under `autoresearch/<sub>-<stamp>/` | `.autoresearch/events.jsonl` (fsync'd, replay-validated), `report.md` with an EVIDENCE section |
| Use when | You want a goal decomposed into experiments and the agent doing the work | You want a repeatable, auditable optimisation loop on a real repo with a hard revert |

They compose: use the vendored skill to *design* the experiment (scope, metric, direction,
guard), the engine to *run* it. Slash commands `/ar-init`, `/ar-run`, `/ar-status`,
`/ar-report` (canonical files in `.agents/commands/`) wrap the engine.

## Invocation

```bash
autoresearch/engine/bin/autoresearch {init,run,status,report,doctor}
# equivalent, no wrapper:
PYTHONPATH=autoresearch/engine python3 -P -m autoresearch <command>
```

`-P` matters: without it `python3 -m` imports a repo-local `autoresearch` package instead
of the engine. A run needs a `run.json` from `init`; `status`/`report` need a ledger.

## init — record the run config

```bash
# 1. the bundled real-repo example: copies ex5 to $TMPDIR/ex5, git-inits it, inits the engine
bash autoresearch/contract/examples/ex5-real-oss-speedup/setup.sh "$TMPDIR/ex5"

# 2. by hand, on your own repo (clean tree, named branch)
autoresearch/engine/bin/autoresearch init --repo . \
  --verify "python3 bench.py" --guard "python3 tests/run.sh --fast" \
  --metric-name seconds --direction lower --scope src --target 0.90 --repeats 3

# 3. re-init an existing run (archives the old one to .autoresearch/archive/<ts>/)
autoresearch/engine/bin/autoresearch init --repo . ... --force
```

`verify` must print the metric (`METRIC name=1.5`, `name: 1.5`, or a bare final float).
`scope` is a repo-relative prefix: no globs, never `.`.

## run — bounded by default

```bash
# 1. a local harness, small bound, record for replay
autoresearch/engine/bin/autoresearch run --agent claude --model claude-sonnet-4-5 \
  --max-iterations 5 --max-wall 900 --record .autoresearch/replay.jsonl

# 2. replay a recorded run anywhere, no harness installed: needs a --record JSONL
autoresearch/engine/bin/autoresearch run --agent replay --replay .autoresearch/replay.jsonl

# 3. see the exact argv and change nothing
autoresearch/engine/bin/autoresearch run --agent opencode --dry-run --json
```

Agents: `claude`, `opencode`, `hermes`, `dsh` (whichever binary is installed),
`replay` (a records file), `command` (an arbitrary shell template). Stops: `target`,
`plateau`, `max_iterations`, `max_wall`, `max_crashes`, `interrupted`.

## status / report — the evidence

```bash
autoresearch/engine/bin/autoresearch status            # replay-validates events.jsonl
autoresearch/engine/bin/autoresearch status --json     # one object, for a script
autoresearch/engine/bin/autoresearch report            # .autoresearch/report.md + results.tsv
autoresearch/engine/bin/autoresearch report --out out/run.md
```

Exit codes: `0` ok · `2` precondition/config (dirty tree, no run, scope missing, guard
fails at baseline, no metric) · `3` ledger does not replay — `run`/`report` refuse it.

## Safety invariants

- **The script owns git.** Never commit, amend or reset on its behalf; a rejected candidate
  is reverted by `git reset --hard` and `git clean -fd` confined to the scopes.
- **Never point it at a repo with uncommitted work.** `init` refuses a dirty tree; do not
  work around that refusal. The only work the loop may destroy is work it created.
- **`--agent command` is local, throwaway-target only** — it runs an arbitrary shell
  command as the agent. Never on a shared host, never with a credential in the template,
  never against a repo you would miss.
- **Never push, publish or open a PR** from a run. The operator decides what ships.
- Do not put a secret in a prompt: harness adapters pass it in `argv`, visible to `ps`.
- One run per repo (`flock` on `.autoresearch/lock`); never delete the file to force a
  second one — that breaks the ledger's segments.

## Agent-less surfaces (API callers)

An API, MCP client or CI job must **not** shell out to this binary. Go through the service
(PRD-20), which bounds the agent allowlist and runs on a per-job copy of a bundled workload:
`POST /api/v1/runs`, `GET /api/v1/runs/{job_id}`, `GET /api/v1/runs/{job_id}/report`,
`DELETE /api/v1/runs/{job_id}`, plus the MCP `run_start` / `run_status` / `run_report` /
`run_cancel` tools. See `autoresearch/service/README.md`.

## Reference

`autoresearch/engine/README.md` — every flag, the metric parser, the ledger format, the
security notes and the exit codes. `docs/prd/17-harness-pluggable-engine.md`.
