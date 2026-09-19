# PRD 08 — Adoption Readiness

> Intent for the adoption-readiness change set: a tracked home for artifacts deployed
> to a subject operated outside this repo, a one-command onboarding path, harness
> neutrality across Hermes / Claude Code / opencode / DeepSeek-OpenAI-compatible, and
> the seven guards that turn doctrine that was merely *stated* into doctrine that is
> *enforced*.
> Verified reality: [docs/08-adoption-readiness.md](../08-adoption-readiness.md).
> Grounded in: [document-funnel-doctrine](../../kb/concepts/document-funnel-doctrine.md),
> [template-agentic-ready-repo](../../kb/entities/template-agentic-ready-repo.md),
> [autoresearch-template-research-conclusions](../../kb/raw/articles/autoresearch-template-research-conclusions.md).
>
> **Grounding note — read this before citing a `kb/` page.** The change set originated
> in **eleven issues the downstream adopter filed against this template** (funnel
> stage 7). Those are tracked artifacts, not `kb/` knowledge: stage 3 grounds the
> *harness-adapter capability* and the *funnel/CI doctrine*, and it does not discuss
> an ops home, an onboarding script or a four-harness enumeration at all. This PRD
> names the issues as intent drivers and does **not** fake a `kb/` citation for them.
> Their working capture is a gitignored scratchpad, which funnel rule 6 makes
> uncitable — see *Assumptions*.

## Context

