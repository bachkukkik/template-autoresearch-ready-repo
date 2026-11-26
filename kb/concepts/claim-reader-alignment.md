---
title: Claim Reader Alignment (read the harness, not its stdout lines)
created: 2026-11-26
updated: 2026-11-26
type: concept
tags: [autoresearch, agentic, research-method]
sources: [raw/articles/2026-11-26-veteran-decisions.md]
confidence: medium
---

# Claim Reader Alignment

An engine that asks an agent for a structured claim — a hypothesis, a
predicted delta, a falsifier — has a second, quieter contract: the reader
must parse **the channel the harness actually emits**. When it parses a
different one, the loop records `null` for a claim the agent made, and every
downstream reading (calibration, compliance, sign match) is computed over an
empty denominator. The failure is silent, looks like agent non-compliance,
and survives reviews because the trial row is well-formed.

The veteran's own phrasing of the outcome: two seasons were graded against a
reader that could not see the message it was asking for.
^[raw/articles/2026-11-26-veteran-decisions.md]

## The measured failure

Two consecutive seasons, same team, opposite verdicts:

| Season | What the agents did | What the reader recorded |
|---|---|---|
| 35 | both logs carry exactly one `CHANGE: … \| HYPOTHESIS: …` line | `hypothesis: null` for both trials; commit subject falls back to `iteration 1` |
| 36 | same line, seat A with `PREDICT: −1` (U+2212) | seat B parsed (`predict: -5.0`, realised −5); seat A still `predict: null` |

The first is a **channel** defect: the adapter scanned raw stdout *lines* for
a line beginning `CHANGE:`, while the harness emits JSONL — one object per
line, the message's newlines escaped inside `part.text` — so no line in that
stream can begin with `CHANGE:`. The second is a **glyph** defect: the
number arrived, `float()` refused the typographic minus, and a claim became a
silence. Both are the reader's, not the seat's.

## The mechanism that fixed it

- **Decode the event stream, then scan.** One helper
  (`_transcript_lines()`) decodes the harness's JSONL and yields the
  assistant text parts; the existing line scans run over the decoded text
  instead of the raw stream.
- **Assistant text only.** A claim echoed back by a tool result is not a
  claim; restricting the scan to assistant text parts keeps a `grep`ed
  example from being counted as the seat's own prediction.
- **Normalise the typography, keep the grammar.** A leading U+2212 / U+2013
  / U+2014 and NBSP padding are accepted as a sign; the rest of the grammar
  (a mechanism, a finite number, a falsifier) is unchanged and a negative
  control proves the vectors bite.
- **Regression vectors from the real logs.** The two failing seasons' agent
  logs ship as fixtures: each must parse to a mechanism, a finite `PREDICT`
  and a falsifier. A parser change that re-breaks the channel fails the
  suite rather than a season.
- **Do not retro-fit the archive.** The record keeps what was recorded at
  trial time; the repair shows up as a new reading, not as an edit.

## Why this generalises past the league

Every harness this repo drives emits its own shape — one JSONL event stream,
one text-mode stdout, one `--output-format` variant — and the template's
contract already says the *invocation* is per-harness. This page is the
other half: the **reading** is per-harness too. See
[[headless-harness-invocation]] for the argv side and
[[veteran-decision-register]] rows 03–04 for the rule in context.

The test that keeps it honest is a pair, not a case: one fixture that must
parse (the real log) and one that must refuse (a claim echoed by a tool
result, a bare glyph, a mechanism with no falsifier). A reader with only the
positive fixture passes on a stream it does not understand.

## What it does not cover

- **A top-level `text` field.** The veteran's reader accepts the assistant
  part and named string fields; a harness that emits its final message
  somewhere else needs its own vector.
- **A claim is not a proof.** Parsing a prediction says the seat pre-registered
  something; whether the prediction *tests* the change is the metric's
  problem, not the reader's — that is [[deterministic-keep-gate]]'s job, and
  the veteran's next defect after this one was paying for a pointer instead
  of a coverage change.
- **Silence is still possible.** A harness that truncates its own stream
  leaves no claim to read; the honest value there is a reason code
  (`missing mechanism`, `non-finite predict`), not a zero — the same
  fail-closed rule the register states for facts.

## Related

- [[veteran-decision-register]] — the twenty rules this page expands (03–04).
- [[headless-harness-invocation]] — the per-harness argv contract this
  mirrors.
- [[deterministic-keep-gate]] — what happens to a claim once it is read.
- [[run-record-contract]] — why the trial row must record *why* a claim was
  ungraded.
