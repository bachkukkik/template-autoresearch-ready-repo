# PRD 28 — Veteran Layer: the Template Carries Decisions, Not Only Code

> Intent: a repo that adopts this template should inherit the **judgment** of the
> instance that already paid for it, not only its contracts. This PRD states the
> portable decisions as a numbered register, sorts every capability into three
> layers so an adopter knows what to inherit and what to configure, and makes the
> register mechanically checkable so it cannot rot into prose.
> **Domain:** `vet` — the veteran layer. **Canonical test:**
> `tests/unit/test_veteran_register.py` (`AC-VET-001..008`).
> **Stage 6:** `docs/28-veteran-layer.md` (pending).
> **Grounding:**
> [veteran-decision-register](../../kb/concepts/veteran-decision-register.md),
> [claim-reader-alignment](../../kb/concepts/claim-reader-alignment.md),
> [raw capture](../../kb/raw/articles/2026-11-26-veteran-decisions.md).
> **Builds on:** PRD 17 (engine), PRD 20 (evals), PRD 21 (unattended recipe),
> PRD 22 (target profile), PRD 23 (command registry). It changes no default.

## Context

The template already carries the contracts a loop needs: the keep/discard
engine, the eval layer, the target profile, the objective and run records, the
command registry, the unattended recipe. What it does not carry is the set of
decisions those contracts were *shaped by* — and that absence has an observable
cost.

**The evidence is an adopter that forked instead of followed.** A second repo
built on this template grew its own referee, its own league economy, its own
round runner and its own overnight supervisor, each as a new PRD: roughly 2,361
lines of intent that re-derive contracts this template already owns. It did not
do that out of carelessness. The template had no rule saying which layer belongs
to the adopter, so the cheapest path was to re-build the layer above the engine.

**The mature instance, for scale.** One downstream repo has played 38 numbered
seasons, written 22 tracked close records and 75 rounds, and its arena package
is 25,046 lines. Those numbers are the reason this PRD carries a register and
not a port: the domain arithmetic that produced them is noise in any other
domain.

**Three holes the register names outright**, each already visible in this tree:

1. The engine has no claim path. `prompt.py` asks for a `CHANGE:` line and
   nothing else, so a trial can never be right *or* wrong in advance — only
   recorded after the fact.
2. `decide.py` states its own defect in its docstring: `Z = 1.96` is the
   asymptotic quantile, "a future PRD may switch to `t`-based margins", and the
   smallest honest sample (two repeats) has a true 95% quantile of 12.706.
3. `scripts/local-ci.sh` reads act's exit code and the `Job failed` marker, but
   not the skipped-job marker. A job that never ran reports `pass`.

## The layer model

Every capability belongs to exactly one layer. The rule is the point.

| Layer | What it is | Fate in this template |
|---|---|---|
| 0 — core | funnel, CI, test tiers, engine, records, registry, recipe | inherit verbatim |
| 1 — instruments | domain-neutral measurement and claim machinery: what a reading is, how a claim is graded, what a trial costs | inherit; parameterised by the target profile |
| 2 — game | the domain's own economics: scoring, pricing, seats, seasons, ranking | **configure downstream, never fork** — ship the contract only |

Layer 2 is not forbidden; it is *located*. An adopter's game is legitimate,
and it must name three things the template gives it — a declared target
profile, a referee command that prints one parseable number per leg, and the
evaluator hash taken at both ends of a round — and must not re-declare the
verify/guard/record/recipe contracts that already exist here. When an
adopter's game re-declares one of those, the defect is the template's: it never
said where the game lives.

## The register

Twenty rules. `Earned by` is the failure that taught the rule; `Enforcement` is
the only place this repo may claim the rule is live.