The template's own doctrine was ahead of its enforcement. `AGENTS.md` states the funnel
rules, the harness adapter and the three-tier test contract, and `kb/` grounds them
([document-funnel-doctrine](../../kb/concepts/document-funnel-doctrine.md): "One
canonical `AGENTS.md`; every harness … resolves to it via symlinks, with repo-scoped
skills in `.agents/`. Missing mechanism ≠ waived rule"), but an adopter who took the
template to production found eleven places where a rule was a sentence rather than a
gate. Five classes of gap mattered:

- **No home for the operational subject.** An autonomous-research program deploys
  artifacts — a scheduler entry, a wrapper script, a board/graph definition, environment
  manifests — to a system *outside* the repo. None of those are knowledge (stage 3),
  intent (stage 4), a gap (stage 5) or verified reality (stage 6), so funnel rule 1 made
  them a defect and the `doctrine` job had nothing to check them against.
- **Onboarding was a list of steps, not a check.** A fresh clone could be broken
  (Windows-cloned symlinks as plain text, a gitignored doctrine path) with nothing to
  run that says so in one line.
- **Doctrine assumed one harness.** The capability tables were written from one agent's
  seat; a DeepSeek/OpenAI-compatible harness with no skill mechanism and no slash
  command had no stated path, and nothing failed if a harness silently dropped out of
  the tables.
- **Documentary invariants were stated, not tested.** Stage-6 doc shape, What
  Fails ↔ Resolution parity, one catalog row per doc, `docs/prd/NN` ↔ `PRD.md`
  alignment and cross-layer `NN` uniqueness were all "hard rules" with no test behind
  them.
- **Two silent-green paths in CI.** A new tracked root nobody declared passed the
  `doctrine` job green, and a whole-tier integration skip read as success.

**Target users:** the downstream adopter operating a research program from a clone of
this template, maintainers reviewing changes, and every coding agent working across
harnesses. **Constraints:** the ops home is repo-canonical with the live side a deploy
target only; the sync tool's destructive mode is gated behind an explicit confirmation
env var; every new guard is hermetic (stdlib + file reads) so it runs on any runner;
no new CI job — the guards land in the existing `unit` / `integration` / `doctrine`
jobs.

## Success Criteria

- **SC1** — **The operational subject has a tracked home and a safe sync tool.** `ops/`
  is the canonical home for artifacts deployed outside the repo; `ops/sync.sh` has a
  read-only `--check` (drift in both directions, live-only files reported with an
  explicit path-scoped allowlist for generated runtime state) and an `--apply` that
  refuses without `OPS_APPLY_CONFIRM=1`. Every deployable root fails loudly when it is
  absent, unenumerable or empty. _Verify:_ `tests/unit/test_ops_sync.py`
  (AC-OPS-001..010) + the `ops-drift` job in `.github/workflows/ci.yml`, which runs
  `ops/sync.sh --check` (self-fixturing a temp target when the `OPS_LIVE_ROOT`
  repository variable is unset; gating the configured target when it is set).

- **SC2** — **Documentary invariants are enforced, not merely stated.** Every
  `docs/NN-slug.md` carries the eight stage-6 sections in the fixed order, `What Fails`
  and `Resolution` carry equal top-level bullet counts, every NN doc has exactly one row
  in `docs/README.md`, every `docs/prd/NN-*.md` appears in `PRD.md`'s Quick Reference
  and vice versa, and every `NN` under `docs/gaps/` — live or archived — has a topic
  file at that number. _Verify:_ `tests/unit/test_docs_template.py` (AC-DOC-001..016).

- **SC3** — **A new tracked root cannot pass CI silently.** The `doctrine` job derives
  every tracked top-level directory and root file from the git index and fails naming
  any root missing from its `DOCTRINE_ROOTS` list; `AC-FUN-003` keeps that literal list
  from drifting away from `AC-FUN-002`'s `REQUIRED_DIRS` in either direction.
  _Verify:_ `tests/unit/test_funnel_structure.py` (AC-FUN-003) + the `doctrine` job's
  tracked-root coverage step in `.github/workflows/ci.yml`.

- **SC4** — **The gap lifecycle survives an empty open set.** With zero live
  `docs/gaps/NN-*.md` files the catalogue check still proves it reached real files via
  the archive, and a malformed gap (a documented gap with no `Resolution`) is still
  reported rather than passed vacuously. _Verify:_ `tests/unit/test_gaps_lifecycle.py`
  (AC-FUN-021) + `tests/unit/test_docs_template.py` (AC-DOC-004/AC-DOC-006).

- **SC5** — **Closed gaps keep their resolution record.** Gaps 03 and 07 are closed by
  this change: their files live under `docs/gaps/_archive/` with path structure
  preserved (never deleted, `NN` never reused), the live open-gaps table correctly
  reports the empty set, and the re-ingested `kb/raw` articles the 03 closure rests on
  are sha-stamped and verified. _Verify:_ `tests/unit/test_docs_template.py`
  (AC-DOC-004 — the row + archive scan; AC-DOC-006 — cross-layer `NN`),
  `tests/unit/test_corpus_integrity.py` (AC-EXC-001/002 — sha stamps on the articles and
  transcripts).

- **SC6** — **A host-dependent test cannot silently decide a tier's verdict.** The
  `integration` job fails when its junit artifact is missing or unparseable, and when
  the tier executed zero tests or skipped all of them; the shared preflight in
  `tests/conftest.py` (`resolve_ambient` / `require_tool`) makes a missing ambient
  binary or interpreter skip **loudly, naming what was resolved and why**; the same
  preflight is applied module-wide in `tests/unit/test_ops_sync.py` (its
  `require_tool("bash")` fixture). _Verify:_ the `integration` job's junit guard step
  in `.github/workflows/ci.yml` + the `resolve_ambient`/`require_tool` preflight in
  `tests/conftest.py` (no test ID — see *Assumptions*).

- **SC7** — **All four harnesses are first-class, and none needs a slash command.**
  `AGENTS.md`'s Harness Adapter names Hermes, Claude Code, opencode and
  DeepSeek/OpenAI-compatible plus a generic fallback, binds each to an entry instruction
  file and the host-level-skills capability, states the inline-`SKILL.md` fallback for a
  harness with no skill mechanism, and states that the canonical cross-harness contract
  is the `sub1`–`sub4` phase blocks + phase table with `/goal` marked Hermes-only;
  `README.md`'s Harness Support table names the same four so the pair cannot drift.
  Beyond the tables, every Hermes-only mechanism `AGENTS.md` names must sit in a
  context that also documents its non-Hermes fallback, and a missing mechanism must
  never waive a skill gate (the inline-`SKILL.md` escape). _Verify:_
  `tests/unit/test_harness_neutrality.py` (AC-HRN-001..007 — the two catalog tables and
  their negative controls; AC-HRN-008..014 — fallback completeness and the skill-gate
  escape).

- **SC8** — **A fresh clone can be proven healthy in one command.**
  `bash scripts/verify-clone.sh` is read-only (no files, no git index, no git config),
  prints one PASS/FAIL line per check, and cannot print success over a run that
  performed no checks. _Verify:_ `tests/unit/test_verify_clone.py` (AC-VC-001..008 —
  the real repo passes with a non-zero check count, the run is pinned read-only, and
  five broken-clone negative controls each exit 1 naming the offender) plus the
  `doctrine` job in `.github/workflows/ci.yml`, which enforces the same invariants on
  every PR.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| `ops/` home + sync tool: loud on an absent/empty root, `--check` drift in both directions, `--apply` gated behind `OPS_APPLY_CONFIRM=1`, symlinked root deployed through; `--check` run in CI with drift proven detectable | `tests/unit/test_ops_sync.py` + `.github/workflows/ci.yml` (`ops-drift`) | AC-OPS-001..010 + the `ops-drift` job |
| Documentary invariants enforced (eight-section order, fails↔resolution parity, catalog rows, cross-layer `NN`) | `tests/unit/test_docs_template.py` | AC-DOC-001..016 |
| A new tracked root cannot pass the `doctrine` job silently; the job's list and `AC-FUN-002` cannot drift | `tests/unit/test_funnel_structure.py` + `.github/workflows/ci.yml` (`doctrine`) | AC-FUN-003 + the `doctrine` tracked-root coverage step |
| Gap lifecycle: a legitimately empty open set still reports a malformed gap | `tests/unit/test_gaps_lifecycle.py` | AC-FUN-021 |
| Closed gaps 03/07 archived with their records; re-ingested `kb/raw` articles sha-verified | `tests/unit/test_docs_template.py`, `tests/unit/test_corpus_integrity.py` | AC-DOC-004, AC-DOC-006, AC-EXC-001/002 |
| A host-dependent test cannot decide a tier's verdict; a whole-tier skip is a red run | `.github/workflows/ci.yml` (`integration`) + `tests/conftest.py` + `tests/unit/test_ops_sync.py` | `integration` junit guard step; `resolve_ambient`/`require_tool` preflight (module-wide `require_tool("bash")` in `test_ops_sync.py`) |
| All four harnesses first-class; no harness needs a slash command; README ↔ AGENTS.md cannot drift; every Hermes-only mechanism documents a fallback and a missing mechanism never waives a skill gate | `tests/unit/test_harness_neutrality.py` | AC-HRN-001..007 (negative controls) + AC-HRN-008..014 (fallback completeness, skill-gate escape) |
| A fresh clone is proven healthy in one read-only command, broken-clone negative controls included | `tests/unit/test_verify_clone.py` + `.github/workflows/ci.yml` (`doctrine`) | AC-VC-001..008 + the `doctrine` tracked-path / tracked-root coverage steps |

## Assumptions

- **The eleven upstream issues are tracked artifacts, not KB knowledge.** They are the
  intent drivers for this PRD (funnel stage 7). Their working capture sits in a
  gitignored `scratchpads/` file, which funnel rule 6 makes uncitable, so no `kb/` page
  is cited for them and no issue number is quoted here. Where a claim needed grounding
  it was re-derived from tracked files (`AGENTS.md`, `README.md`, `ci.yml`,
  `tests/conftest.py`) or from the KB's doctrine pages. `[ASSUMPTION]`
- **`scripts/verify-clone.sh` is test-covered.** `tests/unit/test_verify_clone.py`
  (AC-VC-001..008) runs the real repo's copy and five broken-clone copies built under
  `tmp_path`, so SC8 points at a real test ID. The script's own zero-check guard is
  unreachable from outside the script — nothing a caller does can force the count to
  zero — so it is pinned where it is observable, not faked: AC-VC-001 asserts the
  parsed check count is non-zero and AC-VC-002 asserts the run changed nothing.
- **The ops `--check` mode runs in CI.** The `ops-drift` job runs `ops/sync.sh --check`.
  With the `OPS_LIVE_ROOT` repository variable unset it self-fixtures (a temp root
  `--apply`ed, checked green, then one artifact mutated and required to go red naming
  it); with the variable set, both write steps are `if:`-gated off and it becomes a real
  read-only gate on the adopter's own target. `--apply` is never run against a
  configured target from CI.
- **Harness neutrality is asserted at the document level; the live-client half is
  stated scope.** `tests/unit/test_harness_neutrality.py` (AC-HRN-001..014) asserts the
  catalog tables *and* fallback completeness in `AGENTS.md`; it does not drive an
  opencode, Claude Code or DeepSeek client. No such client is pinned in the repo, two
  are closed and paid, and driving one would move the `unit` tier's verdict onto the
  host — the ambient-dependency class that tier bans. A project wanting the live-client
  half would add it as an opt-in integration-tier entry behind `RUN_INTEGRATION_TESTS=1`.
  `[ASSUMPTION]`
- **The four-harness enumeration is repo-artifact doctrine, not KB knowledge.** The KB
  grounds the *capability* adapter ("a missing mechanism never waives the rule") and the
  funnel/CI doctrine; it names Hermes, Claude Code, Copilot and "generic" and does not
  enumerate opencode or a DeepSeek/OpenAI-compatible harness. The equality claim is
  grounded in `AGENTS.md`'s Harness Adapter + *Per-harness rows* and `README.md`'s
  *Harness Support*, which is exactly what SC7 pins. `[ASSUMPTION]`
- **One new CI job.** The `ops-drift` job is added to `.github/workflows/ci.yml`; every
  other guard lands in an existing job (`unit`, `integration`, `doctrine`) or in
  `tests/conftest.py`.

## Confidence

**High** — the change set is shipped and green: `tests/unit/test_ops_sync.py`
(AC-OPS-001..010), `tests/unit/test_docs_template.py` (AC-DOC-001..016),
`tests/unit/test_funnel_structure.py` + `tests/unit/test_gaps_lifecycle.py`
(AC-FUN-001..004, 021), `tests/unit/test_harness_neutrality.py` (AC-HRN-001..014),
`tests/unit/test_verify_clone.py` (AC-VC-001..008) and
`tests/unit/test_corpus_integrity.py` all pass (`120 passed` for the unit tier), and
`docs/08-adoption-readiness.md` records the run. Seven of the eight SCs point at a real
test ID; SC6 points at a named CI step plus the `tests/conftest.py` preflight rather
than a test ID, because its subject is a runner artifact, not a unit assertion. The one
residual seam is scope, not a gap: the harness guard proves the document every harness
reads and no pinned third-party client exists to drive the live-client half.

## CI/CD Gate

All tests run in CI per `.github/workflows/ci.yml`. No PR merges with a red test.
This PRD adds **one CI job**, `ops-drift`, which runs `ops/sync.sh --check` (see SC1 and
*Assumptions*); the new unit guards run in the existing `unit` tier
(`test_ops_sync.py`, `test_docs_template.py`, `test_harness_neutrality.py`,
`test_funnel_structure.py`, `test_gaps_lifecycle.py`, `test_verify_clone.py`,
`test_corpus_integrity.py`), the `integration` job gained its junit guard step, and the
`doctrine` job's tracked-root coverage step is what SC3 and SC8 rest on. `bash
tests/run.sh` must be `PASSED` locally before a PR is opened (`AGENTS.md` §6).
