---
title: Better/Cheaper/Faster Metrics (T0–T3 tiers)
created: 2026-09-26
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md, raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: high
---

# Better/Cheaper/Faster Metrics

How the slogan "max test coverage, min wall time, min LLM cost" becomes a
decidable objective (a private commerce-pipeline instance's Wave 1).

## Field tiers

| Tier | Meaning | Gate? |
|------|---------|-------|
| T0 | exact, reproducible (image bytes, test counts) | may gate |
| T1 | exact but drifting — value real, delta unattributable without a recorded pin (`audit_db_date`, `ui_repo_commit`) | only beside a pin; exit 2 if pin absent or moved |
| T2 | statistical (median-of-N; measured 11–13% wall-second spread on identical input) | never (`gate: false` enforced by policy lint) |
| T3 | judgment → counted (only the violation count) | count only |

`compare --prev/--next` exit contract: 0 keep / 1 discard / 2 invalid snapshot;
an unmeasured gate forces 2. Policy lives in YAML the evaluator reads — never
in code, never in cards ([[methodology-registration]]).

A statistical leg does **not** gate by default (T2: `gate: false`). When one must gate, the
keep gate's `max(floor, z·SE)` margin is exactly what makes the gate defensible — a T2 delta
inside its own band is jitter, and without the margin it would bank as a keep. The margin is
not an exception to the T2 rule; it is the precondition for making one ([[deterministic-keep-gate]]).

## Evaluator legitimacy (deterministic, LLM-free)

The only admissible judge is the deterministic script: determinism makes cycle
deltas content-attributable; an LLM judge reintroduces exactly the variance the
loop engineered out. Grounds [[evaluator-legitimacy]] operationally.

## The honesty gap (measured)

The instance optimizes 2 of its 3 headline dimensions: per-cycle wall time and
LLM cost were never recorded (placeholder cost 1.0; 0/2757 sessions with cost
attribution), while headline series saturated and gap_debt rose. Template rule:
instrument duration+cost+size fields in the FIRST snapshot; never claim a
favourable direction unless the series is moving. Same discipline as
[[fixed-time-budget]] and [[val-bpb-metric]]: the metric must be honest before
it is optimized.

## Fail-closed: a leg is honest or it is dark (2026-11-15)

> `[S]` marks a figure self-reported by the downstream repo (PR body or committed record).

The honesty gap has a mechanical form. Every leg answers in one of two states, and the
harness may never invent a third:

| State | Answer | Why |
|---|---|---|
| measured | `value` + `values` + `spread` + `honest: true` | the number can be argued about |
| **dark** | `null`, and a named reason (`could_not_run`, `no_reading`) | absence is the finding |

- **`could_not_run → null` + exit 1.** A probe or leg that could not run is never a zero and
  never a pass; the caller must handle the null.
- **All probes missed → exit 0 with rate 0.0.** A cheat-probe sweep that detected nothing is
  a *result*, not an error — but the gate reads the **rate**, never the exit code, or "all
  missed" and "could not run" collapse into the same silence.
- **An unconfigured leg produces nothing, not a zero.** A leg nobody configured must read as
  dark; the downstream league's `faster` was "half-lit" — `statistics.median([first, second])`
  over exactly two bats runs, no dispersion check, and nothing at all when unconfigured, until
  #8/#13 replaced it with `FASTER_REPEATS ≥ 3` plus a recorded spread `[S]`.

Two calibration duties come with it:

- **Measure the noise floor** — an A/A re-measure of the unchanged tree — and record it with
  its values *before* pricing the metric. A deterministic metric honestly reports 0.0 (a
  byte-count leg measured 0.0 spread over 5 reads); a move below the floor is not a move.
- **Canary the evaluator.** Re-measure unchanged trunk against a recorded baseline, treat a
  delta beyond `max(1.96 · baseline spread, tolerance)` as **drift**, append one line to an
  append-only ledger, exit non-zero. Refuse a baseline or ledger path the target tracks, the
  profile scores, or that lives under `.git` — a canary must not move the metric it watches.
  Without it a tool upgrade (shellcheck, bats) silently moves every score in the record.

The keep decision that consumes these numbers — margin, third verdict, provenance — is on
[[deterministic-keep-gate]]; the metric contract that requires a `noise_floor` per leg is
[[objective-as-record]]; classifying a move that came from the instrument rather than the
work is [[relocation-not-play]].

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
^[raw/articles/2026-11-15-downstream-frontier-distillation.md]
