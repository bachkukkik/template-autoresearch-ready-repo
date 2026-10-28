---
title: Verify/Guard Contract
created: 2026-10-28
updated: 2026-10-28
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: high
---

# Verify/Guard Contract

The interface between a loop and the thing it is trying to improve. Eight of the fifteen
studied engines converge on the same shape: **`verify` prints exactly one number; `guard`
prints nothing and returns an exit code; direction and target are pinned once at run start;
anything unparseable is an error, never a zero.** ^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

This is the measurement half of [[deterministic-keep-gate]] (which fixes the *decision*
contract: 0 keep · 1 discard · 2 invalid) and the operational half of the frozen evaluator
in [[autoresearch-contract]].

## The verify surface

| Form | Where | Why it is ranked here |
|------|-------|-----------------------|
| Tagged block — `=== FINAL ===` then `correctness:`, `speedup_vs_pytorch:`, … | autokernel `bench.py` | parse by tag, so a missing line is a loud failure; readable in a log by a human |
| JSON on the last line only — finite decimal, or `--metric-key` into a JSON object, all arithmetic `Decimal` | leo-lilinxiao `parse_metric_output` | no float edge cases; any language can satisfy it |
| JSON object with detail — `{score, max, pct, details[], feedback[]}` | goal-md `scripts/score.sh --json` | `details` is actionable for the agent, `feedback` readable for the human |
| Per-example score vector + Pareto frontier | GEPA | a candidate that wins the average and loses a subset is not automatically preferred |
| `METRIC name=value` lines | pi-autoresearch | several named metrics per run; only the configured primary drives the keep |
| Free-form log read by a model — `{is_bug, metric, lower_is_better}` | aideml | weakest: the candidate computes and prints the number being optimised |

Rules that recur across all of them: read **only** the declared channel (last line, tagged
block, named key) so a chatty build cannot be mistaken for a metric; a crash, timeout, empty
output or non-UTF-8 output is a **failed attempt**, not a score; and the raw bytes are kept
for diagnosis (leo-lilinxiao base64-preserves non-UTF-8 output).

## The guard

Four hard rules, each with a repo behind it:

1. **Must pass at baseline or `init` fails.** Otherwise the first candidate inherits a broken
   gate and every later comparison is meaningless (leo-lilinxiao; uditgoenka runs a guard
   baseline in preconditions).
2. **A guard failure discards an improvement.** `keep = improved AND guard_passed` — evo's
   two-term expression, leo's `finish`, pi's `checks_failed`.
3. **The failure is a first-class verdict, not a zero score.** pi records `checks_failed`;
   research-loop has `invalid` and `crash` as separate states; evo has `PRE_GATE_FAILED`.
   A report must be able to say "broke the build" apart from "no gain".
4. **Cheapest first, short-circuit.** autokernel's five stages (smoke → shape sweep →
   stability → determinism → edge cases) abort on the first failure before benchmark time is
   spent; evo's `pre` phase runs static gates — including a leak grep — before the benchmark.

## Direction and target are pinned

`lower|higher` is written into the run manifest at init (leo-lilinxiao's `run.json`,
uditgoenka's `# metric_direction:` header, research-loop's hash-approved contract). aideml
resolves direction once per run and *logs* a later conflict rather than silently re-ranking.
The failure this prevents is maximise/minimise drift, which inverts every subsequent
decision without any error surfacing.

## The guard you document must be the guard you run

The Liquid case is the corpus's cheapest catastrophic defect: `autoresearch.md` claims the
liquid-spec conformance suite runs as part of the loop while `autoresearch.sh` only invokes
`bench.sh`, so the loop was less protected than its own write-up said. The mechanical fix is
to parse the guard commands named in the program document and assert they appear in the
runner script at `init` and `status` — or to generate the document from the script. A
program document is prose; the script is the only thing that executes.

## Where this leaves a generic engine

`init` writes `{verify_cmd, guard_cmd, direction, target, noise_tolerance}` into the run
manifest and freezes it; `run` treats verify output as the declared channel or errors;
`guard` runs only after an improvement and its failure reverts; `status` reports the two
separately; `report` refuses a claim that does not cite both. See
[[script-owned-keep-revert]] for who executes this and [[autoresearch-engines-real-world]]
for the comparison that produced these rules.

## Related

- [[deterministic-keep-gate]] — the exit-code decision contract this measurement feeds.
- [[autoresearch-contract]] — the frozen-evaluator rule.
- [[script-owned-keep-revert]] — the engine, not the agent, runs verify and guard.
- [[reward-hacking-countermeasures]] — why a guard independent of the metric is not optional.
- [[autoresearch-engines-real-world]] — the 15-system evidence.
