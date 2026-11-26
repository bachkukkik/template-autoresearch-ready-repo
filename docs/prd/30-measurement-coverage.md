# PRD 30 — Measurement Coverage: Cost Beside Score, and Attempts That Survive

> Intent: a run must be able to say what a keep **cost** and what it **tried**,
> not only how far the number moved. Every change here is additive: a field, a
> column, a script. Nothing changes a verdict, a default or an existing row.
> **Domain:** `mcv` — measurement coverage. **Canonical tests:**
> `tests/unit/test_engine_cost.py` (`AC-MCV-001..006`),
> `tests/unit/test_engine_attempts.py` (`AC-MCV-010..014`),
> `tests/unit/test_ci_metrics.py` (`AC-MCV-020..024`),
> `tests/integration/test_measurement_report.py` (`AC-MCV-201`).
> **Stage 6:** `docs/30-measurement-coverage.md` (pending).
> **Grounding:**
> [veteran-decision-register](../../kb/concepts/veteran-decision-register.md)
> (VD-01, VD-10, VD-20),
> [raw capture](../../kb/raw/articles/2026-11-26-veteran-decisions.md).
> **Builds on:** PRD 17 (engine), PRD 20 (evals), PRD 22 (run record).

## Context

A keep rate without a denominator is a slogan. The veteran learned this the
expensive way: a season reported its spend as `0` because the round that died
before settling was the only round that had spent anything, and a retried round
overwrote its own token ledger — so the published cost was a silent lower bound
presented as a total. Two of its own rules exist for that: an unobserved trial
yields **no reading** (VD-01), and the record must **measure itself** (VD-20).

This repository has the same shape of hole. The engine's ledger records a
verdict, a metric value, a delta and provenance, but nothing about tokens or
wall seconds, and a trial that never settles writes no row at all.
`report.py` therefore publishes `keeps` and `best` with no denominator, and
`results.tsv` cannot be used to answer the one question an operator actually
asks: *what did this idea cost per unit of improvement?*

## Scope

In: per-trial cost fields when the harness reports usage; two ratio columns
in the report; an attempt ledger for trials that never settled; one script that
turns a JUnit file into per-suite seconds.
Out: any pricing, any budget enforcement, any cross-run accounting service, any
change to the keep gate.

## Success Criteria

- **SC-mcv-1 — A settled trial carries its cost, or says it has none.** A
  `keep`/`discard`/`inconclusive` event gains `cost` = `{tokens, wall_seconds}`
  when the adapter's transcript reports usage; when it does not, both keys are
  absent — never `0`, never guessed. _Verify:_ `tests/unit/test_engine_cost.py`
  (AC-MCV-001, AC-MCV-002).
- **SC-mcv-2 — The report prints a denominator.** `report.md` gains a
  *Cost* section printing `keeps / 100k tokens` and `keeps / hour`, computed over
  settled trials only, and printing `n/a` (with the reason) when the denominator
  is unknown. `results.tsv` gains `tokens` and `wall_seconds` columns that are
  empty rather than zero when unknown. _Verify:_ `tests/unit/test_engine_cost.py`
  (AC-MCV-003, AC-MCV-004), `tests/integration/test_measurement_report.py`
  (AC-MCV-201).
- **SC-mcv-3 — Cost never changes a verdict.** Feeding a trial with a very large
  or a very small cost leaves the ledger's `verdict`, `delta` and `margin`
  identical to the same trial without cost. _Verify:_
  `tests/unit/test_engine_cost.py` (AC-MCV-005).
- **SC-mcv-4 — An attempt that never settled still leaves a row.** A run that is
  interrupted, killed, or whose agent dies before a trial settles writes one
  `attempt` event carrying `exit_code`, `cost` and the phase it died in; the
  summary reports `attempts` beside `trials` and prints `unsettled: N` rather
  than implying the total is complete. _Verify:_
  `tests/unit/test_engine_attempts.py` (AC-MCV-010, AC-MCV-011).
- **SC-mcv-5 — The attempt ledger is replay-safe.** `status` and `report` accept
  an `attempt` event without a metric value; a run with attempts and no trials
  renders a report that says so in one line and exits 0. _Verify:_
  `tests/unit/test_engine_attempts.py` (AC-MCV-012, AC-MCV-013).
- **SC-mcv-6 — A test's seconds are a number, not a feeling.**
  `scripts/ci_metrics.py` reads a JUnit XML file and prints, per suite: cases,
  failures, errors, skipped and total seconds, then one total line; it exits 0
  (it measures, it does not gate) and exits 2 on a missing or unparseable file.
  _Verify:_ `tests/unit/test_ci_metrics.py` (AC-MCV-020..024).
- **SC-mcv-7 — The script is usable from the runner it measures.** `bash
  scripts/local-ci.sh` writes each job's log where the script can read it, and
  `scripts/ci_metrics.py --junit /tmp/integration.xml` works against the file the
  `integration` CI job already writes. _Verify:_ `tests/unit/test_ci_metrics.py`
  (AC-MCV-024).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-mcv-1 | AC-MCV-001, AC-MCV-002 | `tests/unit/test_engine_cost.py` | unit |
| SC-mcv-2 | AC-MCV-003, AC-MCV-004 | `tests/unit/test_engine_cost.py` | unit |
| SC-mcv-2 | AC-MCV-201 | `tests/integration/test_measurement_report.py` | integration |
| SC-mcv-3 | AC-MCV-005 | `tests/unit/test_engine_cost.py` | unit |
| SC-mcv-4 | AC-MCV-010, AC-MCV-011 | `tests/unit/test_engine_attempts.py` | unit |
| SC-mcv-5 | AC-MCV-012, AC-MCV-013 | `tests/unit/test_engine_attempts.py` | unit |
| SC-mcv-6 | AC-MCV-020..024 | `tests/unit/test_ci_metrics.py` | unit |
| SC-mcv-7 | AC-MCV-024 | `tests/unit/test_ci_metrics.py` | unit |

## CI/CD Gate

- All unit ACs are hermetic; the integration AC replays a scripted loop over a
  throwaway repo. Both run in the existing `unit` and `integration` jobs.
- `scripts/ci_metrics.py` is stdlib only (`xml.etree.ElementTree`), takes a path,
  writes nothing, and is not wired into CI yet: it measures the runner, it does
  not gate it. Wiring it into a job would make a slow suite fail, which is a
  separate decision with its own PRD.
- `scripts/audit_pyramid.py` applies to the new script; `audit-chars.py` and
  `audit-size.py` apply to the new tests.
- No new tracked root; no new dependency.

## Assumptions

- [ASSUMPTION] **Usage is present in some transcripts and absent in others, and
  absence is the honest state.** The adapters already vary: a harness that
  prints a JSONL `usage` object yields tokens; one that prints prose does not.
  The rule "absent, never zero" is what keeps a partial total from reading as a
  complete one — the veteran's exact defect.
- [ASSUMPTION] **`attempt` is a new event kind, not a new verdict.** Adding a
  verdict would change every consumer that switches on verdict; an event kind is
  additive, and readers that do not know it skip it, which is the correct
  behaviour for a measurement record.
- [ASSUMPTION] **Per-suite seconds from JUnit are enough.** A finer picture
  (per-test timing) exists in the XML but is not needed to answer "which tier
  costs the wall clock"; printing it would triple the file with no decision
  attached.
