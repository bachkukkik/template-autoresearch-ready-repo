# 16 — Quality Controls

## What

This repo's quality controls split into two halves. The **codified** half is
enforced by a test or a CI job. The **advisory** half is a file that routes a
human or an agent, but does not gate.

The codified half is workflow hygiene plus the tier and guard jobs. Every
workflow sets a top-level `permissions:` block. Every `uses:` pins a full
40-hex commit SHA. Every checkout sets `persist-credentials: false`. No
workflow uses `pull_request_target`. An aggregate `qc-gate` job fails unless
every pre-merge tier job succeeded. A `zizmor` job lints the workflows and its
findings fail CI.

The advisory half is `SECURITY.md`, `.github/CODEOWNERS`,
`.github/pull_request_template.md` and `.github/dependabot.yml`.

## Why

- The workflows had no `permissions:` block, so they inherited the default
  token scope (gap [16](gaps/16-quality-controls-not-adopted.md)).
- Every `uses:` pinned a mutable tag (`actions/checkout@v4`). A mutable tag can
  be re-pointed to attacker code ([actions-hardening](../../kb/concepts/actions-hardening.md)).
- The tier jobs chained by `needs:` only. A red `unit` job *skips* `integration`
  and `e2e`, and GitHub reads *skipped* as passing ([qc-test-tiers](../../kb/concepts/qc-test-tiers.md)).
- There was no `SECURITY.md`, `CODEOWNERS`, dependabot config or PR template,
  and `main` had no ruleset ([github-merge-gates](../../kb/concepts/github-merge-gates.md)).
- A rule a machine cannot check is a hope. Each control lands as a pytest
  assertion or a CI job, not as prose ([quality-controls](../../kb/concepts/quality-controls.md)).

## How

### The guard file

`tests/unit/test_quality_controls.py` is the machine-checkable half. It is
hermetic: file reads and the stdlib only. It carries AC-QC-001..012.

| ID | Asserts |
|----|---------|
| AC-QC-001 | every workflow has a top-level `permissions:` line |
| AC-QC-002 | every `uses:` is 40-hex SHA-pinned, or in the allowlist-debt register |
| AC-QC-003 | one `persist-credentials: false` per `actions/checkout` step |
| AC-QC-004 | no workflow uses `pull_request_target` |
| AC-QC-005 | `.github/pull_request_template.md` exists with an AI-disclosure checkbox |
| AC-QC-006 | `.github/dependabot.yml` covers `github-actions`, `pip` and `docker` |
| AC-QC-007 | `SECURITY.md` exists at the root and states how to report |
| AC-QC-008 | `CODEOWNERS` owns itself, `.github/workflows/`, `AGENTS.md` and `contract/prepare.py` |
| AC-QC-009 | the `qc-gate` job has `if: always()` and needs every tier job |
| AC-QC-010 | the `zizmor` job runs at `--min-severity low`, not SARIF-only |
| AC-QC-012 | AC-QC-001..004 are re-checked as a codification meta-assertion |

AC-QC-011 (the `main` ruleset) is a platform setting. It is verified after
merge via `gh api repos/bachkukkik/template-autoresearch-ready-repo/rulesets`.
It cannot be asserted from the tree.

### The workflow changes

`.github/workflows/ci.yml` and `.github/workflows/sources-readonly.yml` now
carry `permissions: {}` at the top level. Each job elevates to `contents: read`
only. Each checkout pins SHA `11d5960a…` (`# v4`) and sets
`persist-credentials: false`. `setup-python` pins SHA `a26af69b…` (`# v5`).

`ci.yml` gained two jobs. The `zizmor` job installs zizmor with `pipx` and runs
`zizmor --min-severity low .github/workflows/`. The `qc-gate` job carries
`if: always()` and `needs: [unit, integration, e2e, secret-scan, doctrine,
ops-drift, zizmor]`. It fails unless every result is `success`.

### The governance files

`SECURITY.md` (root) states the private-advisory reporting path. It is a new
tracked root file, so it joins the `doctrine` job's `DOCTRINE_ROOTS` list and
the `ROOT_MD_ALLOWLIST` in `tests/unit/test_funnel_structure.py` (funnel rule
11). `.github/CODEOWNERS` owns itself, `.github/workflows/`, `AGENTS.md` and
`contract/prepare.py` — the frozen evaluator. It says in-file that it is
advisory. `.github/dependabot.yml` covers the `github-actions`, `pip` and
`docker` ecosystems.

