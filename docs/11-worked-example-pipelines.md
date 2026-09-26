# 11 — Worked Example Pipelines

## What

Three complete instantiations of the autoresearch contract, one per objective
shape, living under `contract/examples/`: `ex1-music-abc` (minimize a language-model
loss), `ex2-iris-knn` (maximize a classifier accuracy), and `ex3-hotpath-speedup`
(minimize wall-clock time under an exact-output gate). A single self-contained
`dashboard.html` visualizes all three progression ledgers.

## Why

- **The contract in `docs/02-autoresearch-contract.md` is stated; a worked run proves
  it runs.** Each example carries the whole contract — human policy, frozen evaluator,
  the one agent-edited file, a keep/discard ledger and the loop driver that produced
  it — so a reader can reproduce a real optimization trajectory, not a description of
  one.
- **One direction is not enough to test a loop.** A keep/discard rule can be right for
  a minimization and silently wrong for a maximization; a gate that measures a scalar
  can pass a candidate that a structural gate must reject. Three objectives on one
  contract expose those asymmetries.
- **The loop's own failure modes only appear when it runs.** A mutation that never
  fires, a crash that is discarded but not reset, a simplification blocked by strict
  improvement — none are visible from the template alone. Running the loop three times
  surfaced each and fixed it.

## How

### The three instantiations

| # | Directory | Objective (direction) | Baseline → Best | Candidates (K/D/C) | Proves |
|---|---|---|---|---|---|
| 1 | `contract/examples/ex1-music-abc` | `val_bpb` ↓ (ABC sheet-music LM, procedural stand-in corpus per the transcript-corpus topic) | 3.765056 → **2.178535** (−42.1%) | 6 (4/2/0) | a text domain; the frozen evaluator; keep/discard/reset |
| 2 | `contract/examples/ex2-iris-knn` | `accuracy` **↑** (real seaborn-mirror iris, embedded byte-identical) | 0.933333 → **1.000000** | 7 (3/4/0) | direction inversion; the frozen-evaluator object-identity guard |
| 3 | `contract/examples/ex3-hotpath-speedup` | median seconds ↓ + exact-output gate (non-ML, 2,000,000-token workload) | 2.310 s → **0.275 s** (8.41×) | 11 (9/1/1) | an anti-Goodhart gate rejects a ≈10×-faster wrong answer |

### Anatomy of a faithful instance

Every example directory carries the same five artifacts, plus a README:

| File | Role | Mutable by the loop |
|---|---|---|
| `program.md` | human policy: run tag, CAN/CANNOT rules, the goal | no — authored once |
| `prepare.py` | **FROZEN** evaluator and workloads | no — importing, never redefining, is the contract |
| `train.py` | the candidate being optimized | **yes — the only edited file** |
| `loop_driver.py` | the mechanical loop: apply patch → commit → run → parse metric → keep or reset | no |
| `results.tsv` | the keep/discard ledger | vendored once as the record |

`loop_driver.py` applies each candidate as an ordered patch list against the current
kept state, commits it, runs the objective, parses the metric from the run log, and
either keeps (a strict improvement) or `git reset --hard HEAD~1`. On a discard the next
patch set chains from the last kept file, which is exactly the karpathy loop.

### Ledger shape

| Example | Ledger columns | Rows | keep / discard / crash |
|---|---|---|---|
| ex1-music-abc | `commit val_bpb seconds status description` (no header line) | 6 | 4 / 2 / 0 |
| ex2-iris-knn | `commit accuracy seconds status description` | 7 | 3 / 4 / 0 |
| ex3-hotpath-speedup | `commit median_seconds gate status description` | 11 | 9 / 1 / 1 |

`results.tsv` is **runtime state, vendored here ONCE as the record of the worked
run.** It is not appended to in place: re-running `loop_driver.py` in a scratch clone
produces a fresh ledger, and its `seconds` column (a T2 statistical field — T2 =
statistical tier: values jitter between runs and never gate; see
`kb/concepts/better-cheaper-faster-metrics.md`) jitters between runs. Each example
README embeds the run's git history verbatim; the live scratch clones are gitignored
stage-1 scratch and are never cited.

