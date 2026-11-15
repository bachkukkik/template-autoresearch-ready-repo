---
title: Relocation, Not Play
created: 2026-11-15
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: medium
---

# Relocation, Not Play

The largest number in a frontier run's record was a **booking error**, twice. A speedup whose
cost merely moved elsewhere — a smaller test tier, a denominator that shrank with a deleted
file, an upstream commit — is not a win. It has to be named before it is counted.

> **Evidence.** `[S]` marks a figure **self-reported by the downstream repo** (PR body or a
> committed season record, quoted with its number).

## The three measured relocations

| Leg | Recorded move | What actually happened |
|---|---|---|
| `spec_gap` | 140 → 133 → **30** uncovered ids | three different commits: `origin/uat` (b95ff0b), the round's base (ca6b551), the trunk worktree the seats played in. One commit deleted 18 test files while their PRDs stayed — the denominator moved with no line of test code changing `[S]` |
| `faster` | **82.624 → 61.973 s**, then 61.973 → 38.861 s | `tests/docker-free.txt` held 55 bats entries at the base and 36 at `origin/uat`. The tier got shorter; the build did not get faster. Season 18's record classifies the move `displaced` (82.624 → 61.973) and its doc calls it "none of it is play"; season 19's record still reads `held` (61.973 → 38.861) while its doc calls the same class "a reading only, and not play" — `held` mislabels a relocation `[S]` |
| `cheaper` | 0 bytes over ten scheduled attempts | 1,313,437 bytes before and after — ten seat-level attempts (nine of season 22's fourteen seat-rounds plus round 62) over eight rounds that carry a reading — while captains quoted the intel line back as their reason `[S]` |

## The rules

1. **A run record is a comparison of two readings taken at two named commits**, or it is an
   anecdote. Record `season_start_commit`, `close_commit`, and a per-leg `{commit, value}`
   map. A leg never read gets `{commit}` and **no value** — absent stays absent, and a
   pre-field state closes with `null` rather than a fabricated zero.
2. **Classify by cause before calling anything a win**: *play* (the work moved the metric),
   *improved*, *held* (recalibrated instrument), *displaced* (the cost moved elsewhere),
   *reading* (re-read without work), *regressed*. A verdict is a function of the record, not
   of a reviewer's memory.
3. **Never compare a metric across a change to the instrument that measures it.** Its size
   and hash belong in the record beside the score, because a shorter tier *is* a faster tier
   and nothing in the score says why. This is the sibling of the noise floor on
   [[better-cheaper-faster-metrics]]: one protects against jitter, the other against
   redefinition.
4. **Pin the denominator at the base commit**, so deleting the objective is worth exactly
   zero, and record *declared / credited / uncovered* together — one number hides which half
   moved (`1027 declared / 140 uncovered / 887 credited` in season 19's close record,
   `1027 / 113 / 914` in season 21's — same declared total, a different split `[S]`).
5. **Keep the artefact of a loss.** The unbanked round-60 tree stayed at `evidence/round-60/`
   with its sha256, explicitly *not* a keep: it proves the leg was solvable without
   pretending the round won. An over-budget round is a loss, never an extension — promoting
   it by hand converts a loss into a win.

## Why it generalises

Every one of these is a *measurement-boundary* mistake, not a domain mistake, so it recurs in
any loop whose target is a codebase: dependency upgrades shrink a build, a migration deletes
the file a size metric watched, a refactor moves a test from the fast tier to the slow one.
The check is cheap — two commits and one instrument hash in the record — and it is the
difference between a season of evidence and a season of anecdotes. Season records belong on
[[run-record-contract]]; the objective that decides which legs exist is
[[objective-as-record]].

^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

## Related

- [[run-record-contract]] — the artefact that carries commits, instrument hash and verdicts.
- [[objective-as-record]] — the metric contract (unit, command, noise floor) a relocation test needs.
- [[better-cheaper-faster-metrics]] — the T0–T3 tiers and the honesty gap this page extends.
- [[deterministic-keep-gate]] — a relocation is a keep the gate should not have made.
- [[val-bpb-metric]] — the canonical case of a metric whose instrument matters.
