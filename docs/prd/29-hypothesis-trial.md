# PRD 29 — Hypothesis-Driven Trial: Say What You Expect Before You Look

> Intent: a trial may state a **falsifiable claim** before it runs, and the loop
> records whether the result confirmed it, refuted it, or could not be read at
> all. Everything here is **opt-in**: with the flag off, every prompt, ledger row
> and verdict is byte-for-byte what it is today.
> **Domain:** `hyp`. **Canonical tests:**
> `tests/unit/test_hypothesis_claim.py` (`AC-HYP-001..009`),
> `tests/unit/test_engine_decide.py` (`AC-HYP-010..013`, the margin quantile),
> `tests/integration/test_hypothesis_loop.py` (`AC-HYP-201`).
> **Stage 6:** `docs/29-hypothesis-trial.md` (pending).
> **Grounding:**
> [claim-reader-alignment](../../kb/concepts/claim-reader-alignment.md),
> [veteran-decision-register](../../kb/concepts/veteran-decision-register.md)
> (VD-03, VD-04, VD-05),
> [raw capture](../../kb/raw/articles/2026-11-26-veteran-decisions.md).
> **Builds on:** PRD 17 (engine), PRD 20 (eval layer). Changes no default.

## Context

The keep gate is already strict: a change is kept only when its measured
movement exceeds `max(noise_floor, Z x SE)`. But the gate grades an **outcome**,
never a **prediction**, so the ledger cannot distinguish three very different
trials: one that tested an idea and was right, one that tested an idea and was
wrong, and one that changed something for no stated reason and happened to move
the number.

A mature instance ran two consecutive seasons trying to fix this and paid twice
for the same defect. Both agents *did* print a claim; both seasons recorded
`hypothesis: null`, because the reader scanned raw stdout lines while the
harness emitted JSONL with the text escaped inside a part object. A second
season then lost one seat to a typographic minus sign: the agent wrote
`PREDICT: -1` with U+2212, the parser called `float()` and refused it. Two
seasons of evidence, zero gradeable claims — and the fault was in the reader,
never in the agent.

The same instance also fixed the margin's small-sample defect. This repository's
`decide.py` states it already:

> ``Z = 1.96`` is the *asymptotic* 95% normal quantile and the repeats are
> ``12.7``, so this margin is optimistic by roughly an order of magnitude at the
> smallest honest sample. A future PRD may switch to ``t``-based margins.

This is that PRD, and it makes the switch opt-in so existing runs are untouched.

## Scope

In: the prompt contract, one claim reader that matches the harness it reads,
the ledger field, refutation memory, the margin quantile.
Out: any change to the keep gate's default arithmetic; any model call; any
claim *scoring* of an agent — a missing claim is reported as missing, never as
noncompliance.

## Success Criteria

- **SC-hyp-1 — Off is byte-identical.** Without `--hypotheses`, the rendered
  prompt equals today's prompt byte for byte, no event carries a `hypothesis`
  key, and `report.md`/`results.tsv` are unchanged. _Verify:_
  `tests/unit/test_hypothesis_claim.py` (AC-HYP-001),
  `tests/unit/test_engine_prompt.py`.
- **SC-hyp-2 — On, the prompt asks for one claim on the mandatory line.** With
  `--hypotheses` the prompt's final instruction is one line carrying four named
  fields — `CHANGE:`, `HYPOTHESIS:`, `PREDICT:`, `FALSIFIED IF:` — and the word
  `HYPOTHESIS:` appears exactly once in the rendered prompt. _Verify:_
  `tests/unit/test_hypothesis_claim.py` (AC-HYP-002),
  `tests/unit/test_engine_prompt.py`.
- **SC-hyp-3 — The reader matches the harness, not the ideal.** `parse_claim`
  reads a claim from a plain text line **and** from a harness JSONL transcript by
  decoding each line and taking assistant text parts only; a claim that appears
  only inside a tool result or a tool call argument is **not** a claim. _Verify:_
  `tests/unit/test_hypothesis_claim.py` (AC-HYP-003, AC-HYP-004).
- **SC-hyp-4 — The reader accepts the glyph the agent actually typed.** A
  `PREDICT:` value written with U+2212 MINUS SIGN, with a leading `+`, with
  surrounding whitespace, or as an escaped `\u2212` inside JSONL parses to the
  same float as ASCII `-`. A non-numeric `PREDICT:` yields `predict: null`, the
  claim is still recorded, and nothing is scored. _Verify:_
  `tests/unit/test_hypothesis_claim.py` (AC-HYP-005).
