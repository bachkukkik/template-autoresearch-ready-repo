# 02 — Autoresearch Template Contract

## What

The three-file autoresearch contract in `contract/`: `program.md` (the human-edited
skill), `prepare.py` (the frozen evaluator — data side, ground-truth metric,
keep/discard decision, time budget, ledger checker), and `train.py` (the one
agent-edited artifact), plus the untracked `results.tsv` ledger.

## Why

The repo's purpose is a ready-made autoresearch template in the style of
karpathy/autoresearch aligned with the bachkukkik doctrine. The contract — which
file the human edits, which the agent edits, which nobody edits, and how the
metric is evaluated and the keep decision is made — is the product (PRD 02,
grounded in `kb/concepts/autoresearch-contract.md` and
`kb/concepts/deterministic-keep-gate.md`).

## How

- **`program.md`** — the human-edited skill: run tag + `autoresearch/<tag>`
  branch, baseline first, CAN (edit `train.py` only) / CANNOT (edit `prepare.py`,
  install packages, redefine `evaluate_bpb`), the budget as an iso-compute
  **ceiling** with an outer `timeout 600` hard kill, the noise-floor simplicity
  criterion, summary output format (including `stop_reason`), the `results.tsv`
  columns (`commit\tval_bpb\tmemory_gb\tstatus\tdescription`, tab-separated,
  `keep|discard|crash`), the experiment loop + NEVER STOP, a `## Porting to any X`
  section with the four invariants, and caveats (platform-bound results, sample
  generated output, Goodhart).
- **`prepare.py`** — stdlib-only, frozen: `TIME_BUDGET = 300`, the decision policy
  `DIRECTION = "lower"` and `NOISE_FLOOR = 0.001`, a deterministic char-level
  corpus (`TRAIN_TEXT`/`VAL_TEXT`), `tokenizer()`, `dataloader()`,
  `evaluate_bpb(logits, target_ids, token_bytes, mask_ids)` = total per-token
  cross-entropy in nats / (log 2 × total utf-8 byte length of targets) with
  special tokens masked (raises `ValueError` on zero bytes or length mismatch),
  plus `decide(metric, incumbent, epsilon, direction, shrinks)` and
  `check_ledger(path)`. Its bytes are pinned by `tests/unit/test_prepare_py.py`
  (AC-TPL-014). `python3 contract/prepare.py` prints a dataset summary;
  `python3 contract/prepare.py --check-ledger results.tsv` validates a ledger
  (exit 0 valid / 1 on violations).
- **`train.py`** — stdlib-only, the only file the agent edits: imports
  `evaluate_bpb` from `prepare` (never redefines it), reads `prepare.TIME_BUDGET`
  dynamically, checks a monotonic deadline at every training step (stopping at it
  and reporting `stop_reason: budget|converged`), measures host peak RSS via
  `peak_rss_gb()`, prints the upstream summary block and appends a `results.tsv`
  row only when `--results PATH` is given — with the status `prepare.decide`
  returns against the ledger's incumbent (never a hard-coded keep) and an optional
  `--description` / `--shrinks`.
- **`results.tsv`** — gitignored (untracked per upstream). Header
  `commit\tval_bpb\tmemory_gb\tstatus\tdescription`; rows append on `--results`;
  `memory_gb` is a measured host peak RSS in GB (3 decimals).

## Verification

```bash
python3 -m pytest -q tests/unit         # AC-TPL block: 001..005, 011..014,
                                        # 021..023, 024..028, 031, 041..042
python3 -m pytest -q tests/integration  # service still parses the summary block
python3 contract/prepare.py             # prepare.py OK — TIME_BUDGET=300s, vocab_size=31
time python3 contract/train.py          # val_bpb: 3.795531, stop_reason: converged
cd contract && python3 prepare.py --check-ledger "$TMPDIR/r.tsv"; echo $?  # 0
```

### Run 2026-10-16

Executed on this worktree (stdlib `python3`, no numpy/torch), outputs verbatim:

```
$ time python3 contract/train.py
---
val_bpb:          3.795531
training_seconds: 0.0
total_seconds:    0.0
peak_vram_mb:     0.0
stop_reason:      converged
num_steps:        29
num_params_M:     0.001
---

real    0m0.070s

$ cd contract && rm -f "$TMPDIR/r.tsv" \
  && python3 train.py --results "$TMPDIR/r.tsv" --description baseline \
  && python3 train.py --results "$TMPDIR/r.tsv" \
  && python3 prepare.py --check-ledger "$TMPDIR/r.tsv"; echo $?
commit	val_bpb	memory_gb	status	description
dfc98e8	3.795531	0.016	keep	baseline
dfc98e8	3.795531	0.016	discard	smoothed bigram, stop=converged, budget=300s
check-ledger OK
0
```

