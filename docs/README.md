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
| 05 | [MCP REST Service](05-mcp-rest-service.md) | works | 2026-09-18 | `service/`, `docker-compose.yml`, `tests/{unit,integration,e2e}`, `.github/workflows/` | [05-mcp-rest-service](prd/05-mcp-rest-service.md) | — (resolved; archived 2026-09-18) |
| 06 | [Concurrent Multi-Topic Service](06-multi-topic-concurrency.md) | works | 2026-09-18 | `service/src/{workspace,runner,main}.py`, `contract/` (consumed by the service), `tests/unit/test_{workspace,service_readme}.py`, `tests/integration/test_multi_topic.py`, `tests/e2e/service.bats`, `service/README.md` | [06-multi-topic-concurrent-service](prd/06-multi-topic-concurrent-service.md) | — (resolved; archived 2026-09-18) |
| 02 | [Autoresearch Template Contract](02-autoresearch-contract.md) | works | 2026-09-18 | `contract/program.md`, `contract/prepare.py`, `contract/train.py`, `results.tsv`, `tests/unit/test_{program_md,prepare_py,train_loop,val_bpb,domain_hooks}.py` | [02-autoresearch-contract](prd/02-autoresearch-contract.md) | — (resolved; archived 2026-09-18) |
| 03 | [Funnel & KB Governance](03-funnel-kb-governance.md) | works | 2026-09-18 | `AGENTS.md`, `PRD.md`, `kb/`, `docs/gaps/`, `tests/unit/test_{funnel_structure,kb_layout,gaps_lifecycle}.py`, `.github/workflows/{ci,sources-readonly}.yml` | [03-funnel-kb-governance](prd/03-funnel-kb-governance.md) | — (resolved; archived 2026-09-18) |
| 04 | [Examples Corpus](04-examples-corpus.md) | works | 2026-09-18 | `kb/raw/` (15 sources), `kb/{concepts,entities,comparisons}/` (21 pages), `tests/unit/test_{corpus_integrity,kb_synthesis}.py` | [04-examples-corpus](prd/04-examples-corpus.md) | — (resolved; archived 2026-09-18) |
| 07 | [CodeGraph Adoption](07-codegraph-adoption.md) | partial | 2026-09-19 | `AGENTS.md` (`## codegraph`), `.codegraph/` (gitignored local index), `tests/unit/test_codegraph_adoption.py`, `kb/raw/articles/codegraph-mcp-code-intelligence.md`, `kb/{concepts/agent-code-graph-search,entities/codegraph,comparisons/codegraph-vs-graphify}.md` | [07-codegraph-adoption](prd/07-codegraph-adoption.md) | — (resolved; archived 2026-09-19) |
| 08 | [Adoption Readiness](08-adoption-readiness.md) | works | 2026-09-19 | `ops/` (`README.md`, `sync.sh`, `artifacts/`, `state-allowlist.txt`), `ADOPTING.md`, `scripts/verify-clone.sh`, `tests/unit/test_{ops_sync,verify_clone,docs_template,harness_neutrality,funnel_structure,gaps_lifecycle,corpus_integrity}.py`, `.github/workflows/ci.yml` (`ops-drift` drift gate, `integration` junit guard, `doctrine` tracked-root coverage), `tests/conftest.py`, `docs/gaps/_archive/{03,07}-*.md` | [08-adoption-readiness](prd/08-adoption-readiness.md) | — (resolved; archived 2026-09-19) |

Rows 02–06 were re-verified 2026-09-18 in one pass: `bash tests/run.sh
--with-e2e` → `RESULT: PASSED` (68 unit + 16 integration + 4 e2e) and all four
local `act` jobs (`unit`, `integration`, `secret-scan`, `doctrine`) report
`Job succeeded`. The `AC-TPL-*`/`AC-FUN-*`/`AC-EXC-*` unit tests are green
(31 tests; full unit tier 68 — see each doc's *Verification*). Row 07 was
verified 2026-09-19 against the CodeGraph CLI + MCP surfaces on this machine —
see its *Verification*. Row 08 was re-verified 2026-09-19 on closure of its three
recorded failures: `bash tests/run.sh` → `RESULT: PASSED` (120 unit + 16 integration;
the e2e tier needs a container) with `bash scripts/verify-clone.sh` → `RESULT: PASSED — 33
check(s) passed`, and the `ops-drift` job green end to end under `act` in both modes —
see its *Verification*.

`01` is an intentional gap: the scaffold's CI-gate SCs are verified in `03`, and its
service SCs in `05`/`06` — see
[docs/prd/01-template-scaffold-ci.md](prd/01-template-scaffold-ci.md).

Resolved gaps are archived inside the repo, at the location and by the lifecycle
stated in [docs/gaps/README.md](gaps/README.md) (*Lifecycle* — the single statement
of it); the `Gaps` column records where one closed. A withdrawn gap leaves a
tombstone at `docs/gaps/_archive/NN-<slug>.md` rather than returning its number to
circulation.

**Verdict vocabulary** — copy the net verdict from the doc's own *Verdict* section:

| Verdict | Meaning |
|---------|---------|
| `works` | Verified end to end; no known failures |
| `partial` | Some paths verified, some fail — *What Fails* section is non-empty |
| `broken` | Primary path fails; do not build on it until resolved |
| `stale` | Last verification predates a change to the code it covers — re-verify before citing |
| `retired` | A mechanism withdrawn by decision whose code no longer exists — read for the decision record and its replacement, not to re-verify |

**Retirement lifecycle.** A retirement KEEPS the doc and its row here — the row is
the decision record. If the mechanism is later re-instated, keep the retirement
record and add the new decision on top: the history is the point.

## Rules

1. **Every `docs/NN-*.md` has exactly one row.** A doc with no row is invisible to the
   next agent; a row with no doc is a lie. Both are defects.
2. **`NN` is unique and shared across the funnel.** `docs/NN-slug.md`,
   `docs/prd/NN-*.md`, and `docs/gaps/NN-*.md` reuse the same number for the same
   topic, so an agent can walk intent → gap → reality by number alone. Numbers are
   never reused: a withdrawn gap leaves a tombstone
   (`docs/gaps/_archive/NN-<slug>.md`, `Status: withdrawn`, one-line reason) rather
   than returning the number to circulation.
3. **`Updated` is the last *verification* date**, not the last text edit. Editing prose
   does not refresh it; re-running the verification commands does.
4. **A `stale`, `broken` or `retired` verdict is a required read** before touching the
   code it covers — that is the point of this file.
