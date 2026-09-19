# template-autoresearch-ready-repo — Product Requirements Document

> Version: 1.5.0
> Date: 2026-09-04 (created; see *Version History* for revision dates)
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
| 01 | Template Scaffold & CI | [docs/prd/01-template-scaffold-ci.md](docs/prd/01-template-scaffold-ci.md) | Active — CI gates verified in [docs/03](docs/03-funnel-kb-governance.md); service in [docs/05](docs/05-mcp-rest-service.md) + [docs/06](docs/06-multi-topic-concurrency.md) |
| 02 | Autoresearch Template Contract | [docs/prd/02-autoresearch-contract.md](docs/prd/02-autoresearch-contract.md) | Active — implemented + verified in [docs/02](docs/02-autoresearch-contract.md) |
| 03 | Document Funnel & KB Governance | [docs/prd/03-funnel-kb-governance.md](docs/prd/03-funnel-kb-governance.md) | Active — verified in CI + [docs/03](docs/03-funnel-kb-governance.md) |
| 04 | Examples Corpus | [docs/prd/04-examples-corpus.md](docs/prd/04-examples-corpus.md) | Active — verified in [docs/04](docs/04-examples-corpus.md) |
| 05 | REST + Streamable-HTTP MCP Service | [docs/prd/05-mcp-rest-service.md](docs/prd/05-mcp-rest-service.md) | Active — verified in [docs/05](docs/05-mcp-rest-service.md) |
| 06 | Concurrent Multi-Topic Service | [docs/prd/06-multi-topic-concurrent-service.md](docs/prd/06-multi-topic-concurrent-service.md) | Active — verified in [docs/06](docs/06-multi-topic-concurrency.md) |
| 07 | CodeGraph Adoption | [docs/prd/07-codegraph-adoption.md](docs/prd/07-codegraph-adoption.md) | Active — instruction-surface adoption, verified in [docs/07](docs/07-codegraph-adoption.md); four of six SCs now carry test IDs (`tests/unit/test_codegraph_adoption.py`, AC-CG-001..006), SC4/SC5 stay hand-verified |
| 08 | Adoption Readiness | [docs/prd/08-adoption-readiness.md](docs/prd/08-adoption-readiness.md) | Active — `ops/` home + sync tool, onboarding path, harness neutrality and seven new guards; seven of eight SCs carry a test ID (`tests/unit/test_{ops_sync,verify_clone,docs_template,harness_neutrality,funnel_structure,gaps_lifecycle,corpus_integrity}.py`), SC6 a named CI step + the `tests/conftest.py` preflight, and SC1/SC3/SC8 rest on the new `ops-drift` and existing `doctrine` CI jobs; verified in [docs/08](docs/08-adoption-readiness.md) (verdict `works`) |

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
| 1.2.0 | 2026-09-05 | PRD-06: concurrent multi-topic service — per-job workspace isolation, corpus delivery (texts + files), concurrency cap, async decision locked; verified in docs/06. |
| 1.3.0 | 2026-09-19 | PRD-07: CodeGraph adoption — one-tool MCP surface (`codegraph_explore`), CLI-twins fallback, gitignored local `.codegraph/` index, `sync`/`affected` workflow, `DO_NOT_TRACK=1` opt-out; closes `docs/gaps/07-codegraph-no-prd.md`. Intent-and-instruction-surface only at that version: the six SCs carried `_Verify:_ (no test yet — tracked as a gap)` and were verified by hand in docs/07 (test coverage arrived in 1.4.0). |
| 1.4.0 | 2026-09-19 | PRD-08: adoption readiness — `ops/` home + `sync.sh` (`--check` read-only / `--apply` gated, AC-OPS-001..010); harness-neutrality guard across Hermes / Claude Code / opencode / DeepSeek-OpenAI-compatible (AC-HRN-001..007); documentary-invariant guard (AC-DOC-001..016); `doctrine`-job tracked-root coverage + `AC-FUN-003`; `integration` junit guard + the ambient preflight; `scripts/verify-clone.sh` onboarding check; gaps 03/07 archived. Also gives PRD-07's SCs test IDs (`tests/unit/test_codegraph_adoption.py`, AC-CG-001..006) and corrects the PRD-07 status/README claims that predated them. Verified in docs/08. |
| 1.5.0 | 2026-09-19 | PRD-08 closure — the three failures recorded in docs/08 are now automated: `scripts/verify-clone.sh` is covered by `tests/unit/test_verify_clone.py` (AC-VC-001..008, incl. five broken-clone negative controls and a read-only proof); the ops `--check` runs in CI as the new `ops-drift` job (self-fixtures a temp root when the `OPS_LIVE_ROOT` repository variable is unset, gates the configured target when it is set); harness neutrality enforces fallback completeness (AC-HRN-008..014, replacing table-membership-only). docs/08 re-verified (`120 passed` unit; `RESULT: PASSED — 33 check(s) passed`; `tests/run.sh` PASSED; `ops-drift` green under `act` in both modes) and its verdict moves `partial` → `works`, with the residual live-client gap stated as scope, not failure. |