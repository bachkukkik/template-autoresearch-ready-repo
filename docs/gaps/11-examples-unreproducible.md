# 11 — Worked examples cannot regenerate their ledgers and over-state their provenance

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-10-16

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `contract/examples/README.md` | re-run `loop_driver.py` in a scratch clone to produce a fresh ledger |
| A | `docs/11-worked-example-pipelines.md` | every documented run is reproducible from the tracked copy |
| A | each `loop_driver.py` docstring | the candidate list is the mutation operator's model-chosen output |
| A | `contract/examples/ex2-iris-knn/prepare.py` seed note | the seed-42 split offered zero headroom (every grid config ties at 0.977778) |
| B | fresh `git init` copy of each example | ex1 and ex3 abort with `PATCH MISS`; ex2's baseline logs 1.000000, not 0.933333 — each `train.py` ships its final kept state |
| B | each `loop_driver.py` | `CANDIDATES` is a hard-coded list (a scripted reference run) |
| B | grid on seed 42 | 1-NN = 0.977778, grid max = 1.000000 — headroom existed; seed 23 was chosen after a 0..39 scan |
| B | `tests/` | no test covers `contract/examples/` |

## Evidence

Reproduced 2026-10-16; full record in [`kb/raw/articles/2026-10-16-template-self-audit.md`](../../kb/raw/articles/2026-10-16-template-self-audit.md).

```bash
cp -r contract/examples/ex1-music-abc "$TMPDIR/ex1" && cd "$TMPDIR/ex1" && rm results.tsv \
  && git init -q && git add -A && git -c user.name=a -c user.email=a@b commit -qm base \
  && python3 loop_driver.py; echo "exit=$?"   # PATCH MISS, exit=1
```

## Impact

Readers trust a trajectory they cannot reproduce; the examples imply an autonomous agent did the research; the seed note hides an evaluator-input choice (a Goodhart risk).

## Resolution

Code change + test — new PRD 11 (AC-EXA-*); baselines vendored, provenance relabelled, seed note corrected. Follow-up example with a live agent: GitHub issue #30.
