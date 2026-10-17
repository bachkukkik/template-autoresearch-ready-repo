# Worked examples — four instantiations of the contract

Four complete autoresearch runs, each proving the template on a different axis:
three scripted runs (2026-09-26) and **one live LLM run** (2026-10-17). Every
directory is a faithful contract instance: `program.md` (human policy) /
`prepare.py` (FROZEN evaluator) / the one agent-edited file (`train.py`, or
`target/solution.py` in ex4) / `results.tsv` (keep/discard ledger) / the driver
that ran the loop (`loop_driver.py`, or `agent_driver.py` in ex4) / the
reconstructed baseline the run started from (`train_baseline.py`, or
`solution_baseline.py` in ex4).

**ex1–ex3 are scripted reference runs.** Their `loop_driver.py` replays a **fixed
candidate list** deterministically; it is a reference implementation of the loop,
not a model-driven search. **ex4 is the one LIVE run**: `agent_driver.py` asks a
real OpenAI-compatible model for each candidate and records every exchange in
`transcript.jsonl`, so the run is reproducible offline.

**`results.tsv` is runtime state, vendored here ONCE as the record of the worked
run** — do not continue appending to it. To reproduce it, copy the example into a
scratch clone and run the driver from the tracked baseline:

```bash
cp -r contract/examples/ex2-iris-knn /tmp/ex2 && cd /tmp/ex2
git init -q && git add -A && git commit -qm "contract: baseline"
python3 loop_driver.py --from-baseline
```

ex4 is the one example that replays **offline from its recorded transcript** — no
network, from the tracked baseline:

```bash
mkdir -p "$TMPDIR/ex4"
git archive HEAD contract/examples/ex4-llm-repo-speedup | tar -x -C "$TMPDIR/ex4" --strip-components=3
cd "$TMPDIR/ex4" && git init -q && git add -A && git commit -qm "contract: baseline"
python3 agent_driver.py --from-baseline --replay transcript.jsonl
```

A **live** ex4 run (not the replay) must start from an empty ledger — delete the
vendored `results.tsv` first (`rm -f results.tsv`); the driver refuses to append to
the record. The driver also refuses to run unless the example directory is the git
root, because it commits and hard-resets.

`--from-baseline` copies the tracked `train_baseline.py` over the FINAL-kept
`train.py` and commits it, so the driver's patch anchors (written against the
baseline) apply. A re-run reproduces the **metric / status / description**
columns (ex1, ex2) or the **gate column and descriptions** (ex3) row for row. It
does **not** reproduce the `seconds`/`median_seconds` column — timing is a T2
statistical field and jitters between runs — nor the commit hashes (a fresh
`git init`), and ex3's keep/discard statuses are timing-sensitive. Tests:
`tests/unit/test_examples_replay.py` (ex1/ex2), 
`tests/integration/test_examples_replay.py` (ex3),
`tests/unit/test_examples_ex4.py` (ex4).

| # | Example | Direction | Baseline → Best | Candidates (K/D/C) | Proves |
|---|---|---|---|---|---|
| 1 | [ex1-music-abc](ex1-music-abc/) — ABC sheet-music LM (procedural stand-in corpus, per the transcript-corpus topic) | val_bpb ↓ | 3.765056 → **2.178535** (−42.1%) | 6 (4/2/0) | text domain; frozen evaluator; keep/discard/reset |
| 2 | [ex2-iris-knn](ex2-iris-knn/) — iris kNN (real seaborn-mirror iris, embedded byte-identical) | accuracy **↑** | 0.933333 → **1.000000** | 7 (3/4/0) | direction inversion; object-identity anti-redefine guard fires |
| 3 | [ex3-hotpath-speedup](ex3-hotpath-speedup/) — non-ML hot path, 2M-token workload | median s ↓ **+ exact-output gate** | 2.310 s → **0.275 s** (8.41×) | 11 (9/1/1) | anti-Goodhart gate rejects a 10×-faster wrong answer (`attack:` row) |
| 4 | [ex4-llm-repo-speedup](ex4-llm-repo-speedup/) — small repo, one agent-edited file, **LIVE LLM agent** (`opencode-go/kimi-k3`) | median s ↓ **+ exact-output gate** | inf (baseline 36.05 s = 7.2× over budget) → **0.001811 s** | 5 (1/1/3) | the live loop: a model proposes real code edits; the budget binds (baseline killed at `TIME_BUDGET`); 3 rounds returned empty content and are recorded as crashes |

Progression dashboard (ex1–ex3, one self-contained file):
[`dashboard.html`](dashboard.html). It **hand-transcribes** the ledger values
into an inline `RUNS` array — it does not read the TSVs at load time — so
`tests/unit/test_examples_replay.py` (AC-EXA-003) asserts the inline numbers
equal the vendored ledgers and fails on any drift. ex4 is not charted: its ledger
carries a driver header and T2-timing crash rows the dashboard's two-column
series does not model; its replay is checked in `tests/unit/test_examples_ex4.py`
(AC-EXA-011..030).

## Calibration lessons (validated across all four runs)

- **The loop catches driver bugs for free**: an anchor bug that patches the
  wrong site yields an identical metric → mechanical discard. A candidate that
  ties the incumbent exactly is a mutation that never fired.
- **Reset must fire on crash, not just discard** — otherwise HEAD ends on the
  broken commit (ex3's first driver did this; fixed, history re-run clean).
- **A seed/split choice that widens the headline delta is evaluator-input
  tuning, and it must be disclosed.** ex2's split seed was picked after scanning
  seeds 0–39 for the largest apparent gain; on the first candidate, seed 42, the
  1-NN baseline already scores 0.977778 and the grid still reaches 1.000000, so
  the seed-42 delta is one test row while seed 23's is three. The choice is
  recorded in `ex2-iris-knn/prepare.py` as a Goodhart risk, and the grid claim is
  recomputed by the unit tier rather than trusted.
- **Exact-output gates must be shape-proof**: ex3's `attack:` candidate passed
  the first spot-check field and still failed the full-output comparison — a
  spot-check gate would have kept a badly wrong answer.
- **Strict improvement blocks simplification**: ex3's dead-code deletion lost
  by 0.8% and was discarded in the recorded run (and flips to a keep on a re-run —
  it sits inside the timing noise). Add a noise floor: keep if metric ≤
  incumbent×(1+ε) AND code shrinks.
- **Timing fields are T2**: never treat a wall-clock delta within ~10% as
  signal.
- **A token-capped reasoning model can return empty content.** ex4's rounds 2, 4
  and 5 spent the entire `--max-tokens` budget on a hidden chain of thought and
  returned nothing. The driver records `finish_reason: length` and an
  unusable-response crash rather than inventing a candidate; give a reasoning
  model a generous cap and record `finish_reason` so a truncated round is visible.
- **A verdict the candidate can print or write is not a verdict.** ex4's first
  evaluator parsed `gate` / `median_seconds` / `stop_reason` from the child's
  stdout, which the candidate shares, so a file that printed a fake `gate: ok` and
  exited 0 without running a test was scored `0.000001 s` and kept. Moving the
  verdict into a parent-created file was not enough — the candidate is imported
  inside the child that writes it and can read the path off `sys.argv` — so the gate
  is now the PARENT's own comparison of the raw `run()` outputs the child reports,
  on a held-out workload plus benchmark workloads whose seeds the parent draws with
  `secrets` after the child's import handshake
  (`docs/11-worked-example-pipelines.md`, Run 2026-10-17).

Each example's README records its git history verbatim from the worked run; those
commits live in the (gitignored) scratch clones and are **not** in this repo, so a
re-run produces different hashes — compare columns, never hashes.
