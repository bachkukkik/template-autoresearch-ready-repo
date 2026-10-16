# 02 — Contract claims a budget, a keep/discard decision and an immutable evaluator that no code enforces

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-10-16

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/02-autoresearch-contract.md` SC2 | `prepare.py` immutability "is enforced" |
| A | `contract/program.md` § Experimentation | each run stops within `prepare.TIME_BUDGET` (300 s) |
| A | `contract/program.md` § The experiment loop, steps 8–9 | keep only on improvement, otherwise reset |
| B | `contract/train.py` `run()` | reads `prepare.TIME_BUDGET` but never compares elapsed time with it; the baseline returns in ~0.06 s |
| B | `contract/train.py` `run()` (`--results`) | writes `status="keep"` on every successful run; `program.md` step 7 tells the agent not to correct the row |
| B | `contract/train.py` | `peak_vram_mb = 0.0` constant, so the `memory_gb` column is always `0.0` |
| B | `tests/unit/test_prepare_py.py` | asserts only `TIME_BUDGET == 300`; no byte pin on `prepare.py` |

## Evidence

Reproduced 2026-10-16; full record in [`kb/raw/articles/2026-10-16-template-self-audit.md`](../../kb/raw/articles/2026-10-16-template-self-audit.md).

```bash
time python3 contract/train.py            # real ~0.06s with TIME_BUDGET=300
grep -n 'status="keep"' contract/train.py  # hard-coded status
grep -rn sha256 tests/unit/test_prepare_py.py || echo "no pin"
```

## Impact

An agent following `program.md` records worse candidates as `keep`; the frozen evaluator can be edited without any test failing; the fixed-budget invariant (iso-compute) is untested.

## Resolution

Code change + test — PRD 02 SC2 reworded and SC7–SC11 added (AC-TPL-005, 014, 024–028); implemented in `contract/` on this branch.