- **SC-hyp-5 — The ledger records the claim beside the result.** An opted-in
  trial's event carries `hypothesis` = `{text, predict, falsified_if, sign_match,
  calibration}`; `sign_match` is `true` when the realised delta's sign equals
  `sign(predict)`, `false` when it opposes, and `null` when either side is
  unmeasured. An unclaimed trial carries `hypothesis: null` and is reported as
  such — never as compliant. _Verify:_ `tests/unit/test_hypothesis_claim.py`
  (AC-HYP-006, AC-HYP-007), `tests/integration/test_hypothesis_loop.py`
  (AC-HYP-201).
- **SC-hyp-6 — Refutations are remembered with a reason, and a crash is not a
  refutation.** A refuted claim appends `{text, reason, count}` to the run's
  refuted memory; an identical text increments `count` rather than duplicating;
  the memory is bounded (last ten distinct texts); `agent_error`, `crash` and
  `guard_failed` events never append and never increment. _Verify:_
  `tests/unit/test_hypothesis_claim.py` (AC-HYP-008, AC-HYP-009).
- **SC-hyp-7 — `--margin-quantile t` uses the t quantile at small n, and `z`
  stays the default.** `t` uses the two-sided 95% Student-t value for `df = n-1`
  where `n` is the honest repeat count, looking up `df` 1..30 and falling back to
  `1.96` above 30; `z` reproduces today's numbers byte-identically. _Verify:_
  `tests/unit/test_engine_decide.py` (AC-HYP-010, AC-HYP-011).
- **SC-hyp-8 — The quantile table is the published one.** `t_quantile(df)` returns
  12.706 at df 1, 4.303 at 2, 2.571 at 5, 2.228 at 10 and 2.042 at 30, and the
  module tolerates `df <= 0` by falling back to `Z` rather than raising. _Verify:_
  `tests/unit/test_engine_decide.py` (AC-HYP-012, AC-HYP-013).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-hyp-1 | AC-HYP-001 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-1 | — (existing) | `tests/unit/test_engine_prompt.py` | unit |
| SC-hyp-2 | AC-HYP-002 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-2 | — (existing) | `tests/unit/test_engine_prompt.py` | unit |
| SC-hyp-3 | AC-HYP-003, AC-HYP-004 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-4 | AC-HYP-005 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-5 | AC-HYP-006, AC-HYP-007 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-5 | AC-HYP-201 | `tests/integration/test_hypothesis_loop.py` | integration |
| SC-hyp-6 | AC-HYP-008, AC-HYP-009 | `tests/unit/test_hypothesis_claim.py` | unit |
| SC-hyp-7 | AC-HYP-010, AC-HYP-011 | `tests/unit/test_engine_decide.py` | unit |
| SC-hyp-8 | AC-HYP-012, AC-HYP-013 | `tests/unit/test_engine_decide.py` | unit |

## CI/CD Gate

- Unit ACs run in the existing `unit` job; the one integration AC replays a
  scripted loop over a throwaway git repo with no model and no network — it runs
  in the existing `integration` job. No new job.
- `scripts/audit_pyramid.py` applies to the new module unchanged; it is stdlib
  only, has no subprocess and no `shell=True`.
- The new CLI flag is declared once in the engine CLI (`run`) and is not a
  catalog command: it configures a command that already exists, so PRD 23's rule
  needs no new registry entry. If the reviewer disagrees, the flag is added to
  the registry instead — the rule is not negotiated, only the surface.

## Assumptions

- [ASSUMPTION] **A claim is graded on sign and presence, not on accuracy of
  magnitude.** The veteran's `calibration` metric is approximate; requiring a
  numeric error band would make most honest claims fail. The readable, testable
  claim is: did the sign match, and was anything predicted at all.
- [ASSUMPTION] **The JSONL shape is discovered, not assumed.** The reader
  accepts the two shapes this repo's adapters actually see — a bare line and a
  JSON object with a `text` field or a `part.text` field — and ignores every
  other line. A harness whose shape is neither is a reader defect to be fixed
  against a recorded transcript, exactly as the veteran fixed it.
- [ASSUMPTION] **`t` above df 30 is not materially different from `z`** (2.042 vs
  1.960 at 30, closing to 1.96). Falling back at 30 keeps the table honest and
  the code small; the alternative is an incomplete-beta implementation with no
  test that would catch an error in it.
