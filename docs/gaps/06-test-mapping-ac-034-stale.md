# 06 — PRD-06's Test Mapping misdescribes AC-MCP-034

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-09-18
**Resolved:** 2026-09-18 — PRD edit applied

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/06-multi-topic-concurrent-service.md:97` (Test Mapping) | "Runner executes in workspace; report carries topic + corpus stats; legacy default unchanged (val_bpb 1.234)" |
| B | `tests/unit/test_workspace.py:122-148` (AC-MCP-034) | with `work_dir` the report carries `topic` + `corpus {files, chars}`; without it "the legacy report is unchanged (no topic/corpus keys)" and both paths assert `3.0 < val_bpb < 4.5` |
| B | `tests/unit/test_runner.py:60-66` (AC-MCP-024) | `1.234` is a sample of the legacy vendor `RESULT val_bpb=` format, not a value any default path produces |

## Evidence

```bash
grep -rn "1.234" tests/ docs/
# tests/unit/test_runner.py:65-66   -> parse_val_bpb sample input
# docs/prd/06-multi-topic-concurrent-service.md:97  -> the mapping row
grep -n "3.0 < .*val_bpb" tests/unit/test_workspace.py
# 136:    assert 3.0 < report["val_bpb"] < 4.5  # contract bigram baseline ~3.7
# 146:    assert 3.0 < legacy["val_bpb"] < 4.5
```

The default path now executes the canonical `contract/` (bigram baseline ≈3.795);
no test asserts a `1.234` default.

## Impact

The mapping table described an assertion that does not exist. A reviewer using the
table to decide what AC-MCP-034 pins would have believed the legacy path returns a
vendored-stub metric, and would have missed the part the test really guarantees —
that the legacy path omits the `topic`/`corpus` keys the workspace path adds.

## Resolution

PRD edit — applied 2026-09-18: the row now reads "legacy default path unchanged (no
topic/corpus keys, same ~3.7 contract baseline)". **Status: resolved.**
