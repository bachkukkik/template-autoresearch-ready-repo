# autoresearch — music-abc example

Experiment: let the LLM do its own research on a tiny ABC sheet-music corpus,
in the style of karpathy/autoresearch. You edit exactly one file (`train.py`),
never touch `prepare.py`, and record every experiment in `results.tsv`.

## Setup

1. **Run tag**: `autoresearch/<date>` branch from the base; must not exist.
2. **Read the in-scope files**: `README.md`, `prepare.py` (DO NOT MODIFY),
   `train.py`.
3. **Initialize results.tsv** with the header row
   `commit\tval_bpb\tseconds\tstatus\tdescription`. Leave it untracked.

## Rules

**CAN:** modify `train.py` only — model structure, smoothing, interpolation,
context handling. Everything in-model is fair game.

**CANNOT:**
- Modify `prepare.py`. `evaluate_bpb` is the ground truth — import it, never
  redefine it.
- Install packages. Stdlib only.
- Modify any other file.

**Goal: lowest val_bpb.** TIME_BUDGET=60s is fixed by prepare.py.

**Simplicity criterion:** all else equal, simpler is better. A deletion that
holds the metric is a win.

**First run: baseline, as-is.**

## Loop

LOOP FOREVER:
1. Tune `train.py` with one idea; `git commit`.
2. `python3 train.py > run.log 2>&1`
3. `grep "^val_bpb:" run.log` (empty → crashed: `tail -50 run.log`, fix or skip)
4. Append the row to results.tsv (crash: val_bpb 0.000000, status crash).
5. Strict improvement ⇒ keep the commit; else `git reset --hard HEAD~1`.

NEVER STOP. Do not ask the human whether to continue.

## Caveats

- Corpus is a seeded procedural stand-in for real ABC (see README.md) —
  results characterize the loop, not sheet-music modelling.
- Goodhart: the frozen metric can be gamed by degenerate distributions;
  inspect the model's sampled output (sample a tune from the model) before
  trusting a large win that came from a weird change.