### The frozen evaluator, three ways

- **ex1** imports `evaluate` from `prepare.py`; the baseline starts at a unigram
  add-alpha model and the loop moves to bigram interpolation and a lighter backoff.
- **ex2** imports `evaluate_accuracy` and states the rule in `program.md`:
  `loop_driver.py` asserts `train.evaluate_accuracy is prepare.evaluate_accuracy` and
  aborts with `CONTRACT VIOLATION` otherwise. Redefining the evaluator in `train.py`
  fails that identity check before any candidate runs.
- **ex3** goes further: `prepare.py` owns a frozen `EXPECTED_OUTPUT` reference, and the
  evaluator screens the `train.py` module source for the names `EXPECTED_OUTPUT` and
  `run_reference`, rejecting a candidate that reaches into the ground truth.

### The exact-output gate (ex3)

ex3's objective is wall-clock time, but a candidate's speed counts only after
`run(data)` equals the frozen reference dict-for-dict. The ledger's `gate` column is
`ok` or `invalid`; a gate failure is recorded as `crash` (invalid), never a keep. The
final ledger row is a labeled attack — aggregating only the first 10% of the document
— which is ≈10× faster than the incumbent (0.027475 s vs 0.274679 s) and rejected by
the gate.

### Dashboard

`contract/examples/dashboard.html` is one self-contained file (inline `RUNS` data, no
JavaScript dependencies) rendering the progression of all three ledgers, coloring
keep / discard / crash / best, and reading every value from the vendored
`results.tsv` files.

## Verification

Run from the repo root, 2026-09-26.

```bash
ls contract/examples/
# README.md  dashboard.html  ex1-music-abc  ex2-iris-knn  ex3-hotpath-speedup

ls contract/examples/ex1-music-abc/
# README.md  loop_driver.py  prepare.py  program.md  results.tsv  train.py

wc -l contract/examples/ex*/results.tsv
#   6 contract/examples/ex1-music-abc/results.tsv
#   8 contract/examples/ex2-iris-knn/results.tsv
#  12 contract/examples/ex3-hotpath-speedup/results.tsv
#  26 total

(cd contract/examples/ex1-music-abc && python3 train.py 2>/dev/null | grep val_bpb)
# val_bpb:          2.178535

(cd contract/examples/ex2-iris-knn && python3 train.py 2>/dev/null | grep '^accuracy:')
# accuracy:         1.000000

(cd contract/examples/ex3-hotpath-speedup && python3 train.py 2>/dev/null | grep -E 'median_seconds|gate_ok')
# median_seconds: 0.291148   # representative run; timing jitters (~0.29 ±0.01)
# gate_ok: True

(cd contract/examples/ex2-iris-knn && python3 -c "import loop_driver; loop_driver.assert_frozen_evaluator()")
# contract ok: train.evaluate_accuracy is prepare.evaluate_accuracy (train=105 test=45 seed=23)

grep -c "dot" contract/examples/dashboard.html
# 7        (inline data + legend rendering present; 7,697 bytes)
```

The frozen-evaluator guard is falsifiable, verified directly:
redefining `evaluate_accuracy` in `train.py` and calling
`loop_driver.assert_frozen_evaluator()` prints
`CONTRACT VIOLATION: train.evaluate_accuracy is not prepare.evaluate_accuracy`; the
untouched `train.py` prints
`contract ok: train.evaluate_accuracy is prepare.evaluate_accuracy (train=105 test=45 seed=23)`.

## What Works

- **One contract, three objective shapes.** ex1 (lower-is-better `val_bpb`), ex2
  (higher-is-better `accuracy`) and ex3 (wall-time under a gate) each run the same
  `program.md` / `prepare.py` / `train.py` / `loop_driver.py` / `results.tsv` contract
  with only the direction and the gate changed.
- **The frozen evaluator is enforceable, not advisory.** ex2's object-identity
  assertion aborts the driver on a redefinition, and ex3's source screen rejects a
  candidate that names the ground-truth symbols — both fail before a metric is
  reported.