| ID | Rule | Earned by | Enforcement | Source |
|---|---|---|---|---|
| VD-01 | An unobserved trial yields no reading, never a zero. | a review priced a dead seat's leg up while the moving leg went down | `test: tests/unit/test_engine_loop.py` | `docs/29-league-season25.md` |
| VD-02 | Refuse to start what the remaining wall cannot fund. | seat slots granted iterations each call ran one of | `test: tests/unit/test_engine_loop.py` | `docs/26-league-season19.md` |
| VD-03 | A claim is readable only by a reader matching the harness's real output format. | two seasons graded blind while both agents printed the claim | `test: tests/unit/test_hypothesis_claim.py` | `docs/41-league-season35.md` |
| VD-04 | Accept the harness's typography: U+2212, escaped newlines. | `PREDICT: -1` written with a minus `float()` refused | `test: tests/unit/test_hypothesis_claim.py` | `docs/42-league-season36.md` |
| VD-05 | Small-n margins use the t quantile; z is asymptotic. | the same pair read keep under z and inconclusive under t | `test: tests/unit/test_engine_decide.py` | `docs/prd/24-hypothesis-driven-loop.md` |
| VD-06 | Size a brief to its own gate's margin. | one annotation asked against a 4.3-bullet margin | `declared: none` | `docs/41-league-season35.md` |
| VD-07 | A metric declares direction, unit, command, floor, exploit, probe. | a leg priced with no noise floor and no probe | `test-partial: tests/unit/test_engine_objective.py` | `docs/25-league-season18.md` |
| VD-08 | Retire a metric a census shows unwinnable. | zero honestly winnable services, rejected as a leg three times | `declared: none` | `docs/41-league-season35.md` |
| VD-09 | A pointer is not proof: the verifier must cite the same AC id. | five payloads naming one test that asserts nothing about the criterion | `declared: none` | `docs/43-league-season37.md` |
| VD-10 | Price what moved, not what was attempted. | a close that priced the moving leg down and the unmoved leg up | `test-partial: tests/unit/test_engine_decide.py` | `docs/41-league-season35.md` |
| VD-11 | Re-establish and re-measure the base before paying. | a promote PR deleted the trunk the round was measured on | `declared: none` | `docs/42-league-season36.md` |
| VD-12 | One writer per target: consolidate mutating jobs onto one router. | two hourly schedulers firing into one repo, blind to each other | `declared: none` | `docs/45-cron-overlap-consolidation.md` |
| VD-13 | Schedules are intervals plus an in-code window, never an unparsed cron. | a job reading active with a null next-run, dead in fact | `test: tests/unit/test_supervisor_recipe.py` | `docs/45-cron-overlap-consolidation.md` |
| VD-14 | A skipped job is a failure. | act exiting 0 having run nothing | `test: tests/unit/test_local_ci_guard.py` | `docs/46-measurement-coverage.md` |
| VD-15 | Deterministic first, LLM last; the ceiling lives in code. | a bot told its ceiling in prose could still merge to main | `declared: none` | `docs/prd/25-steward-situation-router.md` |
| VD-16 | Facts fail closed: a missing fact never satisfies a rule. | an unclassified reading that would have silenced a red gate | `declared: none` | `docs/43-steward-uat-red-accuracy.md` |
| VD-17 | Digest the facts so a repeat fire is recognised and stopped. | one unchanged fact set re-fired eight times in 24 h | `declared: none` | `docs/43-steward-uat-red-accuracy.md` |
| VD-18 | Landed gates payment; a reverted seat settles unpaid. | both seats paid for a trunk that failed its guard | `test-partial: tests/unit/test_engine_loop.py` | `docs/27-league-season22.md` |
| VD-19 | Salvage a dead agent's tree, measure it, never read it as a refutation. | a seat's 30 to 0 win reverted unread because its agent timed out | `test: tests/unit/test_engine_loop.py` | `docs/40-league-season34.md` |
| VD-20 | The record measures itself: fidelity, coverage, attempt ledger. | a retried round overwrote its own token ledger | `test-partial: tests/unit/test_engine_record.py` | `docs/46-measurement-coverage.md` |

Two entries correct the brief that requested this register, and the correction
is part of the record: **VD-18**'s stronger clause ("the guard re-runs after a
revert") is contradicted by the veteran's own season-22 document, which lists
*no re-run* among the fix's known limits — the adoptable half is
landed-gates-payment. The scale figure is **38 registered seasons**, not 46;
the tree records 38.

## Scope

In scope: the register above; the structural test that holds it; the
layer-model section in `ADOPTING.md`; the skipped-job guard in
`scripts/local-ci.sh` (VD-14); one gap file naming every `declared` row and who
closes it.

Out of scope, explicitly: the game layer (no `league/`, no economy, no seats);
the steward router (PRD 25 downstream — its rules stay `declared` here); any
per-domain metric.

## Success Criteria

- **SC-vet-1 — The register is a table a machine can read.** PRD 28 carries a
  markdown table whose rows begin `| VD-NN |`, and it parses to exactly twenty
  rows with unique, contiguous ids `VD-01`..`VD-20`. _Verify:_
  `tests/unit/test_veteran_register.py` (AC-VET-001, AC-VET-006).
