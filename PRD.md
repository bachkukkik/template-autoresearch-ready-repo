# template-autoresearch-ready-repo — Product Requirements Document

> Version: 1.0.0
> Date: 2026-09-04
> Status: **ACTIVE** — grounded in `kb/` (stage 3), compared against the codebase in `docs/gaps/` (stage 5)
> Knowledge Base: `kb/`

---

## Repo Identity

This repository is a **template for autonomous research** in the style of
[karpathy/autoresearch](https://github.com/karpathy/autoresearch), built on the
bachkukkik/template-agentic-ready-repo doctrine. It ships the autoresearch
contract (`program.md` / `prepare.py` / `train.py`, fixed-time budget, `val_bpb`,
keep/discard loop) inside the document funnel governance (kb → PRD → gaps →
verified reality) with example service + three-tier tests + CI as the working
scaffold.

**Brand:** template-autoresearch-ready-repo. Tagline: *ship the loop, keep the
funnel.*

## Funnel Position

This PRD set is **stage 4** of the Document Funnel defined in `AGENTS.md`. It is
grounded in `kb/` (stage 3) and compared against the codebase in `docs/gaps/`
(stage 5). Any claim here with no `kb/` page behind it carries `[ASSUMPTION]` or is
dropped. Verified behaviour is never recorded here — it goes to `docs/NN-slug.md`.

## Source-of-Truth Doctrine

Three sources feed this PRD set. When they conflict, this doctrine resolves:

1. **KB wins on semantics and behaviour.** When the KB (`kb/`) and any PRD disagree on *what* something means or *how* a flow behaves, the KB is authoritative.
2. **Repo artifacts win on literal values.** For *literal* values — config values, port numbers, version strings — the repo's own files are the source of truth.
3. **Top-level PRD > detail PRD.** When this file and a `docs/prd/*.md` disagree, this file wins.

## Quick Reference

| # | Topic | Document | Status |
|---|-------|----------|--------|
| 01 | Template Scaffold & CI | [docs/prd/01-template-scaffold-ci.md](docs/prd/01-template-scaffold-ci.md) | Active — verified in [docs/01](docs/01-service-architecture.md) |
| 02 | Autoresearch Template Contract | [docs/prd/02-autoresearch-contract.md](docs/prd/02-autoresearch-contract.md) | Active — implemented + verified in [docs/02](docs/02-autoresearch-contract.md) |
| 03 | Document Funnel & KB Governance | [docs/prd/03-funnel-kb-governance.md](docs/prd/03-funnel-kb-governance.md) | Active — verified in CI + [docs/03](docs/03-funnel-kb-governance.md) |
| 04 | Examples Corpus | [docs/prd/04-examples-corpus.md](docs/prd/04-examples-corpus.md) | Active — verified in [docs/04](docs/04-examples-corpus.md) |
| 05 | REST + Streamable-HTTP MCP Service | [docs/prd/05-mcp-rest-service.md](docs/prd/05-mcp-rest-service.md) | Active — verified in [docs/05](docs/05-mcp-rest-service.md) |

## Verification Policy

Every PRD topic must satisfy:

1. **Context** — clear problem statement, target users, constraints.
2. **Success criteria** — SMART metrics.
3. **Test mapping** — every SC carries an inline `_Verify:` annotation pointing to the test file + test ID.
4. **CI/CD gate** — no PR merges with a red test.
5. **Source attribution** — links to KB concept pages.
6. **Assumption flagging** — `[ASSUMPTION]` markers for unverified claims.
7. **Confidence rating** — high, medium, or low.

### Global Test Suite Structure

| Tier | Directory | Runner | CI Job | ID range | Covers |
|------|-----------|--------|--------|----------|--------|
| Unit + Component | `tests/unit/` | pytest | `unit` | `AC-X-0NN` | Pure logic, no transport |
| E2E | `tests/e2e/` | bats | `e2e` | `AC-X-1NN` | Full flows against a running container |
| Integration | `tests/integration/` | pytest | `integration` | `AC-X-2NN` | Cross-process / persistence |

**Test ID convention:** `AC-<DOMAIN>-NNN` (e.g., `AC-EXM-001`). The hundreds digit
encodes the tier, per the table above.

**CI gate:** All CI jobs must pass before merge. No PR merges with a red test.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-01 | Template created. |
| 0.2.0 | 2026-09-02 | Test tiers made executable; ID ranges encode the tier. |
| 1.0.0 | 2026-09-04 | Real repo identity + four topic PRDs (01–04) grounded in the populated `kb/`; placeholder example PRD replaced. |
| 1.1.0 | 2026-09-04 | PRDs 02–04 un-`[PLANNED]`: autoresearch contract implemented (program.md/prepare.py/train.py), governance + corpus tests added; verified in docs/02–04. |