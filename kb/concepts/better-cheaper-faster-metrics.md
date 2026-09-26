---
title: Better/Cheaper/Faster Metrics (T0–T3 tiers)
created: 2026-09-26
updated: 2026-09-26
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-09-26-autoresearch-methodology-registration.md]
confidence: high
---

# Better/Cheaper/Faster Metrics

How the slogan "max test coverage, min wall time, min LLM cost" becomes a
decidable objective (slash-commerce Wave 1).

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

^[raw/articles/2026-09-26-autoresearch-methodology-registration.md]
