# Worked examples — three instantiations of the contract

Three complete autoresearch runs (2026-09-26), each proving the template on a
different axis. Every directory is a faithful contract instance: `program.md`
(human policy) / `prepare.py` (FROZEN evaluator) / `train.py` (the only
agent-edited file) / `results.tsv` (keep/discard ledger) / `loop_driver.py`
(the mechanical loop driver used for the run).

**`results.tsv` is runtime state, vendored here ONCE as the record of the
worked run** — do not continue appending to it; re-run `loop_driver.py` in a
scratch clone to produce a fresh ledger (its `seconds`/timing column will
jitter — timing is a T2 statistical field).

| # | Example | Direction | Baseline → Best | Candidates (K/D/C) | Proves |
|---|---|---|---|---|---|
| 1 | [ex1-music-abc](ex1-music-abc/) — ABC sheet-music LM (procedural stand-in corpus, per the transcript-corpus topic) | val_bpb ↓ | 3.765056 → **2.178535** (−42.2%) | 6 (4/2/0) | text domain; frozen evaluator; keep/discard/reset |
| 2 | [ex2-iris-knn](ex2-iris-knn/) — iris kNN (real seaborn-mirror iris, embedded byte-identical) | accuracy **↑** | 0.933333 → **1.000000** | 7 (3/4/0) | direction inversion; object-identity anti-redefine guard fires |
| 3 | [ex3-hotpath-speedup](ex3-hotpath-speedup/) — non-ML hot path, 2M-token workload | median s ↓ **+ exact-output gate** | 2.310 s → **0.275 s** (8.41×) | 11 (9/1/1) | anti-Goodhart gate rejects a 10×-faster wrong answer (`attack:` row) |

Progression dashboard (all three runs, one self-contained file):
[`dashboard.html`](dashboard.html)

## Calibration lessons (validated across all three runs)

- **The loop catches driver bugs for free**: an anchor bug that patches the
  wrong site yields an identical metric → mechanical discard. A candidate that
  ties the incumbent exactly is a mutation that never fired.
- **Reset must fire on crash, not just discard** — otherwise HEAD ends on the
  broken commit (ex3's first driver did this; fixed, history re-run clean).
- **Seed/split choice with zero headroom is a legitimate recorded decision**
  (ex2: on the seed-42 split the 1-NN baseline WAS the kNN-family ceiling;
  seeds 0–39 scanned, seed 23 frozen and documented in `prepare.py`).
- **Exact-output gates must be shape-proof**: ex3's `attack:` candidate passed
  the first spot-check field and still failed the full-output comparison — a
  spot-check gate would have kept a badly wrong answer.
- **Strict improvement blocks simplification**: ex3's dead-code deletion lost
  by 0.8% and was discarded. Add a noise floor: keep if metric ≤
  incumbent×(1+ε) AND code shrinks.
- **Timing fields are T2**: never treat a wall-clock delta within ~10% as
  signal.

Git histories are recorded verbatim in each example's README (the scratch
clones themselves are gitignored stage-1 scratch and are not cited).
