---
title: Problem Selection
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, research-method, example]
sources: [raw/transcripts/bMoNOb0iXpA.txt, raw/transcripts/uBWuKh1nZ2Y.txt, raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Problem Selection

Which problems the autoresearch loop (hypothesize → mutate → measure →
keep/discard within a time budget) fits — and which it does not.

## Required conditions (all three)

1. A **clear scalar metric** with a known direction ("if you can score it, you can auto research it").
2. An **automated evaluation** with no human in the loop.
3. An **editable artifact** the agent can mutate.

## Well-suited

- Cheap, fast evaluation that fits the iteration budget.
- Scalar cost; local-move improvement structure.
- Demonstrated: a Kaggle Traveling-Santa TSP run improved with warm starts
  from best-so-far, steering, and pre-seeding the agent with algorithm names;
  relaxing the budget 5 → 10 minutes gave another jump.
- Non-ML transplants: website load time (50ms → 25ms demo; 1100ms → 67ms
  reported), cold-email reply rate, Claude-skill eval pass rate.

## Step back when

- Heavy compute or expensive evaluation per iteration.
- Non-greedy exploration required; the LM lacks domain knowledge.
- **Subjective success**: brand design, UX, pricing (unless huge traffic +
  fast A/B) — the agent "will optimize in a random direction".
- Fuzzy or slow metrics (e.g. "warmth") that cannot drive an unattended loop.

## Operational lessons

- Warm starts beat cold starts; steering beats pure black box.
- Do pre-research before the loop (feed the agent plausible algorithms).
- Save artifacts + add tests; parallelizing runs without tests can lose the
  best solution.

Related: [[autoresearch-contract]] · [[fixed-time-budget]] · [[skill-self-improvement]]

^[raw/transcripts/bMoNOb0iXpA.txt] ^[raw/transcripts/uBWuKh1nZ2Y.txt]