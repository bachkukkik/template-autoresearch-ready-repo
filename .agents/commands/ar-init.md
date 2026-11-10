---
description: "Init an autoresearch run: validate the target repo and record the run config (.autoresearch/run.json)"
argument-hint: "[--repo PATH] --verify CMD --metric-name NAME --direction lower|higher --scope PREFIX [--guard CMD]"
---

EXECUTE IMMEDIATELY. No preamble, no plan narration — run the commands and report.

## 1. Parse `$ARGUMENTS`

| Flag | Required | Rule |
|---|---|---|
| `--repo PATH` | no (default `.`) | Git repo, named branch, **clean tree** |
| `--verify CMD` | yes | Must print the metric — `METRIC name=1.5`, `name: 1.5`, or a bare float |
| `--metric-name NAME` | yes | The token the parser looks for |
| `--direction lower\|higher` | yes | Which way is better |
| `--scope PREFIX` | yes, repeatable | Repo-relative path; **no globs**, never `.` (a revert would wipe the tree) |
| `--guard CMD` | no | Must exit 0 before a candidate can score |
| `--protect FILE` | repeatable | Extra protected file (verify/guard paths are auto-protected) |
| `--target X` `--noise-floor R` `--repeats N` `--program F` `--goal TEXT` `--force` | no | Pass through unchanged |

Ask **once**, batched, for any required flag that is missing. Never invent a verify
command or a metric name: a wrong metric silently optimises the wrong thing.

## 2. Refuse before you run

- Dirty tree, detached HEAD, missing scope, or existing `run.json` → report and **stop**.
  Do **not** reach for `--force`; it archives someone else's run.
- Never point `--repo` at a checkout holding uncommitted work. The engine reverts, so the
  only work it may destroy is work it created.

## 3. Run the engine CLI

```bash
set -euo pipefail
AR="${AR:-autoresearch/engine/bin/autoresearch}"   # run from this repo root
"$AR" init --repo "$REPO" \
  --verify "$VERIFY" --metric-name "$NAME" --direction "$DIRECTION" \
  --scope "$SCOPE" ${GUARD:+--guard "$GUARD"} --goal "$GOAL"
```

Execute it as argv (array or explicit args). No `shell=True`, no `eval`.

## 4. Report

Show the command echoed, its exit code, and the parsed summary it prints. Exit `2` means a
precondition refused it — read the message, fix the precondition, do not bypass it.

Point at what exists now: `.autoresearch/run.json` (immutable config, protected-file
hashes). Nothing has run yet. Next: `/ar-run`, then `/ar-status` and `/ar-report`.

For a disposable target, `bash autoresearch/contract/examples/ex5-real-oss-speedup/setup.sh`
does a full init — copy that invocation's flags instead of guessing them.
