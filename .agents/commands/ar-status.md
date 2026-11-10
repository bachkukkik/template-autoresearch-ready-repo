---
description: "Replay-validate the autoresearch ledger and summarise the run (iterations, keeps, stop reason)"
argument-hint: "[--repo PATH] [--json]"
---

EXECUTE IMMEDIATELY. Read-only: `status` writes nothing.

## 1. Parse `$ARGUMENTS`

- `--repo PATH` — target repo, default `.`
- `--json` — one machine-readable object instead of the summary

## 2. Precondition

`<repo>/.autoresearch/run.json` must exist (it comes from `/ar-init`). If not, `status` exits
`2` with `no run configured` — report that and point at `/ar-init`; do not invent a summary.
With a config but no ledger yet, `status` exits `0` and says `stop incomplete`, `0
iteration(s)` — that is a correct answer: initialised, never run. Say exactly that.

## 3. Run

```bash
set -euo pipefail
AR="${AR:-autoresearch/engine/bin/autoresearch}"
"$AR" status --repo "$REPO"
```

Execute as argv. No `shell=True`, no `eval`.

## 4. Read the result

| Exit | Meaning | Action |
|---|---|---|
| `0` | Ledger replays (or the run has not iterated yet) | Report the summary, word for word |
| `2` | No run / bad precondition | Point at `/ar-init` |
| `3` | Ledger does **not** replay | Report **every** violation the command names, verbatim, and stop — do not run, report or resume on top of it |

A violation is a real finding: a `keep` that was not better than the incumbent, a broken
sequence, an unknown outcome, or a `stop` that is not last. The ledger is the evidence; a
hand-edited or interrupted one is not trustworthy, and `run`/`report` refuse it too.

## 5. Report

Show: baseline metric, best metric and its iteration, keeps / trials, the stop reason, and
the ledger path `.autoresearch/events.jsonl`. Add the last `last_agent.log` tail only if the
user asks why the final iteration failed. Next: `/ar-report` for the written report.
