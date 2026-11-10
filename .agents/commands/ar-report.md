---
description: "Write the autoresearch report.md (with EVIDENCE) and results.tsv from the validated ledger"
argument-hint: "[--repo PATH] [--out PATH]"
---

EXECUTE IMMEDIATELY. Writes only the report files; never edits the target's history.

## 1. Parse `$ARGUMENTS`

- `--repo PATH` — target repo, default `.`
- `--out PATH` — where `report.md` lands; default `<repo>/.autoresearch/report.md`

## 2. Precondition

The ledger must replay. `report` refuses a non-replaying ledger (exit `3`) and a missing run
(exit `2`). If `/ar-status` has not been run in this session, run it first and report its
verdict — a report over a bad ledger is a fabricated result.

## 3. Run

```bash
set -euo pipefail
AR="${AR:-autoresearch/engine/bin/autoresearch}"
"$AR" report --repo "$REPO" ${OUT:+--out "$OUT"}
```

Execute as argv. No `shell=True`, no `eval`.

## 4. Show

Print the written paths and then the report's own contents, in this order:

1. **Goal** — the `--goal` text the run was initialised with.
2. **Config** — verify, guard, scope, metric, direction, noise floor, repeats.
3. **Baseline vs best** — the two numbers and the delta; the only claim that can win.
4. **Trial table** — `iter, commit, metric, outcome, description` from `results.tsv`.
5. **EVIDENCE** — the recorded commands and their output tails. Quote it; never paraphrase
   a metric.

Files: `<repo>/.autoresearch/report.md`, `<repo>/.autoresearch/results.tsv` (or `--out`).

## 5. Close out

State plainly whether the run met its `--target`: yes / no / no target set. A run that
plateaued is a result, not a failure — say which stop reason ended it. Do **not** push,
open a PR, or commit on the target's behalf; the engine already owns that history and the
operator decides what ships.
