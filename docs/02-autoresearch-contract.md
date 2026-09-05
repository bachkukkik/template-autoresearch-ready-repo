# 02 — Autoresearch Template Contract

## What

The three-file autoresearch contract in `contract/`: `program.md` (human-edited skill), `prepare.py` (immutable anti-cheat evaluator + data side), and `train.py` (agent-edited artifact), plus the untracked `results.tsv` ledger.

## Why

The repo's purpose is a ready-made autoresearch template in the style of
karpathy/autoresearch aligned with the bachkukkik doctrine. The contract — which
file the human edits, which the agent edits, which nobody edits, and how the
metric is evaluated — is the product (PRD 02, grounded in
`kb/concepts/autoresearch-contract.md`).

## How

- **`program.md`** — the human-edited skill: run tag + `autoresearch/<tag>`
  branch, baseline first, CAN (edit `train.py` only) / CANNOT (edit `prepare.py`,
  install packages, redefine `evaluate_bpb`), VRAM soft constraint, simplicity
  criterion, summary output format, `results.tsv` columns
  (`commit\tval_bpb\tmemory_gb\tstatus\tdescription`, tab-separated,
  `keep|discard|crash`), experiment loop + NEVER STOP, caveats (platform-bound
  results, sample generated output, Goodhart).
- **`prepare.py`** — stdlib-only, owned by nobody: `TIME_BUDGET = 300`, a
  deterministic char-level corpus (`TRAIN_TEXT`/`VAL_TEXT`), `tokenizer()`,
  `dataloader()`, and `evaluate_bpb(logits, target_ids, token_bytes,
  mask_ids)` = total per-token cross-entropy in nats / (log 2 × total utf-8 byte
  length of targets), special tokens masked; raises `ValueError` on zero bytes or
  length mismatch. Runs as `python3 contract/prepare.py` to print a dataset
  summary.
- **`train.py`** — stdlib-only, the only file the agent edits: imports
  `evaluate_bpb` from `prepare` (never redefines), reads `prepare.TIME_BUDGET`
  dynamically at run time, prints the upstream summary block
  (`val_bpb`, `training_seconds`, `total_seconds`, `peak_vram_mb`, `num_steps`,
  `num_params_M`), and appends rows to `results.tsv` only when `--results PATH`
  is given. Ships a smoothed-bigram baseline as an honest starting point.
- **`results.tsv`** — gitignored (untracked per upstream). Header
  `commit\tval_bpb\tmemory_gb\tstatus\tdescription`; rows append on `--results`.

## Verification

```bash
python3 -m pytest tests/unit -v            # 59 passed (2026-09-05, incl. contract
                                           # location + AC-TPL-001..004, 011..013,
                                           # 021..023, 031, 041..042)
python3 contract/prepare.py                # prepare.py OK — TIME_BUDGET=300s, vocab_size=31
python3 contract/train.py                  # prints summary block → real val_bpb
git check-ignore results.tsv               # -> results.tsv  (untracked ledger)
```

_Verified 2026-09-05 after the contract/ relocation: same 13 AC-TPL behaviors
green at the new location; root-md funnel allowlist updated (program.md is no
longer a root file)._

## What Works

- All 13 AC-TPL tests pass: program.md content, `TIME_BUDGET==300`, data-side
  hooks, `evaluate_bpb` math (hand-computed uniform-logits and perfect-prediction
  cases), train-loop summary + exact results.tsv format + crash row, domain hooks
  (train imports the evaluator, no redefinition).
- `python3 contract/prepare.py` and `python3 contract/train.py` run end to end
  on a stock python3 (stdlib only — no numpy/torch).
- `results.tsv` stays out of git; scale artifacts land under official test tiers.
- Budget is monkeypatchable for tests: `run()` reads `prepare.TIME_BUDGET` at call
  time, so CI never waits 300s (tests run in ~0.1s wall-clock).
- Security: no `shell=True`; `subprocess.run` with explicit argv + `timeout=5`;
  no secrets; no credential logging.

## What Fails

- **Model ceiling:** the shipped bigram baseline is intentionally toy — a real
  run needs the agent to replace `train.py`'s model with something better
  (that is the point of the loop). The template does not pre-tune a model.
- **Crash logging is manual:** `train.py` appends a row only after a successful
  run; if it crashes before `log_result`, the agent records the `crash` row by
  hand per `program.md` step 7.
- **No VRAM measurement:** `peak_vram_mb` prints `0.0` (CPU-only demo); a GPU
  port must measure actual memory (e.g. torch.cuda.max_memory_allocated).

## Resolution

- **Model ceiling:** keep/improve `train.py` within `prepare.TIME_BUDGET`; the
  loop and evaluator are ready. Add real hardware measurement when a GPU stack
  is introduced — update this doc's `Verification` then.
- **Crash logging:** documented in `program.md`; no code change needed.
- **No VRAM measurement:** add platform-specific memory hooks when porting to
  GPU; the summary keys are already structured to accept them.

## Verdict

**works** — the three-file contract is implemented and verified end to end with
stdlib-only code: all AC-TPL tests green, both scripts run, the metric matches the
KB formula, and the ledger format is upstream-exact. Known limits are the toy
baseline (by design) and CPU-only VRAM reporting (platform-dependent).