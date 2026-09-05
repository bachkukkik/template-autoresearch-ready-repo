# PRD 01 — Template Scaffold & CI

> Intent for the verified scaffold: `service/` example, three-tier tests, CI gates.
> Verified reality: the service is documented in
> [docs/05-mcp-rest-service.md](../05-mcp-rest-service.md) +
> [docs/06-multi-topic-concurrency.md](../06-multi-topic-concurrency.md); the
> CI/governance gates in [docs/03-funnel-kb-governance.md](../03-funnel-kb-governance.md).
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

- **SC1** — The repo ships a healthchecked Python HTTP service behind Docker Compose
  with a three-tier test suite (unit, integration, E2E). The live service answers
  `/health` → 200 (unauthenticated) and exposes the `/api/v1/research` lifecycle over
  REST + MCP. _Verify:_ `tests/unit/test_routes.py` (AC-MCP-001..006),
  `tests/integration/test_service_endpoints.py` (AC-MCP-211..215),
  `tests/e2e/service.bats` (AC-MCP-101..104).

- **SC2** — Every test tier has a runner in `tests/run.sh` and a CI job in
  `.github/workflows/ci.yml`; no tier is a stub. _Verify:_ `tests/run.sh` +
  `ci.yml` jobs `unit`, `integration`, `e2e` (AC-MCP-* suite passes end to end).

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
| REST + MCP routing surface (health, research ops, /mcp) | `tests/unit/test_routes.py` | AC-MCP-001..006 |
| Live service over a real socket: health + research lifecycle | `tests/integration/test_service_endpoints.py` | AC-MCP-211..215 |
| Running container answers via `docker compose exec` | `tests/e2e/service.bats` | AC-MCP-101..104 |
| `kb/raw` edits/removals blocked without `ingest` label | `.github/workflows/sources-readonly.yml` | job `check-raw-readonly` |
| Symlinks resolve; funnel tracked; no secrets in tree | `.github/workflows/ci.yml` | jobs `doctrine`, `secret-scan` |

## Assumptions

- The scaffold proved the pipeline with a minimal example; the example service has
  since evolved into the product (PRD-05 REST + MCP, PRD-06 concurrency), documented
  in `docs/05`/`docs/06`. This PRD retains the tiering + CI-gate intent.

## Confidence

**High** — every SC is verified by the live service suite (`docs/05`, `docs/06`)
and the CI gates run on every PR.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml`. No PR merges with a red test.
`bash tests/run.sh --with-e2e` must pass locally against a running container before
a PR is opened (`AGENTS.md` §6).