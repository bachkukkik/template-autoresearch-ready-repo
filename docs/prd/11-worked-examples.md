# PRD 11 — Worked Examples: Honest Provenance and Reproducible Ledgers

> Intent: the worked examples under `contract/examples/` must be **honest
> about how they were produced** and **reproducible from tracked state** — a
> reader who copies an example into a scratch clone and runs its driver must get
> the vendored ledger back (ex1/ex2 row for row; ex3 on its deterministic
> columns only), and every claim the example makes about its own
> artefacts (provenance, the seed choice, the budget, the dashboard) must be true.
> Grounded in: [evaluator-legitimacy](../../kb/concepts/evaluator-legitimacy.md)
> (a deterministic judge is only legitimate if a real delta is distinguishable
> from noise, and metric-tuning is a Goodhart risk),
> [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md)
> (the keep/discard decision is an LLM-free function with an explicit contract),
> [better-cheaper-faster-metrics](../../kb/concepts/better-cheaper-faster-metrics.md)
> (timing is a T2 statistical field), and the audit
> [raw/articles/2026-10-16-template-self-audit.md](../../kb/raw/articles/2026-10-16-template-self-audit.md) §2.

## Context

The three examples (`ex1-music-abc`, `ex2-iris-knn`, `ex3-hotpath-speedup`) each
ship a `program.md` / frozen `prepare.py` / one agent-edited `train.py` / a
vendored `results.tsv` ledger / a `loop_driver.py`. The self-audit §2 found four
honesty defects in that set, all of the same shape — **the example describes a
run it did not ship**:

1. **Not reproducible.** Each example ships `train.py` in its FINAL kept state,
   while the driver's patch anchors are written against the BASELINE. Re-running
   a driver against the tracked tree aborts on `PATCH MISS` (ex1, ex3) or replays
   from the wrong start state (ex2 logs `1.000000` as its baseline instead of the
   recorded `0.933333`). The READMEs' "git history (verbatim from the worked
   run)" names commits (`15d522f`, `56cde0b`, …) that do not exist in this repo.
2. **Provenance overstated.** The driver docstrings said the candidate list was
   "the mutation operator's choices" (attributed to a model); `CANDIDATES` is a
   static Python list of string patches replayed deterministically.
3. **A false evaluator claim.** ex2's seed note claimed the seed-42 split had
   zero headroom (every grid config ties at 0.977778). On seed 42 the 1-NN
   baseline is
   `0.977778` and the K × metric × normalize × weighted grid still reaches
   `1.000000`, so headroom exists; seed 23 was picked after scanning seeds 0–39
   for a split with a **larger headline delta** — evaluator-input tuning.
4. **Smaller factual drift.** ex1's `results.tsv` had no header row; ex3's
   final-state `train.py` docstring/comments described its baseline; `TIME_BUDGET`
   was presented as if the run used it (it never does — the baseline finishes in
   well under a second); the dashboard hand-transcribes numbers without any check.

A fourth example, `ex4-llm-repo-speedup`, is the one **LIVE** run: a real model
proposed the candidates and `transcript.jsonl` records every exchange, so its
provenance is the opposite of ex1–ex3's scripted-reference-run provenance and it
is verified in its own test module rather than with the other three (SC7).

**Users:** a reader or agent who trusts an example as evidence for the contract.
**Constraint:** the fix must be *minimal and honest* — reconstruct the baseline as
a tracked file, relabel provenance, correct the notes — **not** a re-run that
fabricates a nicer ledger. The vendored ledgers stay the record; a re-run produces
its own commit hashes and its own (jittering) timing column.

## Success Criteria

- **SC1 ✅ implemented 2026-10-16** — **Reproducible from tracked state.** Each
  example ships a tracked `train_baseline.py` (the reconstructed baseline) and its
  `loop_driver.py` accepts `--from-baseline`, which copies the baseline over
  `train.py` and commits it before replaying. In a fresh scratch git copy, ex1 and
  ex2 replay reproduces the vendored ledger's metric/status/description columns row
  for row. ex3, whose keep/discard statuses are a T2 statistical field, is
  replay-verified on what is deterministic only: the driver starts from the tracked
  baseline and completes the baseline row, the descriptions it produces are a prefix
  of the vendored ledger, and the final kept `train.py` — the vendored artifact when
  a timing flip diverges the cascade, the replay's own HEAD otherwise — passes the
  frozen exact-output gate. Its `median_seconds`, `status` and `gate` columns are
  explicitly **not** compared; a narrow keep that flips can end the cascade on a
  `PATCH MISS` (documented in `docs/11-worked-example-pipelines.md`). _Verify:_
  `tests/unit/test_examples_replay.py` (AC-EXA-001, AC-EXA-002, AC-EXA-009),
  `tests/integration/test_examples_replay.py` (AC-EXA-201, AC-EXA-202).
