# autoresearch — ex3-hotpath-speedup

Experiment: let the agent do its own research on a fixed **hot-path workload**
(a 12 MB document → eight aggregate statistics), in the style of
karpathy/autoresearch. You edit exactly one file (`train.py`), never touch
`prepare.py`, and record every experiment in `results.tsv`.

This is the **non-ML** instantiation of the contract: the objective is not a
model metric but **wall-clock time of a pure function**, and the guard against
Goodhart is an **exact-output gate** — the candidate's result must equal the
frozen reference result, dict-for-dict, before its speed is allowed to count.

## Setup

1. **Run tag**: `autoresearch/<date>` branch from the base; must not exist.
2. **Read the in-scope files**: `README.md`, `prepare.py` (DO NOT MODIFY),
   `train.py`, `program.md` (this file).
3. **Initialize results.tsv** with the header row
   `commit\tmedian_seconds\tgate\tstatus\tdescription`. Leave it untracked.

## Rules

**CAN:** modify `train.py` only — data-passes, tokenization, containers,
short-circuits, helper structure. Everything in-workload is fair game.

**CANNOT:**
- Modify `prepare.py`. It owns the workloads and the frozen reference result —
  import from it, never redefine or reach into it.
- Name `EXPECTED_OUTPUT` / `run_reference` anywhere in `train.py`: the
  evaluator screens the module source for those names and rejects the
  candidate (returning the frozen truth is not a solution, it is cheating).
- Install packages. Stdlib only.
- Modify any other file.

**Goal: LOWEST median seconds per `run(data)` call — SUBJECT TO the
exact-output gate.** `gate_ok: True` and `median_seconds` both come from
`prepare.evaluate(train_module)`; `TIME_BUDGET=60` is fixed by prepare.py.

**Gate first, speed second.** A candidate whose `run(data)` does not reproduce
the frozen result exactly is **invalid** (`train.py` exits 2, the ledger
records `crash`). A faster-but-wrong run is a crash, never a keep — the median
of a rejected candidate is a single-rep diagnostic only, kept in the ledger so
the failure is visible, and it is not eligible to become the incumbent.

**Simplicity criterion:** all else equal, simpler is better. A deletion that
holds the metric is a win. Where the ledger's strict-improvement rule and the
simplicity criterion disagree, the ledger rules (a tie is a `discard`) — the
tension is recorded, not hidden.

**Rejection rule (keep/discard):**
- `gate_ok: False` → `crash` (invalid), `git reset`.
- `gate_ok: True` and median **strictly** below the incumbent → `keep`.
- otherwise → `discard`, `git reset --hard HEAD~1`.

**First run: baseline, as-is.**

## Loop

LOOP FOREVER:

1. Change `train.py` with one idea; `git commit`.
2. `python3 train.py > run.log 2>&1` (exit 0/2/3 = ok / gate failed / over
   budget).
3. `grep -E "^(median_seconds|gate_ok):" run.log` (empty → crashed:
   `tail -50 run.log`, fix or skip).
4. Append `commit\tmedian_seconds\tgate\tstatus\tdescription` to results.tsv
   (crash: `-1.000000` median if nothing was measured).
5. Strict improvement under a passing gate ⇒ keep the commit; else
   `git reset --hard HEAD~1`.

NEVER STOP. Do not ask the human whether to continue.

## Caveats

- The workload is a seeded procedural document (see `prepare.py` and
  `README.md`) — an honest stand-in for a real hot-path text workload. Results
  characterize the loop and the gate, not a production pipeline.
- **The gate is the metric.** Wall-time alone is trivially gameable: sampling a
  prefix, caching a previous answer, skipping an aggregate, or dropping the
  lexicographic tie-break in `top50` all "win" on speed and all crash on the
  gate. `prepare.py` also checks a held-out workload and uses a fresh copy of
  the input per timed rep, so identity-keyed caches and dataset-specific
  shortcuts are rejected too.
- The frozen reference implementation is itself near the practical floor for
  this workload on CPython (one regex scan + C-level counting), so the
  achievable speedup is bounded by `baseline ÷ floor`; a candidate that goes
  much below the reference median should be suspected of a gate hole and
  investigated before it is trusted.