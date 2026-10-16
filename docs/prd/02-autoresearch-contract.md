# PRD 02 — Autoresearch Template Contract

> Intent for the core deliverable: the template ships the autoresearch loop —
> `program.md` (human-edited skill), `train.py` (agent-edited artifact),
> `prepare.py` (immutable), fixed-time budget, `val_bpb` metric, keep/discard
> loop, `results.tsv` log.
> Grounded in: [autoresearch-contract](../../kb/concepts/autoresearch-contract.md),
> [val-bpb-metric](../../kb/concepts/val-bpb-metric.md),
> [fixed-time-budget](../../kb/concepts/fixed-time-budget.md),
> [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md),
> [evaluator-legitimacy](../../kb/concepts/evaluator-legitimacy.md),
> [problem-selection](../../kb/concepts/problem-selection.md),
> [karpathy-autoresearch](../../kb/entities/karpathy-autoresearch.md).

## Context

The repo's purpose is to be a ready-made autoresearch template in the style of
karpathy/autoresearch, aligned with the bachkukkik doctrine. Users must be able
to clone it, swap in their own domain data, and run the autonomous research loop
on their own hardware. The contract — which file the human edits, which the agent
edits, which nobody edits, and the evaluation rules — is the product.

**Target users:** a human researcher who wants overnight autonomous experimentation
on their platform; an agent that will run the loop unattended. **Constraints:**
three-file contract, fixed wall-clock budget, immutable evaluator, keep/discard
selection, results logged to `results.tsv`.

## Success Criteria

- **SC1** — The repo ships a human-edited `program.md` (task-scale skill file) that
  specifies: run tag + `autoresearch/<tag>` branch; baseline first; CAN/CANNOT
  rules; simplicity criterion; VRAM soft constraint; output format; NEVER STOP.
  _Verify:_ `tests/unit/test_program_md.py` (AC-TPL-001..003). ✅ implemented 2026-09-04

- **SC2** — The repo ships an immutable `prepare.py` holding constants (`TIME_BUDGET
  = 300`), the decision policy (`DIRECTION`, `NOISE_FLOOR`), the data, tokenizer,
  dataloader, and the ground-truth evaluator `evaluate_bpb`; its immutability is
  **enforced by a byte pin** — the sha256 of `contract/prepare.py` is asserted in
  the test, so an evaluator edit fails CI unless the pin moves in the same
  commit. _Verify:_ `tests/unit/test_prepare_py.py` (AC-TPL-011..014). ✅ implemented 2026-10-16

- **SC3** — The repo ships an agent-edited `train.py` that runs within the time
  budget and the keep/discard loop records `commit | val_bpb | memory_gb |
  status | notes` in `results.tsv`. _Verify:_ `tests/unit/test_train_loop.py`
  (AC-TPL-021..023). ✅ implemented 2026-09-04

- **SC4** — `val_bpb` is computed per the KB definition: total per-token
  cross-entropy in nats ÷ (log 2 × total utf-8 byte length of targets), special
  tokens masked. _Verify:_ `tests/unit/test_val_bpb.py` (AC-TPL-031). ✅ implemented 2026-09-04

- **SC5** — The loop surface exposes the domain hooks from
  [domain-adaptation](../../kb/concepts/domain-adaptation.md): only the data side
  of `prepare.py` + notes in `program.md` change to port to a new domain, and the
  metric/selection rules stay intact. _Verify:_ `tests/unit/test_domain_hooks.py`
  (AC-TPL-041..042). ✅ implemented 2026-09-04

- **SC6** — The template documents the fixed-time-budget and evaluator-legitimacy
  caveats: platform-bound results, Goodhart risk, always sample generated output.
  _Verify:_ `tests/unit/test_program_md.py` (AC-TPL-004). ✅ implemented 2026-09-04

- **SC7** — `TIME_BUDGET` is **enforced in the loop**: `train.py` checks a
  monotonic deadline at every training step and stops at it, reporting
  `stop_reason: budget|converged` in the summary; the budget is an honest
  iso-compute **ceiling**, and `program.md` adds an outer hard kill
  (`timeout 600 python3 train.py`). Grounded in
  [fixed-time-budget §Enforced in code](../../kb/concepts/fixed-time-budget.md).
  _Verify:_ `tests/unit/test_train_loop.py` (AC-TPL-024). ✅ implemented 2026-10-16

- **SC8** — Keep/discard is a **deterministic, evaluator-owned decision**:
  `prepare.decide(metric, incumbent, epsilon, direction, shrinks)` returns
  `keep|discard` (baseline → keep; strict improvement beyond `NOISE_FLOOR` →
  keep; inside the floor only when the artifact shrinks), and `train.py
  --results` writes that verdict against the ledger's incumbent — never a
  hard-coded keep. Grounded in
  [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md).
  _Verify:_ `tests/unit/test_contract_gate.py` (AC-TPL-025) +
  `tests/unit/test_train_loop.py` (AC-TPL-026). ✅ implemented 2026-10-16

