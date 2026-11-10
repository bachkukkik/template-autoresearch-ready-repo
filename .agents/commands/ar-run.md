---
description: "Run the autoresearch keep/discard loop with a harness agent, a replay record, or a local command adapter"
argument-hint: "--agent claude|opencode|hermes|dsh|replay|command [--model M] [--max-iterations N] [--max-wall S] [--dry-run]"
---

EXECUTE IMMEDIATELY. Bounded by default — never launch an unbounded run.

## 1. Parse `$ARGUMENTS`

| Flag | Rule |
|---|---|
| `--agent` | Required. `claude` `opencode` `hermes` `dsh` (local harness), `replay` (needs `--replay FILE`), `command` (needs `--agent-cmd`) |
| `--model M` | Passed to that harness |
| `--replay FILE` | A `--record` JSONL from an earlier run — no harness needed |
| `--agent-cmd CMD` | `{prompt_file}` / `{repo}` substituted; **local throwaway targets only** |
| `--max-iterations N` | Default small (`3`–`10`). Total, not per invocation |
| `--max-wall S` | Seconds for this invocation. Always set one on a first run |
| `--plateau K` `--agent-timeout S` `--max-crashes C` `--record FILE` `--json` | Pass through |

If `--agent` is missing, ask once. Do not default to `claude`.

## 2. Choose the agent

- Documented harness installed (`claude`, `opencode`, `hermes`, `dsh`) → that one.
  Unknown binary exits `2` — check with `"$AR" doctor` first.
- Reproducing a recorded run → `--agent replay --replay .autoresearch/replay.jsonl`.
- `--agent command` runs **arbitrary shell** as the agent. Local, disposable targets only.
  Never on a shared host, never with a credential in the template.

**API / MCP callers must not use this command.** They go through the service allowlist —
`POST /api/v1/runs`, `GET /api/v1/runs/{job_id}`, `.../report`, `DELETE .../{job_id}` and
the MCP `run_*` tools — which bounds the agent set and runs on a per-job copy of a bundled
workload. A slash command is the human, local surface.

## 3. Dry run first

```bash
set -euo pipefail
AR="${AR:-autoresearch/engine/bin/autoresearch}"
"$AR" run --repo "$REPO" --agent "$AGENT" ${MODEL:+--model "$MODEL"} --dry-run
```

It prints the exact argv and stops. Read it; only then drop `--dry-run` and add the bounds.

## 4. Run it

```bash
"$AR" run --repo "$REPO" --agent "$AGENT" \
  --max-iterations "${MAX_ITER:-5}" --max-wall "${MAX_WALL:-900}" --record .autoresearch/replay.jsonl
```

Execute as argv. No `shell=True`, no `eval`. Ctrl-C is safe: it restores the incumbent and
appends an `interrupted` stop, exit `0`.

## 5. Report

Per iteration the script — not the agent — commits, guards, verifies, then keeps or
reverts. Report: iterations run, the stop reason (`target`, `plateau`, `max_iterations`,
`max_wall`, `max_crashes`, `interrupted`), baseline vs best metric, and the ledger path
`.autoresearch/events.jsonl`. Results: `/ar-status`, `/ar-report`. Never `git push`.
