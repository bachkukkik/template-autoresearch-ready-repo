# PRD 02 — Autoresearch Template Contract

> Intent for the core deliverable: the template ships the autoresearch loop —
> `program.md` (human-edited skill), `train.py` (agent-edited artifact),
> `prepare.py` (immutable), fixed-time budget, `val_bpb` metric, keep/discard
> loop, `results.tsv` log.
> Grounded in: [autoresearch-contract](../../kb/concepts/autoresearch-contract.md),
> [val-bpb-metric](../../kb/concepts/val-bpb-metric.md),
> [fixed-time-budget](../../kb/concepts/fixed-time-budget.md),
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
  _Verify:_ `tests/unit/test_program_md.py` (AC-TPL-001..003). `[PLANNED]`

- **SC2** — The repo ships an immutable `prepare.py` holding constants (`TIME_BUDGET
  = 300`), data, tokenizer, dataloader, and the ground-truth evaluator
  `evaluate_bpb`; its immutability is enforced. _Verify:_
  `tests/unit/test_prepare_py.py` (AC-TPL-011..013). `[PLANNED]`

- **SC3** — The repo ships an agent-edited `train.py` that runs within the time
  budget and the keep/discard loop records `commit | val_bpb | memory_gb |
  status | notes` in `results.tsv`. _Verify:_ `tests/unit/test_train_loop.py`
  (AC-TPL-021..023). `[PLANNED]`

- **SC4** — `val_bpb` is computed per the KB definition: total per-token
  cross-entropy in nats ÷ (log 2 × total utf-8 byte length of targets), special
  tokens masked. _Verify:_ `tests/unit/test_val_bpb.py` (AC-TPL-031). `[PLANNED]`

- **SC5** — The loop surface exposes the domain hooks from
  [domain-adaptation](../../kb/concepts/domain-adaptation.md): only the data side
  of `prepare.py` + notes in `program.md` change to port to a new domain, and the
  metric/selection rules stay intact. _Verify:_ `tests/unit/test_domain_hooks.py`
  (AC-TPL-041..042). `[PLANNED]`

- **SC6** — The template documents the fixed-time-budget and evaluator-legitimacy
  caveats: platform-bound results, Goodhart risk, always sample generated output.
  _Verify:_ `tests/unit/test_program_md.py` (AC-TPL-004). `[PLANNED]`

> **`[PLANNED]` marker:** the tests above do not exist yet — they are the target of
> the next implementation run (see `docs/gaps/02-*`). The funnel stages this PRD
> *intent*; verified behaviour will land in `docs/02-*` when it is run.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| `program.md` complete per §SC1 | `tests/unit/test_program_md.py` | AC-TPL-001..003 |
| Caveats documented in `program.md` | `tests/unit/test_program_md.py` | AC-TPL-004 |
| `prepare.py` immutable + `evaluate_bpb` correct | `tests/unit/test_prepare_py.py` | AC-TPL-011..013 |
| `train.py` within budget; `results.tsv` format | `tests/unit/test_train_loop.py` | AC-TPL-021..023 |
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
sources); **low** on implementation state — the contract files do not exist yet and
are the next build.

## CI/CD Gate

Once implemented, all `AC-TPL-*` tests run in CI per `.github/workflows/ci.yml`
via `tests/run.sh`. No PR merges with a red test. Until then this PRD is intent-only
and every SC carries the `[PLANNED]` marker.