- **SC2 ✅ implemented 2026-10-16** — **Provenance is honest.** Every example file
  describes the driver as a **scripted reference run** — a fixed candidate list
  replayed by a deterministic driver, with no claim that a model chose the
  candidates. No example file contains a model-chose-it provenance phrase or
  `mutation operator`. _Verify:_ `tests/unit/test_examples_replay.py` (AC-EXA-005).
- **SC3 ✅ implemented 2026-10-16** — **The ex2 seed note is corrected and its
  claim is computed, not trusted.** The note no longer claims the seed-42 split
  offered zero headroom (the grid is recomputed in the test: seed 42 reaches
  `1.000000` > baseline `0.977778`, so headroom exists), it discloses that the seed
  was chosen after a scan to enlarge the headline delta, names that as
  evaluator-input tuning / a Goodhart risk, and keeps `SPLIT_SEED = 23` so the
  vendored ledger stays valid. The frozen split is still a real measurement
  (`0.933333 → 1.000000`). _Verify:_ `tests/unit/test_examples_replay.py`
  (AC-EXA-006, AC-EXA-007, AC-EXA-008).
- **SC4 ✅ implemented 2026-10-16** — **Every ledger carries its driver's header.**
  ex1's headerless `results.tsv` gains the header its driver writes; each vendored
  ledger's first line equals that example's `HEADER` constant, five tab-separated
  columns wide. _Verify:_ `tests/unit/test_examples_replay.py` (AC-EXA-004).
- **SC5 ✅ implemented 2026-10-16** — **The dashboard is checkable, not trusted.**
  The inline series in `dashboard.html` must equal the vendored ledgers it charts
  (value and status, in order), so a drift fails the tier instead of rendering
  silently. _Verify:_ `tests/unit/test_examples_replay.py` (AC-EXA-003).
- **SC6 ✅ implemented 2026-10-16** — **The budget is described as a ceiling.**
  Every example's `program.md` frames `TIME_BUDGET` as a bound on a runaway
  candidate, never as a target the run is expected to fill. _Verify:_
  `tests/unit/test_examples_replay.py` (AC-EXA-010).
- **SC7 ✅ implemented 2026-10-17** — **ex4 is the live-LLM instance, and its run
  replays offline.** `contract/examples/ex4-llm-repo-speedup/` instantiates the
  contract with a live model in the mutation slot: `agent_driver.py` (an
  OpenAI-compatible loop keyed on env-var NAMES only, `--from-baseline` /
  `--replay`) prompts the model for the complete `target/solution.py`, applies
  it, commits, runs the FROZEN evaluator and keeps or resets. `transcript.jsonl`
  records every exchange with its `finish_reason`, so `--replay` re-applies the
  recorded responses **with no network** and reproduces the ledger's
  deterministic columns (`gate`, `stop_reason`, `tokens`, `description`) row for
  row — never `median_seconds`, nor the discard row's timing-turning `status`.
  The budget binds: the shipped quadratic baseline runs **36.05 s = 7.2×** the
  `TIME_BUDGET = 5` s ceiling, so its ledger row is a budget stop
  (`stop_reason: budget` / `status: timeout`). The recorded 2026-10-17 run
  (model `opencode-go/kimi-k3`) is 5 rounds — **1 keep / 1 discard / 3 unusable**
  (empty content, `finish_reason: length`, recorded as crash) — and the ledger
  states that plainly rather than smoothing it away. Provenance is a LIVE LLM
  run (a model id and a date are recorded); no ex4 file claims the
  scripted-reference-run provenance ex1–ex3 carry. _Verify:_
  `tests/unit/test_examples_ex4.py` (AC-EXA-011..018).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| ex1 replay (from tracked baseline) reproduces the vendored ledger | `tests/unit/test_examples_replay.py` | AC-EXA-001 |
