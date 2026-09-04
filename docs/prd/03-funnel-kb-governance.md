# PRD 03 — Document Funnel & KB Governance

> Intent for the governance layer this repo is built on: the document funnel,
> `kb/` knowledge base, harness adapter, and their CI enforcement.
> Grounded in: [document-funnel-doctrine](../../kb/concepts/document-funnel-doctrine.md),
> [template-agentic-ready-repo](../../kb/entities/template-agentic-ready-repo.md).

## Context

Every piece of writing in this repo must have exactly one home, flow in one
direction, and harden as it moves downstream (prompt → scratchpads → kb/raw → kb →
PRD → gaps → docs/NN → issues). The governance is not advisory: CI jobs enforce the
add-only `kb/raw` rule (funnel rule 3) and the tracked-doctrine rule (rules 9–10),
and harness entry points resolve through symlinks (Harness Adapter). This PRD
states the intent for the governance layer so agents and CI agree on the contract.

**Target users:** every agent and human that writes to this repo.
**Constraints:** stages 1–6 paths are the only doc homes; `kb/` layer-2 pages are
written only by llm-wiki; gaps are transient; secrets never enter `kb/` or `docs/`.

## Success Criteria

- **SC1** — No stray documents: a new `.md` outside stages 1–6 (scratchpads,
  kb/raw, kb, PRD/docs/prd, docs/gaps, docs/NN, issues) is a defect. _Verify:_
  `tests/unit/test_funnel_structure.py` (AC-FUN-001..003). `[PLANNED]`

- **SC2** — `kb/raw/**` is add-only and enforced in CI (M/D without `ingest` label
  fails); secrets never land in `kb/` or `docs/` (mirrored by the `secret-scan`
  job's kb scan). _Verify:_ `.github/workflows/sources-readonly.yml` (job
  `check-raw-readonly`), `ci.yml` job `secret-scan` step "Assert no secret values
  landed in kb/".

- **SC3** — The doctrine stays tracked and intact: `AGENTS.md`, `PRD.md`, `docs/`,
  `kb/`, `tests/`, `.agents/`, `.github/` are versioned and not gitignored, and
  every harness entry point resolves through a symlink. _Verify:_ `ci.yml` job
  `doctrine`.

- **SC4** — `kb/` layer-2 pages are never hand-written: the llm-wiki workflow is
  the only writer, and the KB layout (`SCHEMA.md`, `index.md`, `log.md`, `raw/`)
  follows the llm-wiki spec. _Verify:_ `tests/unit/test_kb_layout.py`
  (AC-FUN-011..012). `[PLANNED]`

- **SC5** — Gaps are transient: every `docs/gaps/NN-*.md` file has a `Resolution`
  section naming exactly one closing action, and open gaps are listed in
  `docs/gaps/README.md`. _Verify:_ `tests/unit/test_gaps_lifecycle.py`
  (AC-FUN-021). `[PLANNED]`

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| Funnel stage layout enforced structurally | `tests/unit/test_funnel_structure.py` | AC-FUN-001..003 |
| `kb/` add-only gate + secret-free `kb/` | `.github/workflows/sources-readonly.yml`, `ci.yml` | jobs `check-raw-readonly`, `secret-scan` |
| Doctrine tracked, entry points resolve | `.github/workflows/ci.yml` | job `doctrine` |
| KB layout matches llm-wiki spec | `tests/unit/test_kb_layout.py` | AC-FUN-011..012 |
| Gap lifecycle (Resolution required, listed) | `tests/unit/test_gaps_lifecycle.py` | AC-FUN-021 |

## Assumptions

- The CI jobs are the authoritative structural enforcement today; the `[PLANNED]`
  unit tests harden the same rules inside the pytest tier per `AGENTS.md` §5
  (every tier must have a runner — no tier is a stub). `[ASSUMPTION]`

## Confidence

**High** — the funnel and harness adapter are fully documented in `AGENTS.md`, the
KB doctrine page, and enforced by live CI jobs (`doctrine`, `sources-readonly`).

## CI/CD Gate

The `doctrine` and `secret-scan` jobs run on every PR per
`.github/workflows/ci.yml`; `sources-readonly.yml` runs on PR open/sync/label
events. No PR merges with a red gate. The `[PLANNED]` unit tests join the suite
when written (next implementation run).