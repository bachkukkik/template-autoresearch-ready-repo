# 02 — Autoresearch contract files do not exist in the codebase

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-09-04

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

The template's core value proposition (an autoresearch-ready repo) is intent-only.
A human cloning it today gets a scaffold + knowledge base, not the loop itself.
Until files exist, `docs/prd/02` SC1–SC6 carry the `[PLANNED]` marker and cannot
be verified.

## Resolution

Code change + test — next implementation run authors the contract files at repo
root (per KB contract: `kb/concepts/autoresearch-contract.md`,
`kb/raw/articles/autoresearch-program-md-reference.md`) with the `AC-TPL-*` tests
in `tests/unit/`. This gap closes when those files and tests land. Tracked as the
lead item of the "implement autoresearch template contract" build.