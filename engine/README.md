# autoresearch engine

A script-owned keep/discard research loop you can point at real code.

The repo's examples carry a `val_bpb` toy loop with the keep/discard dance
copy-pasted per example. This engine generalises the loop itself: **the script,
not the agent, commits, measures and reverts**, so an agent is free to be
creative without ever owning the history of your repository.

* `verify` prints the metric — that number is the only thing that can win.
* `guard` must exit 0 — a candidate that breaks behaviour never gets a score.
* `scope` and `protected` files bound what an agent may touch.
* `noise_floor`, `repeats` and a median stop jitter from counting as progress.
* Four bounded stops plus a dry run mean a run cannot wander.
* Every outcome is appended to a replay-validated ledger.

Stdlib only, Python >= 3.11. Nothing to install.

## Commands

Run it through the wrapper (it sets `PYTHONPATH` for you):

```bash
engine/bin/autoresearch <command> [options]
```

or directly:

```bash
PYTHONPATH=engine python3 -P -m autoresearch <command> [options]
```

`-P` is not decoration: `python3 -m` puts the working directory first on
`sys.path`, so without it a repo-local `autoresearch.py` would be imported
instead of the engine. The wrapper already passes `-P`.

| Command | What it does |
|---|---|
| `init` | Validates the target repo, hashes the protected files, writes `.autoresearch/run.json`. |
| `run` | Runs iterations until a stop condition: agent → scope → protected → commit → guard → verify → keep\|revert. |
| `status` | Replay-validates `events.jsonl` and prints the run summary. |
| `report` | Writes `report.md` (with an EVIDENCE section) and `results.tsv`. |
| `doctor` | Prints each harness binary, its `--version`, and whether `OPENAI_API_KEY` is set (never its value). |

### init

```bash
engine/bin/autoresearch init \
  --repo . \
  --verify "python3 benchmark.py" \
  --guard  "python3 tests/run.sh --fast" \
  --metric-name val_bpb --direction lower \
  --scope src --scope benchmark.py \
  --target 0.90 --noise-floor 0.01 --repeats 3
```

| Flag | Default | Meaning |
|---|---|---|
| `--repo PATH` | `.` | Target repo. Must be a git repo on a named branch with a clean tree. |
| `--verify CMD` | required | Prints the metric (`METRIC name=1.5`, `name: 1.5`, or a bare final float). |
| `--metric-name NAME` | required | The token `parse_metric` looks for. |
| `--direction {lower,higher}` | required | Which way is better. |
| `--scope PREFIX` | required, repeatable | Repo-relative path prefix the agent may edit. No globs. Must exist, and must not be the repo root (`.`): a revert would then clean every untracked file. |
| `--guard CMD` | none | Must exit 0 for a candidate to be scorable. |
| `--target X` | none | Stop once the metric reaches it (inclusive). |
| `--noise-floor REL` | `0.01` | A candidate must beat the incumbent by this fraction to be kept. |
| `--repeats N` | `1` | Verify runs per candidate; the median is the metric. |
| `--verify-timeout S` | `600` | Bound on one verify run. On expiry the process group is killed, the pipe drain is bounded, and the pipes are closed — a forked helper that inherited stdout cannot extend it. |
| `--guard-timeout S` | `600` | Same bound for one guard run. |
| `--protect PATH` | — | Extra protected file (repeatable). |
| `--program FILE` | — | Standing instructions copied into every prompt. |
| `--goal TEXT` | — | One-line goal copied into every prompt and the report. |
| `--force` | off | Archive the existing run to `.autoresearch/archive/<ts>/` and start over. |

Protected files default to every file named as a path token in `--verify` and
`--guard` that exists in the repo, so `... --verify "python3 score.py"` protects
`score.py` without being asked. Each one is hashed into `run.json`; a candidate
that changes one is reverted.

`init` refuses a dirty tree, a detached HEAD, a scope that does not exist, a glob
in a scope, and an existing `run.json` without `--force`.

### run

```bash
engine/bin/autoresearch run --agent claude --model claude-sonnet-4-5 \
  --max-iterations 20 --record .autoresearch/replay.jsonl
```

| Flag | Default | Meaning |
|---|---|---|
| `--agent {claude,opencode,hermes,dsh,command,replay}` | required | Harness adapter. |
| `--model M` | — | Model flag for that harness. |
| `--agent-cmd CMD` | — | `command` adapter template; `{prompt_file}` and `{repo}` are substituted. |
| `--agent-arg ARG` | — | Extra argv appended to the adapter command (repeatable). |
| `--replay FILE` | — | `replay` adapter input: a `--record` file from an earlier run. |
| `--record FILE` | — | Append `{iteration, description, patch}` per iteration so the run is replayable. |
| `--max-iterations N` | `10` | Hard iteration bound (total, not per invocation). |
| `--plateau K` | `5` | Stop after K consecutive non-keeps. |
| `--max-wall S` | `0` (unlimited) | Wall-clock budget for this invocation. |
| `--agent-timeout S` | `900` | Hard bound on one agent run; a timeout kills the process group. |
| `--max-crashes C` | `3` | Stop after C consecutive `crash`/`agent_error` outcomes. |
| `--dry-run` | off | Validate everything, print the exact argv, run no agent, commit nothing, write no events. |
| `--json` | off | One JSON object per event on stdout. |

`--dry-run --json` is the exception to the one-object-per-event rule: it prints a
**single plan object** and exits 0 — `dry_run`, `metric`, `metric_name`,
`direction`, `argv`, `stops`. Nothing has iterated yet, so there are no events.

