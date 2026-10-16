---
title: Autoresearch OSS Landscape (19 implementations compared)
created: 2026-10-16
updated: 2026-10-16
type: comparison
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-16-autoresearch-oss-landscape.md]
confidence: medium
---

# Autoresearch OSS Landscape

A side-by-side read of the 19 MIT/Apache-2.0 implementations studied on
2026-10-16, compared on the dimensions this template's contract cares about. The
full per-repo evidence table (SPDX, head sha, stars, mechanism + file path) lives
in the raw source. ^[raw/articles/2026-10-16-autoresearch-oss-landscape.md]

## Dimensions

| Dimension | Best-in-class exemplar | Local exemplar | Verdict |
|-----------|------------------------|----------------|---------|
| Deterministic keep gate | leo-lilinxiao (state machine), evo (gate inheritance) | the contract writer's `compare` 0/1/2 | adopt the exit-code triple → [[deterministic-keep-gate]] |
| Budget enforced in code | n-autoresearch (import + hard kill), TheGreenCedar (cumulative), autokernel (SIGALRM) | `contract/prepare.py TIME_BUDGET` | strengthen: enforce, don't just declare |
| Noise floor | autokernel (1% rule), davebcn87 / Bilevel (MAD) | none | add a minimum-delta rule |
| Protected surface | autoguardrails (surface hash), cyzlmh (bundle hash), AutoResearchClaw (injected harness) | object-identity test only | consider a byte pin |
| Ledger validation | leo (strict event schema), uditgoenka (`validate-state`) | untracked `results.tsv` | optional hardening |
| Harness portability | Arbor (Markdown skills), CORAL (runtime registry) | `.agents/` + symlinks | this template leads → [[harness-portability]] |
| Held-out gate | evo (60/40 + leak pre-gate), Arbor (B_dev/B_test) | none | strong idea for correctness domains |

## Verdict

No single repo is a superset. The recurring, transferable core is exactly this
template's contract — three mutability classes, a fixed budget, a keep/discard
ledger — plus four hardenings the study surfaces: **enforce** the budget in code,
add a **noise floor**, **hash the frozen surface**, and gate on a **held-out**
split for correctness domains. The evaluator-integrity and harness-portability
clusters are the richest sources; the end-to-end research agents
(AutoResearchClaw, Arbor) are mostly scope creep. See [[evaluator-legitimacy]]
for why the integrity cluster exists at all.

## Related

- [[deterministic-keep-gate]] · [[harness-portability]] · [[autoresearch-contract]] ·
  [[evaluator-legitimacy]]