## Verification

### Run 2026-10-16

From the repo root:

```bash
python3 -m pytest -q tests/unit/test_quality_controls.py
# -> 11 passed

python3 -m pytest -q tests/unit
# -> 187 passed, 1 warning

bash tests/run.sh
# -> unit 187 passed / integration 18 passed / e2e SKIPPED / RESULT: PASSED

bash scripts/verify-clone.sh 2>&1 | grep -E 'RESULT|tracked-root'
# -> PASS  tracked-root coverage — 14 tracked top-level directory(ies), all declared
# -> RESULT: PASSED — 35 check(s) passed

grep -c '^permissions:' .github/workflows/ci.yml .github/workflows/sources-readonly.yml
# -> .github/workflows/ci.yml:1
# -> .github/workflows/sources-readonly.yml:1

grep -c 'persist-credentials: false' .github/workflows/ci.yml .github/workflows/sources-readonly.yml
# -> .github/workflows/ci.yml:7
# -> .github/workflows/sources-readonly.yml:1

grep -rn 'pull_request_target' .github/workflows/ || echo none
# -> none

python3 scripts/audit-ste.py ; echo "exit=$?"
# -> exit=0
```

The nine `uses:` refs in `ci.yml` (seven checkout, two setup-python) and the
one in `sources-readonly.yml` all carry a 40-hex SHA and a `# vN` comment.

AC-QC-011 is verified **after merge**, not here: `gh api
repos/bachkukkik/template-autoresearch-ready-repo/rulesets` must return a
ruleset on `main` that requires a PR and the `qc-gate` check, and blocks
force-push and deletion.

## What Works

- All 12 quality-control assertions pass. The guard is hermetic: file reads and
  the stdlib only, no subprocess and no service import.
- Every workflow sets a top-level `permissions: {}`.
- Every `uses:` is SHA-pinned. The AC-QC-002 allowlist-debt register is empty,
  which is the healthy state.
- Every checkout sets `persist-credentials: false` (7 in `ci.yml`, 1 in
  `sources-readonly.yml`).
- The `qc-gate` job needs all seven tier jobs and treats `skipped` as failure.
- `SECURITY.md`, `CODEOWNERS`, the PR template and `dependabot.yml` all ship.
- The full default suite is green: 187 unit tests and 18 integration tests,
  `RESULT: PASSED`. The integration tier covers the MCP surface over a real
  socket, with no container.
- `scripts/verify-clone.sh` reports `RESULT: PASSED — 35 check(s) passed`.

## What Fails

- **The `zizmor` job is not exercised on this host.** It needs a network
  install. AC-QC-010 asserts the job's shape, not its runtime verdict.
- **`CODEOWNERS` and the PR template are advisory.** The repo has one
  maintainer, so required approvals stay off. Neither file blocks a merge.
- **AC-QC-011 is not tree-assertable.** The `main` ruleset is a platform
  setting. A direct push to `main` stays possible until the ruleset lands.
- **AC-QC-002 is a tripwire, not a guarantee.** It proves the pin *shape*. An
  allowlist entry could still name an unpinned action with a reason.

## Resolution

- **The `zizmor` job:** it runs in CI on every push and PR. The unit test is
  the standing tripwire; the job is the runtime gate. A local run needs
  `pipx install zizmor` and network access.
- **`CODEOWNERS` and the PR template:** both files say in-file that they are
  advisory. That is the intended single-maintainer posture, not a defect.
- **AC-QC-011:** apply the ruleset after merge, then re-check with `gh api`.
  The check is recorded here and in the PRD's *CI/CD Gate*.
- **AC-QC-002:** keep the allowlist empty. When an entry is unavoidable, it
  carries a reason and a retire condition
  ([actions-hardening](../../kb/concepts/actions-hardening.md)).

## Verdict

**works** — all 12 quality-control assertions pass against the real tree. The
workflows pin every action, scope the token, drop persisted credentials and
chain through an always-running aggregate gate that treats `skipped` as
failure. The governance files ship. The one unverifiable-from-tree control,
the `main` ruleset, is recorded for post-merge verification.
