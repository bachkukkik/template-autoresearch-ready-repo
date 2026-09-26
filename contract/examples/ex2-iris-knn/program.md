# autoresearch — iris-knn example

Experiment: let the LLM do its own research on a tiny classical supervised
learning problem (Fisher's Iris, 150 rows), in the style of karpathy/autoresearch.
You edit exactly one file (`train.py`), never touch `prepare.py`, and record
every experiment in `results.tsv`.

This is the **direction-inverted** instantiation of the contract: ex1-music-abc
minimizes `val_bpb` (lower is better), this example **maximizes `accuracy`**
(higher is better). Everything else — one editable file, a frozen ground-truth
evaluator, an append-only ledger, keep-or-reset — is identical.

## Setup

1. **Run tag**: `autoresearch/<date>` branch from the base; must not exist.
2. **Read the in-scope files**: `README.md`, `prepare.py` (DO NOT MODIFY),
   `train.py`.
3. **Initialize results.tsv** with the header row
   `commit\taccuracy\tseconds\tstatus\tdescription`. Leave it untracked.

## Rules

**CAN:** modify `train.py` only — the classifier (k, distance metric, feature
scaling, voting scheme, per-class structure). Everything in-model is fair game.

**CANNOT:**
- Modify `prepare.py`. `evaluate_accuracy` is the ground truth — import it,
  never redefine it. (`loop_driver.py` asserts
  `train.evaluate_accuracy is prepare.evaluate_accuracy` and aborts otherwise.)
- Touch the split: `TRAIN`, `TEST`, the seed and the raw dataset are frozen in
  `prepare.py`. Re-splitting is metric tampering.
- Install packages. Stdlib only.
- Modify any other file.

**Goal: highest accuracy.** TIME_BUDGET=60s is fixed by prepare.py (a kNN run
here takes milliseconds; the budget bounds the search, not the fit).

**Simplicity criterion:** all else equal, simpler is better. A deletion that
holds the metric is a win.

**First run: baseline, as-is.**

## Loop

LOOP FOREVER:
1. Tune `train.py` with one idea; `git commit`.
2. `python3 train.py > run.log 2>&1`
3. `grep "^accuracy:" run.log` (empty → crashed: `tail -50 run.log`, fix or skip)
4. Append the row to results.tsv (crash: accuracy 0.000000, status crash).
5. **Strict improvement** (new > best) ⇒ keep the commit; else
   `git reset --hard HEAD~1`.

NEVER STOP. Do not ask the human whether to continue.

## Caveats

- Dataset is the real Fisher's Iris (150 rows), fetched from the seaborn-data
  mirror of the UCI archive and embedded verbatim in `prepare.py`; see
  `open_questions` in the parent report for the exact source URL.
- **Granularity:** the test split holds 45 rows, so one row = 0.0222 accuracy.
  A one-row "win" is one example, not a trend — treat anything under ~0.04 as
  noise and prefer the simpler model on a tie.
- **Goodhart:** the frozen metric is a single fixed split. Anything that reads
  `TEST` inside `train.py` (peeking at the labels, tuning on the test set) is
  cheating the metric, not improving the classifier. Only `TRAIN` may inform
  the model; `evaluate_accuracy` is the judge, never the optimizer.
- **Scaling trap (found by the first run of this example):** the z-score
  candidate originally scored 0.3778 because the features were standardized for
  the *training* set but the query vector was left raw, so every distance was
  measured in mismatched units. If you add any feature scaling, apply the SAME
  train-only transform to the query. Check the accuracy number against the
  no-scaling variant before trusting a large drop — a wide-miss score usually
  means a unit bug, not a genuinely worse classifier.
- **Direction inversion:** unlike ex1, "improvement" means the number goes
  **up**. A `keep` here is a strictly greater accuracy; equal accuracy is a
  `discard` (and by the simplicity criterion, ties go to the existing commit).
