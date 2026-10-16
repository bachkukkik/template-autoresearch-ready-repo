# 07 — PRD-07 SC4/SC5 claim a tracking gap that does not exist

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-10-16

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/07-codegraph-adoption.md` SC4, SC5 | `_Verify:_ (no test yet — tracked as a gap)` |
| B | `docs/gaps/` | no open gap for topic 07; `_archive/07-codegraph-no-prd.md` is resolved |

## Evidence

Reproduced 2026-10-16; full record in [`kb/raw/articles/2026-10-16-template-self-audit.md`](../../kb/raw/articles/2026-10-16-template-self-audit.md).

```bash
grep -n "no test yet" docs/prd/07-codegraph-adoption.md
ls docs/gaps/*07* 2>/dev/null || echo "no open 07 gap"
```

## Impact

Two SCs are both untested and untracked.

## Resolution

GitHub issue [#29](https://github.com/bachkukkik/template-autoresearch-ready-repo/issues/29) — real, but needs a live `codegraph` binary on CI; PRD-07 SC4/SC5 now point at the issue.
