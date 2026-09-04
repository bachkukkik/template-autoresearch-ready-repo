# 02 — Autoresearch contract files do not exist in the codebase

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-04
**Resolved:** 2026-09-04 — contract files implemented; see [docs/02](../02-autoresearch-contract.md)

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/02-autoresearch-contract.md:27-48` | The repo ships `program.md`, `prepare.py`, `train.py`, and `results.tsv` with the contract semantics |
| B | repo root (`git ls-files`) | No such files exist; the repo ships only `service/`, `tests/`, `docs/`, `kb/`, config, workflows |

## Evidence

```
$ git ls-files | grep -E '^(program|prepare|train|results)\.' || echo "no contract files"
no contract files
```

## Impact

The template's core value proposition (an autoresearch-ready repo) was intent-only:
a human cloning it got a scaffold + knowledge base, not the loop itself. Until the
contract files landed, `docs/prd/02` SC1–SC6 carried the `[PLANNED]` marker and
could not be verified.

## Resolution

Code change + test — **DONE 2026-09-04**: the contract files ship at repo root
(`program.md`, `prepare.py`, `train.py`) with the `AC-TPL-*` tests in
`tests/unit/`; all pass and are CI-enforced. Verified in
[docs/02-autoresearch-contract.md](../02-autoresearch-contract.md).