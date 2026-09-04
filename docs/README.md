# docs/ — Empirical Status Index

> Funnel stage 6 catalog (see *Document Funnel* in `AGENTS.md`). One row per
> `docs/NN-slug.md`. **Maintained via the `coding-agents-docs-guideline` skill** —
> the same skill invocation that writes or updates a doc updates its row here.
>
> Scope: this file indexes the **empirical layer only**.
> - Intent (`docs/prd/`) is indexed by [PRD.md](../PRD.md#quick-reference) — do not duplicate it here.
> - Gaps (`docs/gaps/`) are transient and self-listing — see [docs/gaps/README.md](gaps/README.md).
> - Knowledge (`kb/`) has its own llm-wiki catalog — see [kb/index.md](../kb/index.md).

## Status Docs

| # | Topic | Verdict | Updated | Covers | PRD | Gaps |
|---|-------|---------|---------|--------|-----|------|
| 01 | [Service Architecture](01-service-architecture.md) | partial | 2026-09-02 | `service/`, `docker-compose.yml`, `tests/{unit,integration,e2e}`, `.github/workflows/` | [01-template-scaffold-ci](prd/01-template-scaffold-ci.md) | — |
| 02 | [Autoresearch Template Contract](02-autoresearch-contract.md) | works | 2026-09-04 | `program.md`, `prepare.py`, `train.py`, `results.tsv`, `tests/unit/test_{program_md,prepare_py,train_loop,val_bpb,domain_hooks}.py` | [02-autoresearch-contract](prd/02-autoresearch-contract.md) | [02-contract-files-missing](gaps/02-contract-files-missing.md) — resolved |
| 03 | [Funnel & KB Governance](03-funnel-kb-governance.md) | works | 2026-09-04 | `AGENTS.md`, `PRD.md`, `kb/`, `docs/gaps/`, `tests/unit/test_{funnel_structure,kb_layout,gaps_lifecycle}.py`, `.github/workflows/{ci,sources-readonly}.yml` | [03-funnel-kb-governance](prd/03-funnel-kb-governance.md) | [03-governance-tests-missing](gaps/03-governance-tests-missing.md) — resolved |
| 04 | [Examples Corpus](04-examples-corpus.md) | works | 2026-09-04 | `kb/raw/` (13 sources), `kb/{concepts,entities,comparisons}/` (14 pages), `tests/unit/test_{corpus_integrity,kb_synthesis}.py` | [04-examples-corpus](prd/04-examples-corpus.md) | [04-corpus-tests-missing](gaps/04-corpus-tests-missing.md) — resolved |

`01` is `partial`, not `works`: its *What Fails* lists cold-start latency in the
integration fixture, no host port binding, and an E2E job that must not be run under
`act` on a host serving this compose project. `02`—`04` were verified 2026-09-04 with
the contract implementation wave: all `AC-TPL-*`/`AC-FUN-*`/`AC-EXC-*` unit tests
green (34/34, see each doc's *Verification*).

**Verdict vocabulary** — copy the net verdict from the doc's own *Verdict* section:

| Verdict | Meaning |
|---------|---------|
| `works` | Verified end to end; no known failures |
| `partial` | Some paths verified, some fail — *What Fails* section is non-empty |
| `broken` | Primary path fails; do not build on it until resolved |
| `stale` | Last verification predates a change to the code it covers — re-verify before citing |

## Rules

1. **Every `docs/NN-*.md` has exactly one row.** A doc with no row is invisible to the
   next agent; a row with no doc is a lie. Both are defects.
2. **`NN` is unique and shared across the funnel.** `docs/NN-slug.md`,
   `docs/prd/NN-*.md`, and `docs/gaps/NN-*.md` reuse the same number for the same
   topic, so an agent can walk intent → gap → reality by number alone.
3. **`Updated` is the last *verification* date**, not the last text edit. Editing prose
   does not refresh it; re-running the verification commands does.
4. **A `stale` or `broken` verdict is a required read** before touching the code it
   covers — that is the point of this file.