The identical second candidate is a mechanical `discard` (no gain vs the
incumbent) — the evaluator, not the agent, decides. The budget path is real too:
`prepare.TIME_BUDGET = 0` yields `stop_reason: budget, num_steps: 0` and a worse
`val_bpb` (4.954196), showing a cut stream trains less, never more.

## What Works

- In-loop budget: `train.py` checks a monotonic deadline every step. With
  `TIME_BUDGET = 0` it stops at once (`stop_reason: budget`, `num_steps: 0`); with
  the default 300 s the toy fit converges in ~0.07 s (`stop_reason: converged`).
  The budget is an honest ceiling, not a declared constant.
- Evaluator-owned decision: `prepare.decide` returns `keep` for the baseline and
  for strict improvements beyond `NOISE_FLOOR`, `keep` for within-floor changes
  only when the artifact `shrinks`, and `discard` otherwise. `train.py --results`
  writes that verdict — the identical-second-candidate run above records
  `discard`, which the old hard-coded `keep` could not.
- Ledger checker: `prepare.py --check-ledger` enforces the exact header, 5 tab
  columns, a 7-char commit, the status vocabulary, crash rows at
  `0.000000`/`0.000`, a keep baseline first, and every keep consistent with
  `decide()` against the prior best keep; it reports all violations and exits 1.
- Measured memory: `memory_gb` is a real host peak RSS (0.016 GB here), not the
  old constant `0.0`.
- The evaluator is byte-pinned (AC-TPL-014): an edit to `contract/prepare.py`
  fails CI unless the pin moves in the same commit.
- `python3 contract/prepare.py` and `python3 contract/train.py` run end to end on
  a stock `python3` (stdlib only); `results.tsv` stays out of git; the budget is
  monkeypatchable so CI never waits 300 s.

## What Fails

- **Model ceiling:** the shipped bigram baseline is intentionally toy — a real
  run needs the agent to replace `train.py`'s model (that is the point of the
  loop); the template does not pre-tune a model.
- **The budget is a ceiling, not a floor:** the shipped baseline converges in
  ~0.07 s, so a normal run reports `converged` and the 300 s bound only ever
  bites a candidate the agent writes. There is no minimum-runtime guarantee.
- **Crash logging is manual:** `train.py` appends a row only after a successful
  run, so a run killed by `timeout` (or one that dies before `log_result`) is
  recorded as `crash` by the agent, per `program.md`.
- **VRAM is still unmeasured:** `peak_vram_mb` prints `0.0` (CPU-only demo). The
  ledger's `memory_gb` measures host RSS, not accelerator memory.
- **`shrinks` is not in the ledger:** `check_ledger` can enforce "no keep is worse
  than the incumbent beyond the noise floor", but it cannot verify that a
  within-floor keep actually shrank — that flag is not recorded.

## Resolution

- **Model ceiling:** keep/improve `train.py` within `prepare.TIME_BUDGET`; the
  loop, evaluator and decision are ready. Add real hardware measurement when a GPU
  stack is introduced — update this doc's `Verification` then.
- **Budget-as-ceiling:** documented in `program.md`; the outer `timeout 600` hard
  kill covers a wedged or non-converging candidate, and a killed run counts as a
  `crash`. An agent that writes a genuinely slow model does hit `stop_reason:
  budget`.
- **Crash logging:** documented in `program.md` (a `timeout` kill is a `crash`
  row); the ledger checker accepts and validates crash rows.
- **VRAM:** add platform-specific device-memory hooks when porting to GPU; the
  summary and ledger keys already accept them.
- **`shrinks`:** today the checker is deliberately conservative (it accepts
  within-floor keeps) and the agent passes `--shrinks`; a future ledger column
  could record the artifact size delta so the checker can enforce it.

## Verdict

**works** — the three-file contract now enforces what it claims: the time budget
is checked in the loop, keep/discard is a deterministic evaluator-owned function,
the ledger is validated, the memory column is a real measurement, and the frozen
evaluator is byte-pinned. Verified end to end on 2026-10-16 with stdlib-only code
(`val_bpb: 3.795531`, `keep`/`discard` as expected, `check-ledger OK`, exit 0;
172 unit tests and 18 integration tests green). Known limits are the toy baseline
(by design), the budget being a ceiling rather than a floor, and CPU-only VRAM
reporting.