- **SC9** — The append-only `results.tsv` ledger is **validated**:
  `prepare.py --check-ledger PATH` / `check_ledger(path)` enforces the exact
  header, 5 tab columns, a 7-char commit, the `keep|discard|crash` vocabulary,
  crash rows at `0.000000`/`0.000`, a keep baseline first, and every keep
  consistent with `decide()` against the prior best keep (exit 0 valid / 1 on
  violations). Grounded in
  [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md).
  _Verify:_ `tests/unit/test_contract_gate.py` (AC-TPL-027). ✅ implemented 2026-10-16

- **SC10** — The `memory_gb` results column is a **real measurement** (host peak
  RSS via `resource.getrusage`, normalised across platforms) — `train.peak_rss_gb()`
  returns > 0 and the appended row records it — rather than a constant
  placeholder. Grounded in
  [fixed-time-budget](../../kb/concepts/fixed-time-budget.md). _Verify:_
  `tests/unit/test_train_loop.py` (AC-TPL-028). ✅ implemented 2026-10-16

- **SC11** — `program.md` documents porting the loop to **any X**: a
  `## Porting to any X` section carrying the four invariants (one editable
  artifact; the evaluator owns metric + eval inputs + `DIRECTION`/`NOISE_FLOOR`/
  `TIME_BUDGET`; an append-only ledger checked by `--check-ledger`; the metric
  read from `run.log`, never self-reported; T2 timing never gates), a noise-floor
  rule in the simplicity criterion, and the outer hard kill. Grounded in
  [fixed-time-budget §Noise floor](../../kb/concepts/fixed-time-budget.md).
  _Verify:_ `tests/unit/test_program_md.py` (AC-TPL-005). ✅ implemented 2026-10-16

> **Implemented status:** the `AC-TPL-001..004`, `011..013`, `021..023`, `031`,
> `041..042` tests ship with the contract files (2026-09-04 implementation wave);
> the Wave-B1 hardening criteria (SC2 pin, SC7..SC11) landed 2026-10-16 with the
> `AC-TPL-005`, `014`, `024..028` tests — all green, see
> [docs/02-autoresearch-contract.md](../02-autoresearch-contract.md).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| `program.md` complete per §SC1 | `tests/unit/test_program_md.py` | AC-TPL-001..003 |
| Caveats documented in `program.md` | `tests/unit/test_program_md.py` | AC-TPL-004 |
| `program.md` porting + noise floor + hard kill (§SC11) | `tests/unit/test_program_md.py` | AC-TPL-005 |
| `prepare.py` immutable, pinned + `evaluate_bpb` correct | `tests/unit/test_prepare_py.py` | AC-TPL-011..014 |
| `prepare.decide()` evaluator-owned keep/discard (§SC8) | `tests/unit/test_contract_gate.py` | AC-TPL-025 |
| `check_ledger` / `--check-ledger` validates the ledger (§SC9) | `tests/unit/test_contract_gate.py` | AC-TPL-027 |
| `train.py` within budget; `results.tsv` format | `tests/unit/test_train_loop.py` | AC-TPL-021..023 |
| Budget enforced in-loop + `stop_reason` (§SC7) | `tests/unit/test_train_loop.py` | AC-TPL-024 |
| `--results` writes `decide()`'s verdict (§SC8) | `tests/unit/test_train_loop.py` | AC-TPL-026 |
| `memory_gb` is a measured host RSS (§SC10) | `tests/unit/test_train_loop.py` | AC-TPL-028 |
| `val_bpb` formula | `tests/unit/test_val_bpb.py` | AC-TPL-031 |
| Domain portability hooks | `tests/unit/test_domain_hooks.py` | AC-TPL-041..042 |

## Assumptions

- The template targets small-compute defaults (TinyStories-friendly) per
  [autoresearch-platform-forks](../../kb/comparisons/autoresearch-platform-forks.md).
  `[ASSUMPTION]`
- Upstream `program.md` semantics are preserved verbatim where the KB derives from
  [raw/articles/autoresearch-program-md-reference.md](../../kb/raw/articles/autoresearch-program-md-reference.md).
- The 5-minute budget may need relaxation (e.g. 10 min) per problem —
  [fixed-time-budget](../../kb/concepts/fixed-time-budget.md). `[ASSUMPTION]`

## Confidence

**High** on semantics (KB pages are `high`/`medium` confidence and trace to raw
sources); **verified** on implementation — the contract files ship with the
`AC-TPL-*` tests and all pass (2026-09-04), see
[docs/02-autoresearch-contract.md](../02-autoresearch-contract.md).

## CI/CD Gate

All `AC-TPL-*` tests run in CI per `.github/workflows/ci.yml` via `tests/run.sh`
(`unit` job). No PR merges with a red test.