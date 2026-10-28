# template-autoresearch-ready-repo — Product Requirements Document

> Version: 2.0.0
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
| 07 | CodeGraph Adoption | [docs/prd/07-codegraph-adoption.md](docs/prd/07-codegraph-adoption.md) | Active — instruction-surface adoption, verified in [docs/07](docs/07-codegraph-adoption.md); all six SCs carry test IDs (`tests/unit/test_codegraph_adoption.py`, AC-CG-001..006, plus the opt-in `tests/integration/test_codegraph_live.py`, AC-CG-201..202), and `.codegraph/` is now ignored wholesale like upstream |
| 08 | Adoption Readiness | [docs/prd/08-adoption-readiness.md](docs/prd/08-adoption-readiness.md) | Active — `ops/` home + sync tool, onboarding path, harness neutrality and seven new guards; seven of eight SCs carry a test ID (`tests/unit/test_{ops_sync,verify_clone,docs_template,harness_neutrality,funnel_structure,gaps_lifecycle,corpus_integrity}.py`), SC6 a named CI step + the `tests/conftest.py` preflight, and SC1/SC3/SC8 rest on the new `ops-drift` and existing `doctrine` CI jobs; verified in [docs/08](docs/08-adoption-readiness.md) (verdict `works`) |
| 11 | Worked Examples | [docs/prd/11-worked-examples.md](docs/prd/11-worked-examples.md) | Active — reproducible scripted reference runs (ex1–ex3) + the one LIVE LLM run (ex4) (`AC-EXA-*`); gap [11](docs/gaps/11-examples-unreproducible.md); verified in [docs/11](docs/11-worked-example-pipelines.md) |
| 13 | Output-Medium Doctrine | [docs/prd/13-output-medium-doctrine.md](docs/prd/13-output-medium-doctrine.md) | Active — `AGENTS.md` §7 standing order + kb grounding + AC-OM/AC-CTX tripwires; verified in [docs/13](docs/13-output-medium-doctrine.md) |
| 14 | gen-env Script | [docs/prd/14-gen-env-script.md](docs/prd/14-gen-env-script.md) | Active — `scripts/gen-env.py` + 5 hermetic unit tests (`AC-GEN-001..005`); verified in [docs/14](docs/14-gen-env-script.md) |
| 15 | STE-style Audit | [docs/prd/15-ste-audit.md](docs/prd/15-ste-audit.md) | Active — `scripts/audit-ste.py` + `AC-STE-001..003`; verified in [docs/15](docs/15-ste-audit.md) |
| 16 | Quality Controls | [docs/prd/16-quality-controls.md](docs/prd/16-quality-controls.md) | Active — ported from the foundation template's PRD 06 (`AC-QC-001..012`); gap [16](docs/gaps/16-quality-controls-not-adopted.md); verified in [docs/16](docs/16-quality-controls.md) |
| 17 | Autoresearch Engine | [docs/prd/17-autoresearch-engine.md](docs/prd/17-autoresearch-engine.md) | Active — generic harness-pluggable engine (`engine/`, `AC-ENG-*`) + real-OSS target ex5 (`AC-EXA-040..050`); verified in [docs/17](docs/17-autoresearch-engine.md) |

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
| 1.6.0 | 2026-10-03 | Foundation-template alignment (new rules adopted from `bachkukkik/template-agentic-ready-repo`; provenance note: funnel rule 11 and `ops/` are this repo's own extensions, not baseline adoptions): PRD-13 output-medium doctrine — `AGENTS.md` §7 standing order (prose → controlled English → diagram → HTML → explainer video; code-first render → parse; discardable artifacts) with kb grounding and `AC-OM-001..003`; the `AC-CTX-002` host-pinned cap + `AC-CTX-003` 500-char headroom floor, met by compressing two non-load-bearing AGENTS.md sections (the *Skill-to-phase mapping* table → `README.md` § Skills; *Ops artifacts* → one line); PRD-14 `scripts/gen-env.py` (`AC-GEN-001..005`); PRD-15 `scripts/audit-ste.py` ("80% to ASD-STE100" prose gate, `AC-STE-001..003`); `tests/run.sh` e2e auto-start; `docker-compose.host-ports.example.yml` + the funnel rule 11 multi-file edit. Verified in docs/13–15. |
| 1.6.1 | 2026-10-03 | Drop `docker-compose.host-ports.example.yml` (an upstream auxiliary, not needed here) and its funnel-rule-11 token from the `doctrine` job's `DOCTRINE_ROOTS`. Local-CI fix: the `doctrine` tracked step now passes a root that is tracked **or** present on disk, so `act -j doctrine` no longer false-reds on a working tree that holds a not-yet-committed root; and `scripts/local-ci.sh` runs the five pre-PR jobs one `act` invocation each (act's `-j` is not a repeatable array) and refuses `e2e`. Verified in docs/08. |
| 1.7.0 | 2026-10-16 | Improvement wave (self-audit + 19-repo OSS autoresearch landscape): PRD-02 SC7–SC11 — budget enforced in code (`stop_reason`), evaluator-owned `decide()` with a noise floor, truthful `--results`, `prepare.py --check-ledger`, measured memory, `AC-TPL-014` sha256 pin on the frozen evaluator; PRD-11 worked examples made reproducible (`train_baseline.py` + replay tests, `AC-EXA-*`, scripted-reference-run provenance, seed-note corrected); PRD-08 SC9–SC12 — skills vendored or install-sourced (`AC-HRN-015..017`), `GEMINI.md` entry point, harness set as a floor, AGENTS.md budget restated as a repo budget; PRD-16 quality controls ported from the foundation template (`AC-QC-001..012`, `qc-gate` + `zizmor`, governance files); new `kb/` sources (OSS landscape, self-audit, QC dossier; methodology raw superseded de-identified). Gaps 02/08/11/16 opened on this branch, resolutions implemented here, closed at merge; gap 07 closed to issue #29. Upstream alignment (foundation @ 81f2192): the Lifecycle section (Development D0–D4 + Delivery sub1–sub4 with the opt-in UAT sub4/sub5 variant, shared footer stated once) with the layout guard `AC-LC-001..003`; action pins → checkout v7.0.1 / setup-python v7.0.0; pytest 9.1.1; service image → python:3.14-slim (docker build + /health verified). |
| 1.8.0 | 2026-10-17 | PRD-07 closure (issue #29): SC4/SC5 gain an opt-in live test, `tests/integration/test_codegraph_live.py` (AC-CG-201 `codegraph sync` → status → query; AC-CG-202 `codegraph affected --stdin -f '<glob>'` maps a changed file to its test), resolved through the `tests/conftest.py` `require_tool` preflight so a host — or CI runner — without the codegraph binary reports skips, not reds; PRD-07 corrects the "affected maps nothing" claim (a test glob maps this layout; the default filter does not). Upstream alignment: `.gitignore` ignores `.codegraph/` wholesale, `git rm` retires the `.codegraph` placeholder file, and the rule-11 tracked-root edit drops `.codegraph` from the `doctrine` job's `DOCTRINE_ROOTS` and from `AC-FUN-002`; AC-CG-004 is re-aimed at the index (nothing under `.codegraph/` is tracked). Verified in docs/07 + docs/12. |
| 1.9.0 | 2026-10-17 | PRD-11 SC7 — the **ex4 live-LLM worked example**: a real model proposes edits to a small repo under a binding `TIME_BUDGET = 5` s ceiling, and the recorded transcript replays the run offline. New `contract/examples/ex4-llm-repo-speedup/` — frozen `prepare.py` + `target/tests.py`, one agent-edited `target/solution.py` (+ `solution_baseline.py`), `agent_driver.py` (OpenAI-compatible loop keyed on env-var NAMES, `--from-baseline`/`--replay`), vendored `results.tsv` + `transcript.jsonl`, `AC-EXA-011..033` (`tests/unit/test_examples_ex4.py`) — review hardening, with a parent-verified gate and parent-side per-rep timing; `contract/examples/README.md` names ex4 the one live run. The budget binds (baseline 36.05 s = 7.2× the budget; row `stop_reason: budget`/`status: timeout`); the recorded 2026-10-17 run (model `opencode-go/kimi-k3`) is 5 rounds — 1 keep / 1 discard / 3 unusable (empty content, `finish_reason: length`) — stated plainly. |
| 2.0.0 | 2026-10-28 | PRD-17 — the **autoresearch engine**. Triage: the loop never improved real code (no engine, no harness-driven edits, no real target, KB ungrounded in systems that report real wins). New `kb/raw/articles/2026-10-28-autoresearch-real-world-engines.md` (15 systems incl. FAROS, CORAL, codex-autoresearch, uditgoenka, pi-autoresearch/Shopify Liquid #2056) + 8 layer-2 pages. New stdlib `engine/` — `init`/`run`/`status`/`report`/`doctor`; script-owned keep/revert; verify/guard/scope/protected files; noise floor; bounded stops; `--dry-run`; `--record`/replay; adapters for Hermes, Claude Code, opencode, DeepSeek Harness. New ex5: NLTK 3.9.1 `distance.py` under a four-stage isolated guard. Additive: PRD-02/11 contract and ex1–ex4 unchanged. |
