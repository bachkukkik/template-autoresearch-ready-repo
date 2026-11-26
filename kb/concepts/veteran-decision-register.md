---
title: Veteran Decision Register (20 rules from 38 played seasons)
created: 2026-11-26
updated: 2026-11-26
type: concept
tags: [autoresearch, research-method, decision, agentic]
sources: [raw/articles/2026-11-26-veteran-decisions.md]
confidence: medium
---

# Veteran Decision Register

Twenty rules a mature downstream instance
(`vanilla-open-design-autoresearch`, 38 numbered seasons, 22 tracked close
records, 75 rounds) arrived at by playing them, not by designing them. Each
rule was earned by a named failure — a season that closed dry, a leg that
could not move, a reader that could not hear — and each is stated in the
instance's own tracked files. ^[raw/articles/2026-11-26-veteran-decisions.md]

The register's value is not the list. It is that every entry has the shape
**claim → the failure that paid for it → the file that states it**, so a
reader can check the rule against the evidence instead of adopting it on
authority. The full capture, with two verbatim fragments per row, its
evidence table and the adopter-fork table, is the raw source above; this
page is the one-line index into it.

> **Scope.** One lineage's evidence. Nothing here has been re-run on this
> template's own loop, which is why `confidence: medium` — the rules are
> verified as *stated* in the veteran, not as *necessary* anywhere.

## The register

| # | Rule | Earned by | Related |
|---|---|---|---|
| 01 | An unobserved trial yields **no reading**, never a zero. | a review pricing a dead seat's leg up 1.0 → 1.5 while the moving leg went down | [[deterministic-keep-gate]] |
| 02 | Refuse to start what the remaining wall cannot fund. | 14 seat-rounds granted 2–6 iterations that each ran one trial | [[loop-stop-conditions]] |
| 03 | A claim is readable only by a reader matching the harness's real output format. | two seasons graded on `hypothesis: null` while both agents printed the claim | [[claim-reader-alignment]] |
| 04 | Accept the harness's typography — U+2212, escaped newlines. | `PREDICT: −1` refused by `float()`; one seat counted uncompliant | [[claim-reader-alignment]] |
| 05 | Small-n margins use the t quantile; z is asymptotic (df 1 = 12.706). | the same pair `z keep` / `t inconclusive` | [[better-cheaper-faster-metrics]] |
| 06 | Size a brief to its own gate's margin, or it is inconclusive by construction. | one annotation asked against a 4.3-bullet margin | [[objective-as-record]] |
| 07 | A metric declares direction, unit, command, noise floor, exploit, probe. | a leg priced with no floor and no probe | [[verify-guard-contract]] |
| 08 | Retire a metric a census shows is unwinnable. | zero honestly winnable services, rejected as a leg three times | [[evaluator-legitimacy]] |
| 09 | A pointer is not proof: the verifier must cite the same AC id. | five payloads naming one test that asserts nothing about the criterion | [[verify-guard-contract]] |
| 10 | Price what moved, not what was attempted. | a close that priced the moving leg down and the unmoved leg up | [[fair-competition-invariants]] |
| 11 | Re-establish and re-measure the base before paying for a round. | a promote PR deleting the trunk it was measured on | [[run-record-contract]] |
| 12 | One writer per target: consolidate mutating jobs onto one router. | two hourly schedulers firing into one repo, blind to each other | [[unattended-loop-recipe]] |
| 13 | Schedules are intervals plus an in-code window, never an unparsed cron. | a job reading `active` with `next_run_at: null`, dead in fact | [[unattended-loop-recipe]] |
| 14 | A skipped job is a failure — local CI fails when the actor skips. | `act` exiting 0 having run nothing | [[quality-controls]] |
| 15 | Deterministic first, LLM last; the delivery ceiling lives in code. | a bot told its ceiling in prose can still merge to `main` | [[reward-hacking-countermeasures]] |
| 16 | Facts fail closed: a missing fact never satisfies a rule. | an unclassified CI reading that would have silenced a red gate | [[unattended-loop-recipe]] |
| 17 | Digest the facts so a repeat fire is recognised and stopped. | one unchanged fact set re-fired eight times in 24 h | [[unattended-loop-recipe]] |
| 18 | *Landed* gates payment (the re-run-after-revert clause is **unsupported**). | both seats paid +51.63 for a trunk that failed its guard | [[run-record-contract]] |
| 19 | Salvage a dead agent's tree, measure it, never read it as a refutation. | a seat's 30 → 0 win reverted unread because its agent timed out | [[script-owned-keep-revert]] |
| 20 | The record measures itself: fidelity, coverage, an attempt ledger. | a retried round overwriting its own token ledger | [[objective-as-record]] |

## The six that are contracts, not tactics

Half the register is hygiene; six rows are the ones a template cannot
inherit by example, because they define what a *reading* is. Rows 01, 03–04,
07, 09 and 20 together say: a number only exists if a declared metric, read
by a matched reader, over a priced movement, in a record that can be
audited. Everything else in the register is how that arithmetic survives
contact with a scheduler and a budget — [[loop-stop-conditions]] for the
wall, [[unattended-loop-recipe]] for the clock.

Row 03–04 is the one that generalises furthest beyond league play, and it has
its own page: [[claim-reader-alignment]].

## Where the register corrects its own brief

- **VD-18.** "The guard re-runs after a revert" is contradicted by the
  veteran's own season-22 document, which lists *no re-run* as a known limit
  of the fix. The rule as written there is: the guard runs **before** the
  banks, and a reverted seat settles unpaid. Adopt that, not the stronger
  claim.
- **Scale.** The capture's brief said 46 seasons; the tree records 38. The
  register cites the verified figure.

## Open questions

- Which rows survive a single-agent loop? Rows 01–11 are single-loop
  contracts (a reading, a margin, a brief, a base); rows 12–17 presuppose a
  scheduler; rows 18–19 presuppose two seats.
- Is row 06 a metric-design rule or a prompt rule? The veteran fixed it in
  the brief twice (size up, then name the gate) and never in the metric.
- Does row 20's family have a floor? Eleven self-measurements were added
  across two seasons; nothing removed one.

## Related

- [[claim-reader-alignment]] — rows 03–04, the harness transcript rule.
- [[deterministic-keep-gate]] — rows 01 and 10: what counts as a reading.
- [[loop-stop-conditions]] — rows 02 and 11: the wall and the base.
- [[fair-competition-invariants]] — rows 10 and 18: settlement arithmetic.
- [[verify-guard-contract]] — rows 07 and 09: the measurement contract.
- [[unattended-loop-recipe]] — rows 12–17: one writer, a window, a digest.
- [[run-record-contract]] — rows 11, 18 and 20: where the record lands.
- [[objective-as-record]] — rows 06 and 20: what may be priced.