| ex2 replay (from tracked baseline) reproduces the vendored ledger | `tests/unit/test_examples_replay.py` | AC-EXA-002 |
| dashboard.html inline numbers == vendored TSVs | `tests/unit/test_examples_replay.py` | AC-EXA-003 |
| every results.tsv first line == its driver's HEADER | `tests/unit/test_examples_replay.py` | AC-EXA-004 |
| provenance says "scripted reference run"; no model-chose-it phrase | `tests/unit/test_examples_replay.py` | AC-EXA-005 |
| seed-42 grid recomputed: headroom exists (note claim falsified) | `tests/unit/test_examples_replay.py` | AC-EXA-006 |
| frozen split (seed 23) is a real 0.933333 → 1.000000 measurement | `tests/unit/test_examples_replay.py` | AC-EXA-007 |
| seed note discloses evaluator-input tuning / Goodhart | `tests/unit/test_examples_replay.py` | AC-EXA-008 |
| each example ships train_baseline.py + `--from-baseline` | `tests/unit/test_examples_replay.py` | AC-EXA-009 |
| every program.md frames TIME_BUDGET as a ceiling | `tests/unit/test_examples_replay.py` | AC-EXA-010 |
| ex4 ships the three-role split (frozen evaluator + frozen suite, one agent artifact, driver, ledger, transcript) | `tests/unit/test_examples_ex4.py` | AC-EXA-011 |
| every results.tsv first line == its driver's HEADER (ex4) | `tests/unit/test_examples_ex4.py` | AC-EXA-012 |
| the budget binds: ex4's baseline row is a budget stop | `tests/unit/test_examples_ex4.py` | AC-EXA-013 |
| ex4 transcript rounds == ledger LLM rows; an empty response is a recorded crash | `tests/unit/test_examples_ex4.py` | AC-EXA-014 |
| ex4 provenance is a live LLM run (model + date; no scripted-reference claim) | `tests/unit/test_examples_ex4.py` | AC-EXA-015 |
| no ex4 file names a secret or a machine path | `tests/unit/test_examples_ex4.py` | AC-EXA-016 |
| ex4 program.md frames TIME_BUDGET as a ceiling | `tests/unit/test_examples_ex4.py` | AC-EXA-017 |
| ex4 offline replay reproduces the deterministic columns row for row | `tests/unit/test_examples_ex4.py` | AC-EXA-018 |
| ex3 replay completes the baseline row + a description prefix; final artifact passes the gate | `tests/integration/test_examples_replay.py` | AC-EXA-201 |
| final kept ex3 train.py passes the exact-output gate inside budget | `tests/integration/test_examples_replay.py` | AC-EXA-202 |

## Assumptions

- The reconstructed baselines are exactly the states the drivers' patch anchors
  were written against; the drivers self-check this (a wrong anchor is a
  `PATCH MISS` and a non-zero exit, not a silent wrong row). `[ASSUMPTION]`
- Commit hashes in a re-run differ from the vendored ones (fresh `git init`), so
  the tiers compare the metric / status / description columns and never the commit
  column. `[ASSUMPTION]`
- ex3's timing column and its keep/discard statuses are not reproducible by
  construction (two candidates sit within a few percent of their incumbent and
  flip), and a flipped keep diverges the patch cascade — the discarded row's state
  survives, a later candidate then raises inside `run()`, and the final `attack:`
  anchor misses (`PATCH MISS`). The integration tier therefore compares only what
  is deterministic: the baseline row, the descriptions produced as a **prefix** of
  the vendored ledger, and the final-artifact exact-output gate (the vendored
  `train.py` when a flip diverged the cascade). It never compares the
  `median_seconds`, `status` or `gate` columns. `[ASSUMPTION]`
- A candidate whose `run()` raises makes the frozen gate print `gate_ok: False`, so
  the driver records it as gate `invalid` (median `inf`); a run that dies before
  printing a verdict is gate `n/a`. Both are crashes, distinct from a genuine
  wrong-answer rejection, but a divergent cascade can add either cell to the
  ledger — which is exactly why the tier compares no gate column. The mechanism is
  documented in `docs/11-worked-example-pipelines.md` (§ Run 2026-10-16).
  `[ASSUMPTION]`
- A full ex3 replay costs ~1.5 minutes (12 candidates × 5 timed reps over a
  2M-token workload); acceptable inside the integration job's 5-minute timeout.
  `[ASSUMPTION]`
- The vendored ledgers are the record and are not regenerated: the ledger files
  keep their original (non-reproducible) commit hashes on purpose. `[ASSUMPTION]`

## Confidence

**High** on SC1's ex1/ex2 replay (both reproduced the vendored ledgers row for row
here) and on SC1's ex3 deterministic claims (baseline row, description prefix and
the final-artifact exact-output gate — verified here in both the converged and a
forced-diverged cascade), SC2, SC4, SC5 and SC6 (purely textual/structural
checks). **High** on SC3's computed falsification (the seed-42 grid is recomputed
in the tier). **Medium** on the ex3 integration budget: measured ~1.5 min on this
host, so the job's 5-minute timeout holds, but a very slow runner could approach it
— the replay is guarded by a generous explicit timeout.

## CI/CD Gate

`tests/unit/test_examples_replay.py` and `tests/integration/test_examples_replay.py`
are picked up automatically by `tests/run.sh` (which runs `pytest tests/unit` then
`pytest tests/integration`) and by `.github/workflows/ci.yml`'s `unit` and
`integration` jobs, which glob those directories. No workflow edit is needed. The
integration job already fails when its junit XML shows zero executed tests, so the
new integration test cannot pass by being silently skipped in CI. No PR merges with
a red tier (AGENTS.md §5/§6).