Per iteration: build prompt → run agent → scope → protected → commit → guard →
verify → keep or `git reset --hard`. A reject never leaves a trace in history:
`git clean -fd` is confined to the scope prefixes, and the untracked files the
agent created in that iteration (anywhere in the repo, `.autoresearch/`
excepted) are removed by name — including a symlink aimed outside the repo, and
ignored files it created inside the scope. Unrelated operator work is untouched:
pre-existing ignored files are fingerprinted before the agent runs and compared
after (a write to one is `scope_violation`, reason `ignored file changed`), never
deleted.

Artifacts are not the agent's edits: `git status` is snapshotted immediately
before the agent runs, so only the delta is attributed to it, and untracked files
that guard/verify create after a keep (a `results.json`, for instance) are swept
before the next iteration. `__pycache__/` and `*.pyc` are never a change.

Stops (recorded as the final `stop` event): `target`, `plateau`, `max_iterations`,
`max_wall`, `max_crashes`, `interrupted` (Ctrl-C, after restoring the incumbent).
Starting a stopped run again appends a `resume` event before it iterates, so the
ledger is a sequence of segments and each stop closes only its own.

Replay a recorded run anywhere — no harness needed:

```bash
engine/bin/autoresearch run --agent replay --replay .autoresearch/replay.jsonl --max-iterations 6
```

Start the replay at the recorded run's baseline commit. A record whose patch is
already in the tree (it reverses cleanly) is a no-op, so replaying from a
post-keep commit reports `no_change`; a patch that neither applies nor reverses,
and an iteration with no record at all, are both `agent_error` — a replay never
silently skips an iteration.

### status / report

```bash
engine/bin/autoresearch status          # replay-validates the ledger
engine/bin/autoresearch report          # writes .autoresearch/report.md + results.tsv
engine/bin/autoresearch report --out out/run.md
```

`status` exits 3 and names every violation when the ledger does not replay — a
`keep` that was not better than the incumbent, a broken sequence, an unknown
outcome, or a `stop` that is not last.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Stopped normally (any stop reason, including `interrupted`, `dry-run` and `doctor`). |
| `2` | Configuration or precondition error: dirty tree, missing run, scope missing, guard fails at baseline, verify prints no metric, HEAD not the incumbent, missing adapter binary. |
| `3` | Ledger invalid — `status`/`report`/`run` refuse to work from a history that does not replay. |

Ctrl-C is caught, never a traceback. Mid-run it restores the worktree to the
incumbent, appends an `interrupted` stop and exits `0`. During the baseline it
records **nothing** and still exits `0`: there is no incumbent to restore, and a
stop without a baseline would leave a ledger that cannot replay — the next
invocation simply measures the baseline again.

## Files

Everything lives under `<repo>/.autoresearch/`, which ignores itself via its own
`.gitignore` (`*`) so the loop never dirties the tree it measures.

| File | Written by | Contents |
|---|---|---|
| `run.json` | `init` | Immutable run config: commands, metric, scope, protected hashes. |
| `events.jsonl` | `run` | Append-only, fsync'd: `baseline`, `trial`, `stop`, and `resume` when a stopped run is started again. Each trial carries the capped (`4000` char) `log_tail` of the phase that decided it. |
| `results.tsv` | `report` | `iter, commit, metric, outcome, description`. |
| `report.md` | `report` | Goal, config, baseline vs best, trial table, EVIDENCE. |
| `last_agent.log` | `run` | Tail of the most recent agent output (capped at `4000` chars). |
| `prompt.txt` | `run` (command adapter) | The exact prompt handed to the agent. |
| `lock` | `run`, `init --force` | `flock` target: one run per repo; a second invocation exits `2`. |
| `archive/<ts>/` | `init --force` | The previous run's files. |

## Metric parsing

`parse_metric` accepts three shapes, in priority order:

```
METRIC val_bpb=0.9123     # (a) preferred
val_bpb: 0.9123           # (b)
0.9123                    # (c) last non-empty line, bare float
```

The **last** matching line wins, so a script may log a header value and then the
final one. A run with `--repeats N > 1` uses the median of N values.

## Security notes

* `verify` and `guard` are `shlex.split` and exec'd — never a shell. No
  `shell=True` anywhere in the engine.
* Every subprocess call carries a `timeout=`. A timeout kills the process group,
  and the drain after the kill is bounded too: a `setsid` grandchild that
  inherited stdout cannot stretch the timeout by holding the pipe. Ctrl-C kills
  the group before the interrupt propagates, so the loop never reverts the tree
  out from under a running child.
* **The agent's output is stored, and the prompt is visible.** Each trial's
  `log_tail` (last 4000 chars) is written to `events.jsonl` and the most recent
  one to `last_agent.log`; the description taken from its `CHANGE:` line is
  stripped of control characters, collapsed and capped at 120 chars before it
  becomes a commit subject or a report cell. Harness adapters pass the prompt in
  **argv**, so it is visible in `ps` to anyone on the host — the `command`
  adapter writes it to `prompt.txt` instead. Do not put a secret in a prompt.
* Measurement children run with an environment scrubbed of every variable whose
  **name** matches `(?i)(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)`. Agents get the
  full environment, because they need their credentials to run at all, and only
  `doctor` looks at a credential, printing `set`/`unset` and never a value.
* Commit identity is forced to `autoresearch <autoresearch@localhost>` so a run
  is attributable and never inherits the operator's git config.

## Tests

```bash
python3 -m pytest tests/unit/test_engine_*.py tests/integration/test_engine_*.py -q
```
