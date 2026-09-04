# PRD 01 — Template Scaffold & CI

> Intent for the verified scaffold: `service/` example, three-tier tests, CI gates.
> Verified reality: [docs/01-service-architecture.md](../01-service-architecture.md).
> Grounded in: [template-agentic-ready-repo](../../kb/entities/template-agentic-ready-repo.md),
> [document-funnel-doctrine](../../kb/concepts/document-funnel-doctrine.md).

## Context

Agents and humans need a working skeleton that enforces the doctrine from day one:
a real service with real tests and CI gates, so the pipeline is proven before any
custom code is added. The scaffold demonstrates every tier named in `AGENTS.md`
§5 and every CI gate (§6) against a minimal, healthchecked service.

**Target users:** agents onboarding into this repo, and maintainers reviewing
changes. **Constraints:** three executable test tiers, no stub jobs, no host port
binding by default, no live credentials tracked.

## Success Criteria

- **SC1** — The repo ships a minimal Python HTTP service behind Docker Compose that
  answers `/health` → 200, `/` → 200, unknown path → 404, and reports healthy to
  Docker. _Verify:_ `tests/unit/test_routing.py` (AC-EXM-001..003),
  `tests/integration/test_service_endpoints.py` (AC-EXM-201..203),
  `tests/e2e/example.bats` (AC-EXM-101, AC-EXM-102).

- **SC2** — Every test tier has a runner in `tests/run.sh` and a CI job in
  `.github/workflows/ci.yml`; no tier is a stub. _Verify:_ `tests/run.sh` +
  `ci.yml` jobs `unit`, `integration`, `e2e` (AC-EXM-* suite passes end to end).

- **SC3** — `kb/raw/**` is add-only: a PR that modifies or deletes a raw source
  fails unless labeled `ingest`; additions always pass. _Verify:_
  `.github/workflows/sources-readonly.yml` (job `check-raw-readonly`).

- **SC4** — The doctrine is structurally enforced: every harness entry point
  resolves through a symlink and no funnel stage is gitignored. _Verify:_
  `ci.yml` job `doctrine`.

- **SC5** — No tracked credential files or hardcoded secret assignments enter the
  repo. _Verify:_ `ci.yml` job `secret-scan`.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| `/health`, `/`, unknown path map to 200/200/404 | `tests/unit/test_routing.py` | AC-EXM-001, AC-EXM-002, AC-EXM-003 |
| Running container answers the endpoints over HTTP | `tests/integration/test_service_endpoints.py` | AC-EXM-201, AC-EXM-202, AC-EXM-203 |
| Container answers via `docker compose exec` | `tests/e2e/example.bats` | AC-EXM-101, AC-EXM-102 |
| `kb/raw` edits/removals blocked without `ingest` label | `.github/workflows/sources-readonly.yml` | job `check-raw-readonly` |
| Symlinks resolve; funnel tracked; no secrets in tree | `.github/workflows/ci.yml` | jobs `doctrine`, `secret-scan` |

## Assumptions

- The scaffold service is intentionally minimal and is **not** the product; it
  exists to prove the pipeline. `[ASSUMPTION]` — keep it minimal, per
  karpathy-guidelines simplicity.

## Confidence

**High** — every SC is already verified today; see
[docs/01-service-architecture.md](../01-service-architecture.md) (verdict:
`partial`, last verified 2026-09-02) and the live CI jobs.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml`. No PR merges with a red test.
`bash tests/run.sh --with-e2e` must pass locally against a running container before
a PR is opened (`AGENTS.md` §6).