- **SC-vet-2 — No row may be blank.** Every row carries five non-empty cells:
  id, rule, earned-by, enforcement, source. A row with an empty cell fails
  naming the id and the column. _Verify:_ `tests/unit/test_veteran_register.py`
  (AC-VET-002).
- **SC-vet-3 — An `enforced` claim names something that exists.** A row whose
  enforcement starts `test:` or `test-partial:` names a repo-relative test path
  that exists in the tree; a missing path fails naming the id and the path.
  _Verify:_ `tests/unit/test_veteran_register.py` (AC-VET-003).
- **SC-vet-4 — A `declared` row is named in the gap that defers it.** A row whose
  enforcement is `declared:` is listed by id in
  `docs/gaps/28-veteran-rules-unenforced.md`, and that file names the layer or
  PRD that would close it; an unlisted id fails. _Verify:_
  `tests/unit/test_veteran_register.py` (AC-VET-004).
- **SC-vet-5 — The register cannot depend on a machine.** No cell contains an
  absolute path, `scratchpads/`, a `..` traversal, or a sibling checkout's name;
  a `Source` is either a repo-relative path or an `https://` URL. This is the
  check that keeps the register alive on a fresh clone. _Verify:_
  `tests/unit/test_veteran_register.py` (AC-VET-005).
- **SC-vet-6 — The layer rule is stated where an adopter reads it.**
  `ADOPTING.md` carries a *Layer model* section naming the three layers, and it
  says a game layer is configured downstream and never forked. _Verify:_
  `tests/unit/test_veteran_register.py` (AC-VET-008).
- **SC-vet-7 — A skipped job fails local CI.** `scripts/local-ci.sh` marks a job
  `FAIL` when act exits 0 but its log carries a skip marker (act's
  `Skipping unsupported platform`, or a `Job skipped` line), prints the reason,
  and exits non-zero. A job that genuinely ran still passes. _Verify:_
  `tests/unit/test_local_ci_guard.py` (AC-VET-007).
- **SC-vet-8 — The fix is behavioural, not a string match.** The test runs the
  real script against a stub `act` on `PATH`: one stub exits 0 having written a
  skip marker (expect exit 1, `FAIL`), one exits 0 having written a clean log
  (expect exit 0, `pass`). _Verify:_ `tests/unit/test_local_ci_guard.py`
  (AC-VET-007).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-vet-1 | AC-VET-001, AC-VET-006 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-2 | AC-VET-002 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-3 | AC-VET-003 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-4 | AC-VET-004 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-5 | AC-VET-005 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-6 | AC-VET-008 | `tests/unit/test_veteran_register.py` | unit |
| SC-vet-7 | AC-VET-007 | `tests/unit/test_local_ci_guard.py` | unit |
| SC-vet-8 | AC-VET-007 | `tests/unit/test_local_ci_guard.py` | unit |

## CI/CD Gate

- Both tests are stdlib-only and hermetic: the register test reads two tracked
  files; the guard test builds a throwaway `PATH` with a stub `act` shell script
  and asserts exit codes. No Docker, no network.
- No new CI job: the unit ACs run in the existing `unit` job.
- `scripts/local-ci.sh` stays under the file-size gate; the added check is three
  lines plus one reason string.
- No new tracked root, so funnel rule 11 does not apply. `kb/` gained two concept
  pages and one raw capture in the same cycle; that PR carries `ingest`.

## Assumptions

- [ASSUMPTION] **The register belongs in a PRD, not in `docs/`.**
  `docs/NN-slug.md` is stage 6 (empirical, one verdict) and
  `test_docs_template.py` holds every file there to the eight-section shape.
  The register is intent — rules adopted, not runs observed — so it lives in its
  PRD and the stage-6 record for this PRD cites it.
- [ASSUMPTION] **A `declared` row is honest, not a failure.** Eight of the twenty
  rules presuppose a league, a payment, or a steward that this template does not
  ship. Marking them `declared` with a named gap is the honest record; shipping
  them as `test:` would be the lie.
- [ASSUMPTION] **`test-partial` is needed as a third kind.** VD-07, VD-10, VD-18
  and VD-20 have a mechanical half that runs today and a settlement half that does
  not exist without a game. The gap file names the missing half per row.

## Confidence

**High** for the register's content (every row is checked against the veteran's
tracked files, 40 of 40 quoted fragments machine-verified) and for the two
buildable enforcements. **Medium** for the layer model's boundaries: the split
between an instrument and a game is clear at the ends and arguable in the middle
(a seat's wall budget is arithmetic, but its pricing is economics).
