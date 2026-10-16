# 16 — Foundation-template quality controls never adopted

**Layers:** prd ↔ code
**Status:** resolved
**Opened:** 2026-10-16

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/16-quality-controls.md` SC1–SC12 | permissions, SHA pins, no persisted credentials, governance files, aggregate gate, zizmor, `main` ruleset |
| B | `.github/workflows/ci.yml`, `sources-readonly.yml` | no `permissions:`; six `uses:` pinned by tag; no `persist-credentials: false` |
| B | `.github/` | no `CODEOWNERS`, `dependabot.yml`, `pull_request_template.md`; no root `SECURITY.md` |
| B | `ci.yml` jobs | tiers chained by `needs:` only; no `qc-gate`, no `zizmor` |
| B | GitHub settings | `gh api …/rulesets` → 0; branch `main` not protected |

## Evidence

Reproduced 2026-10-16; full record in [`kb/raw/articles/2026-10-16-template-self-audit.md`](../../kb/raw/articles/2026-10-16-template-self-audit.md).

```bash
grep -c '^permissions:' .github/workflows/*.yml
grep -n 'uses:' .github/workflows/*.yml
gh api repos/bachkukkik/template-autoresearch-ready-repo/rulesets --jq length   # 0
```

## Impact

Adopters inherit broad default token scope and mutable action tags; a red unit tier can merge as 'skipped'; a direct push to `main` bypasses CI.

## Resolution

Code change + test — PRD 16 (AC-QC-001..012) implemented on this branch; ruleset applied post-merge (AC-QC-011).
