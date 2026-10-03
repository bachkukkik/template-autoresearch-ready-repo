# 15 — STE-style audit

> Status: Accepted · Confidence: high · Gate: `unit` job (pytest `tests/unit`)

## Context

Karpathy's output-medium post recommends writing "80% of the way to ASD-STE100" — the
aerospace controlled-language spec, softened. This repo adopted that rule as rung 2 of
the output-medium doctrine (`AGENTS.md` §7). But the check was a one-off analysis in a
session, not a repo artifact. A rule no script can run is a rule the next agent must
rediscover. This topic makes the rule structural.

Origin: `bachkukkik/template-agentic-ready-repo` (PRD 05, commit #14).

`[ASSUMPTION]` Scope is the rule subset that is machine-checkable without the ASD-STE100
dictionary (never vendored — it is ASD's copyright): sentence-length limits and passive
voice. That is the same "80%" framing the source post uses.

## Deliverable

`scripts/audit-ste.py` — stdlib-only CLI:

- Input: one or more markdown files (default: `docs/*.md`, `README.md`).
- Strips code fences, tables, headings, and list markers; splits prose into sentences.
- Measures per doc: total sentences, sentences over the descriptive limit (25 words),
  longest sentence, passive-voice constructions (`be` + past participle).
- `--max-words N` (default 25), `--threshold P` (default 80): exit 0 when the share of
  sentences within the limit is ≥ P%, else exit 1 and print every offender.
- `--verbose`: print the per-file table even on success.

`tests/unit/test_ste_audit.py` — hermetic unit tier (`AC-STE-0NN`):

| ID | Asserts |
|----|---------|
| `AC-STE-001` | This repo's real docs pass at the 80% threshold (`python3 scripts/audit-ste.py` exit 0). |
| `AC-STE-002` | The auditor discriminates: a synthetic doc with a 60-word sentence fails at threshold 80 but passes at threshold 50; offenders are named in output. |
| `AC-STE-003` | Contract: `--help` exits 0; a missing input file exits 1 with a clear message; code fences are exempt (a fenced block with long lines does not count). |

## Success criteria

| ID | Criterion | Verify |
|----|-----------|--------|
| SC-ste-1 | `scripts/audit-ste.py` exists, runs stdlib-only, and the repo's own docs pass at the default 80% threshold. | `tests/unit/test_ste_audit.py::test_ste_audit_real_docs_pass_threshold` (AC-STE-001) |
| SC-ste-2 | The auditor discriminates: a synthetic over-limit doc fails at 80 but passes at 50, offenders named, fenced code exempt. | `tests/unit/test_ste_audit.py::test_ste_audit_discriminates_and_exempts_fences` (AC-STE-002) |
| SC-ste-3 | CLI contract: `--help` exits 0; a missing input exits 1 and names the path. | `tests/unit/test_ste_audit.py::test_ste_audit_cli_contract` (AC-STE-003) |

## Test Mapping

| SC | Test | Tier |
|----|------|------|
| Docs stay ≥80% within limits | `AC-STE-001` | unit |
| Auditor detects violations | `AC-STE-002` | unit |
| CLI contract | `AC-STE-003` | unit |

## CI/CD gate

The `unit` job runs the auditor against the real docs on every push and PR. A doc edit
that drops the repo below 80% fails CI before merge — the doctrine's rung 2 becomes
structural, like the §7 token tripwire.

## Source attribution

Rule source: `kb/raw/articles/karpathy-output-medium-escalation.md` (the "80% of the way
to ASD-STE100" phrasing) → `kb/concepts/output-medium-escalation.md` (rung 2). Licensing
constraint (no dictionary vendoring): `docs/13-output-medium-doctrine.md`.

## Assumptions

- `[ASSUMPTION]` The machine-checkable subset is sentence length + passive voice; the
  full ASD-STE100 rule set is not enforceable without the copyrighted dictionary.
- `[ASSUMPTION]` A 25-word descriptive cap and an 80% within-limit threshold are the
  right defaults; both are CLI-overridable (`--max-words`, `--threshold`).

## Confidence

**High** — the rule is grounded in the ingested raw source, the checker is a hermetic
stdlib-only script, and the real docs pass the gate today (measured, not asserted).
