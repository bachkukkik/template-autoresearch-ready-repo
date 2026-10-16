# PRD 16 — Quality Controls (Codified Review & QC Gates)

> Funnel stage 4. Ported from the foundation template
> `bachkukkik/template-agentic-ready-repo` (its PRD 06, commit `11b00e1`), renumbered
> to 16 because topic 06 here is the concurrent multi-topic service.
> Grounded in: [quality-controls](../../kb/concepts/quality-controls.md),
> [actions-hardening](../../kb/concepts/actions-hardening.md),
> [github-merge-gates](../../kb/concepts/github-merge-gates.md),
> [qc-test-tiers](../../kb/concepts/qc-test-tiers.md),
> [scanning-without-advanced-security](../../kb/concepts/scanning-without-advanced-security.md).
> Raw evidence: [quality-controls-audit-dossier](../../kb/raw/articles/quality-controls-audit-dossier.md),
> [2026-10-16-template-self-audit](../../kb/raw/articles/2026-10-16-template-self-audit.md).

## Context

This repo's tests are strong but its gates are weak. Three test tiers run in CI, but:

- the workflows have no `permissions:` block and inherit the default token scope;
- all `uses:` steps pin actions by mutable tag (`actions/checkout@v4`, `actions/setup-python@v5`);
- no checkout sets `persist-credentials: false`;
- there is no `SECURITY.md`, `CODEOWNERS`, dependabot config or PR template;
- the tier jobs are chained only by `needs:`, so a red `unit` *skips* `integration` and
  `e2e`, and a required check reads *skipped* as green;
- `main` has no branch protection and no ruleset (`gh api …/rulesets` → `0`), so a direct
  push bypasses every gate.

The foundation template fixed all of this in its PRD 06; this repo never adopted it.

**Target users:** a template adopter who inherits the workflows as-is; the maintainer who
self-merges after green CI. **Constraints:** single maintainer (no required approvals);
public repo, no GitHub Advanced Security; every control must be **rule-based** — a test or
a CI job, not prose (the 80/20 codification rule).

## Success Criteria

- **SC1** — Every workflow file sets a top-level `permissions:` block; jobs request only
  what they need (`contents: read` by default). _Verify:_ `tests/unit/test_quality_controls.py`
  (AC-QC-001). ✅ implemented 2026-10-16
- **SC2** — Every `uses:` is SHA-pinned (40-hex, `# vN` comment), or listed in the test's
  allowlist-debt register with a reason and a retire condition. _Verify:_
  `tests/unit/test_quality_controls.py` (AC-QC-002). ✅ implemented 2026-10-16
- **SC3** — Every `actions/checkout` step sets `persist-credentials: false`. _Verify:_
  `tests/unit/test_quality_controls.py` (AC-QC-003). ✅ implemented 2026-10-16
- **SC4** — No workflow uses the `pull_request_target` trigger. _Verify:_
  `tests/unit/test_quality_controls.py` (AC-QC-004). ✅ implemented 2026-10-16
- **SC5** — `.github/pull_request_template.md` asks for scope, test evidence and an
  AI-contribution disclosure checkbox. _Verify:_ `tests/unit/test_quality_controls.py`
  (AC-QC-005). ✅ implemented 2026-10-16
- **SC6** — `.github/dependabot.yml` covers the `github-actions`, `pip` (service/) and
  `docker` ecosystems. _Verify:_ `tests/unit/test_quality_controls.py` (AC-QC-006). ✅ implemented 2026-10-16
- **SC7** — `SECURITY.md` at the repo root states how to report a vulnerability (private
  advisory) and holds no live secret. _Verify:_ `tests/unit/test_quality_controls.py`
  (AC-QC-007). ✅ implemented 2026-10-16
- **SC8** — `.github/CODEOWNERS` owns itself, `.github/workflows/`, `AGENTS.md` and
  `contract/prepare.py` (the frozen evaluator), and says in-file that it is advisory.
  _Verify:_ `tests/unit/test_quality_controls.py` (AC-QC-008). ✅ implemented 2026-10-16
- **SC9** — An aggregate `qc-gate` job (`if: always()`) fails unless every pre-merge tier
  job (`unit`, `integration`, `e2e`, `secret-scan`, `doctrine`, `ops-drift`, `zizmor`)
  succeeded — *skipped* counts as failure. _Verify:_ `tests/unit/test_quality_controls.py`
  (AC-QC-009) + the `qc-gate` CI job. ✅ implemented 2026-10-16
- **SC10** — A `zizmor` job runs workflow static analysis and its findings fail CI.
  _Verify:_ `tests/unit/test_quality_controls.py` (AC-QC-010) + the `zizmor` CI job. ✅ implemented 2026-10-16
- **SC11** — A ruleset on `main` requires a PR and the `qc-gate` check, and blocks
  force-push and deletion. _Verify:_ `gh api repos/bachkukkik/template-autoresearch-ready-repo/rulesets`
  after merge (AC-QC-011, recorded in `docs/16-quality-controls.md`). ✅ implemented 2026-10-16
- **SC12** — The 80/20 split holds: each of AC-QC-001..010 is enforced by a pytest
  assertion or a CI job (meta-assertion over the test module). _Verify:_
  `tests/unit/test_quality_controls.py` (AC-QC-012). ✅ implemented 2026-10-16

**Not adopted (peer data says no):** gitleaks/trufflehog jobs (GitHub's free native secret
scanning covers public repos; the existing `secret-scan` job covers the generic-shape
class it misses); required approvals ≥ 1 (unsatisfiable for one maintainer); merge queue
(org-only).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Workflow hygiene: permissions, SHA pins, no persisted credentials, no `pull_request_target` | `tests/unit/test_quality_controls.py` | AC-QC-001..004 |
| Governance files: PR template, dependabot, SECURITY.md, CODEOWNERS | `tests/unit/test_quality_controls.py` | AC-QC-005..008 |
| Aggregate gate + workflow linter present and wired | `tests/unit/test_quality_controls.py` + `qc-gate`, `zizmor` jobs | AC-QC-009..010 |
| `main` ruleset | `gh api …/rulesets` (post-merge, platform setting) | AC-QC-011 |
| Controls are codified, not prose | `tests/unit/test_quality_controls.py` | AC-QC-012 |

## Assumptions

- Single-maintainer flow continues: self-merge after green CI; required approvals stay off. `[ASSUMPTION]`
- `zizmor` runs from a SHA-pinned third-party action; if that action's supply-chain posture
  degrades, install it via `pipx` inside the job instead. `[ASSUMPTION]`
- The self-hosted/`act` local run (`AGENTS.md` §6) cannot exercise the ruleset; AC-QC-011
  is verified only against GitHub. `[ASSUMPTION]`

## Confidence

**High** — every control is backed by verified current-state evidence in the self-audit
and by the foundation template's peer survey (14 MIT/Apache repos), and the foundation
template already ships the same controls green.

## CI/CD Gate

The `unit` job runs `tests/unit/test_quality_controls.py`. The `qc-gate` aggregate job is
the single required check on `main`. No PR merges with a red test.