- **The exact-output gate defeats Goodharting.** ex3's attack candidate is ≈10× faster
  and is recorded as an invalid crash, so the incumbent (0.274679 s, the fastest
  *valid* row) keeps its place.
- **Direction inversion is real, not cosmetic.** ex2 maximizes accuracy while ex1/ex3
  minimize, and the loop's comparison, ledger and keep/reset rule hold against `>`
  exactly as against `<`.
- **A zero-headroom split is a recorded decision, not tampering.** ex2's `prepare.py`
  documents that the seed-42 split had no headroom (the 1-NN baseline WAS the kNN-family
  ceiling at 0.977778 = 44/45), records the seeds 0–39 scan, and freezes seed 23.
- **The dashboard is portable.** `dashboard.html` carries its data inline and loads no
  external script, so it renders offline from the vendored ledgers.
- **Every documented run is reproducible from the tracked copy.** `python3 train.py` on
  each example prints the ledger's best metric — 2.178535 / 1.000000 / gate_ok True —
  from the shipped `train.py`.

## What Fails

- **A mutation that never fires is indistinguishable from a failed candidate.** An
  anchor bug that patches the wrong site (ex1) leaves the metric identical to the
  incumbent, which a strict-improvement rule mechanically discards.
- **A crash that only discards leaves HEAD on the broken commit.** ex3's first driver
  reset on a discard but not on a crash, so the tree could end on the broken candidate.
- **Strict improvement rejects a simplification that costs nothing.** ex3's dead-code
  deletion (candidate 10) lost by 0.8% (0.276896 s vs 0.274679 s) and was discarded even
  though the code shrank.
- **A spot-check gate is not shape-proof.** ex3's attack candidate passed the first
  spot-check field and still failed the full-output comparison — a field-sample gate
  would have kept a badly wrong answer.
- **A split with zero headroom turns the loop into a no-op.** On ex2's seed-42 split the
  1-NN baseline was the whole kNN family's ceiling, so every candidate could only
  discard.
- **Timing columns are T2 and jitter between runs.** A wall-clock delta within ~10% is
  not signal, so a re-run of `results.tsv` never reproduces its `seconds` column exactly
  (ex3's fresh run measured 0.291 s against the vendored 0.275 s).

## Resolution

- Verify the patch site before trusting a result: the drivers abort on a
  `PATCH MISS`/`src.count(old) != 1` and an exact tie with the incumbent is read as a
  fired-patch bug, not a candidate outcome.
- Reset on any non-keep, crash included — the fix landed in ex3's driver, which runs
  `git reset --hard HEAD~1` when `status != "keep"`, so a broken candidate stays neither
  in the tree nor in history (the row survives in the ledger). ex1 and ex2 as shipped
  reset only on `discard` (`if status == "discard"`) and keep HEAD on a crashed
  candidate; their crashes never fire in the recorded runs (ex1 and ex2 ledgers have 0
  crash rows), so the difference is latent rather than observed.
- Apply a noise floor: keep if `metric <= incumbent*(1+eps)` **and** the code shrinks,
  so a simplification that is within the timing noise but deletes code is a win.
- Compare the whole output, not a field: the exact-output gate matches the reference
  dict-for-dict, which is what made ex3's fast-but-wrong candidate fail.
- Pre-register a split with headroom in the frozen evaluator: scan seeds and freeze one
  (ex2 seed 23), documenting the rejected split and the scan in `prepare.py` as a
  recorded decision.
- Never treat a sub-10% wall-clock delta as signal, and vendor `results.tsv` once: new
  measurements go to a scratch clone, and only the endpoints (not the timing column) are
  compared across runs.

## Verdict

**works** — three faithful contract instantiations run end to end on three objective
shapes, each reproducible from its tracked `train.py` (2.178535 / 1.000000 / gate_ok
True), with the frozen-evaluator guard and the exact-output gate proven falsifiable
against a live redefinition and a labeled ~10×-faster attack. The loop-mechanics
failures this doc records are the naive loop's, and each carries the calibration rule
that fixes it; no example's own run is left red.
