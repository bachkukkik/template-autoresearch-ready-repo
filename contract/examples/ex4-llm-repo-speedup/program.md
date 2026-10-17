# autoresearch -- ex4-llm-repo-speedup

Experiment: let a LIVE LLM agent do its own research on a small **software
repo**, in the style of karpathy/autoresearch. You edit exactly one file
(`target/solution.py`), never touch `prepare.py` or `target/tests.py`, and every
experiment is recorded in `results.tsv`.

This is the template's main use case: an agent proposing edits to real code,
scored by that code's **test suite** plus a **speed metric**, where the fixed
`TIME_BUDGET` genuinely stops a candidate.

## Setup

1. **Run tag**: `autoresearch/ex4-<date>` branch from the base; must not exist.
2. **Read the in-scope files**: `README.md`, `target/README.md` (the module
   contract), `prepare.py` (DO NOT MODIFY), `target/tests.py` (DO NOT MODIFY),
   `target/solution.py` (yours), this file.
3. **Initialize results.tsv** with the header row
   `commit / median_seconds / gate / stop_reason / status / tokens / description`
   (tab-separated). Leave it to the driver: `agent_driver.py` writes it.

## The three roles (never merged)

| Role | Files | Mutable |
|---|---|---|
| frozen evaluator | `prepare.py` + `target/tests.py` | no |
| human policy | `program.md` | authored once |
| agent artifact | `target/solution.py` | **yes -- the one edited file** |

## Rules

**CAN:** rewrite anything inside `target/solution.py` -- data structures, the
tokenizing/grouping strategy, short-circuits, helper layout.

**CANNOT:**
- Modify `prepare.py` or `target/tests.py`. They own the workload, the oracle,
  the metric and `TIME_BUDGET`.
- Reference the frozen truth. `prepare.py` screens the candidate source and
  rejects any artifact that imports the evaluator (`import prepare` /
  `from prepare`) to reach its held-out oracle.
- Forge the result. The candidate runs inside the child process, so nothing it
  asserts is trusted: the child reports only the raw OUTPUTS of `run()` for the
  inputs it was given, and the parent recomputes `reference(...)` itself and
  compares. A verdict the candidate writes into the results file — a fake
  `gate: ok`, a `median` of `1e-06` — is never the number the ledger records: an
  unrecognised record is ignored, and a wrong output is a failed gate.
- Read the caller's environment. The evaluated child runs with a scrubbed
  environment (no API keys), and a budget kill takes its whole process group.
- Pretend to be fast. The benchmark seeds are chosen by the parent with
  `secrets` and handed over only after the child reports it has imported the
  candidate, so a workload precomputed at import, or an answer cached across
  reps, is worthless.
- Install packages. Stdlib only.
- Modify any other file.

## Goal

**LOWEST median seconds per `run(items)` call -- SUBJECT to the correctness
gate.** The gate is decided by the PARENT, never asserted by the child: the child
sends back the raw outputs of `run()` on a held-out workload the code never saw
and on the timed workloads, and the parent recomputes `prepare.reference(...)`
and compares. `target/tests.py` still runs in the child as a cheaper first check.
A failing gate makes the candidate **invalid** (recorded `crash`): a
faster-but-wrong run is never a keep.

`prepare.TIME_BUDGET` is a **ceiling, not a target**: one evaluated run is a
single subprocess with a HARD wall-clock limit of `TIME_BUDGET` seconds, and the
evaluator kills it at that limit (`stop_reason: budget`, `median_seconds: inf`,
recorded `timeout`). The shipped baseline is quadratic and takes many times the
budget, so the very first row of the ledger is a budget stop -- the budget binds
by construction. A correct candidate that is merely *slow* is killed too, so
"fits under the budget, then faster" is the whole game.

**Simplicity criterion:** all else equal, simpler is better. A candidate that
deletes code and holds the metric is a win.

**Rejection rule (evaluator-owned, never the model):**

- gate failed -> `crash` (invalid), `git reset`.
- gate passed and median **strictly** below the incumbent -> `keep`.
- budget kill -> `timeout`, `git reset`.
- otherwise -> `discard`, `git reset --hard HEAD~1`.

`incumbent` starts at `inf` (the baseline never finished), so the first valid
candidate that fits the budget is the first keep.

## Loop

The driver (`agent_driver.py`) runs it: for each round it builds a prompt from
this policy file + the current artifact + the ledger tail + the last run log
tail, asks the model for the **complete** new file in one fenced block, commits,
runs `prepare.py` under the budget, records the row, and keeps or resets.

```bash
# in a DISPOSABLE scratch copy of this directory (never in the template checkout:
# the driver refuses unless this directory is the git root, because it resets hard)
git init -q && git add -A && git commit -qm "contract: baseline"
rm -f results.tsv        # a LIVE run starts from an empty ledger
python3 agent_driver.py --from-baseline --rounds 8        # LIVE: calls the model
python3 agent_driver.py --from-baseline --replay transcript.jsonl   # no network
```

NEVER STOP mid-run: do not ask the human whether to continue.

## Caveats

- The workload is a seeded procedural corpus (`prepare.py`), an honest stand-in
  for a real hot-path over a string list. Results characterize the loop, the
  gate and the budget, not a production pipeline.
- **The gate is the metric.** Speed alone is trivially gameable: sampling a
  prefix, caching a previous answer, or dropping the `(-count, value)` tie-break
  all "win" on speed and all fail the gate. Each timed rep's workload is built
  from a seed the **parent** draws with `secrets` after the child's import
  handshake (`BENCH_REPS` distinct workloads, median over reps), so memoizing one
  answer buys nothing and a workload precomputed at import time is empty; the
  parent's own held-out comparison blocks dataset-specific shortcuts; and the
  source screen blocks reaching into the oracle.
- **The speed number is still measured inside the candidate's process.** The
  correctness signal is parent-verified and cannot be forged, but `run()`'s
  timing is a `time.perf_counter` delta the child reports, so a hostile candidate
  that patches the clock could understate it. The parent rejects only what the
  wall clock it measured cannot have produced (a `median * BENCH_REPS` above the
  bench phase, or a non-positive median). Treat a live loop's timing as a T2
  field and run it only in a disposable sandbox.
- Timing is a **T2 statistical field**: a wall-clock delta within ~10% is not
  signal. The replay compares the gate / stop_reason / description columns, never
  `median_seconds`.
- `TIME_BUDGET` is platform-bound. Record the budget with any claim.
