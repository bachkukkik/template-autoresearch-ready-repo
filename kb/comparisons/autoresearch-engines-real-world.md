---
title: Autoresearch Engines — Real-World Comparison (15 systems)
created: 2026-10-28
updated: 2026-10-28
type: comparison
tags: [autoresearch, research-method, example]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: medium
---

# Autoresearch Engines — Real-World Comparison

Fifteen systems studied at pinned commits on 2026-10-28, compared on the axis this
template actually cares about: **does the loop measurably improve real code, and what
mechanism made that possible?** The per-repo evidence table (SPDX, `head_sha`, mechanism
+ file path, numbers) and the full cross-cutting analysis live in the raw source; this
page is the comparison and the verdict. ^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

The filter is severe: three of the fifteen are not engines (a curated list, a
specification, a platform whose loop never iterates), three publish no measurable result,
and one publishes results whose confidence intervals cross zero.

## Dimensions

| Dimension | Best-in-class | Weakest in the set | Verdict for a generic engine |
|-----------|---------------|--------------------|------------------------------|
| Verify contract | autokernel (`=== FINAL ===` tagged block), leo-lilinxiao (Decimal + `--metric-key`) | aideml (candidate prints its own metric, an LLM reads the log) | tagged block or JSON object; unparseable = error → [[verify-guard-contract]] |
| Guard independent of metric | evo (`keep = score ∧ gate`), leo (`--guard` must pass at baseline) | karpathy (no guard beyond the pinned val shard) | two-term keep, guard vetoes an improvement |
| Keep/revert owner | leo-lilinxiao, evo, steer (script) | karpathy, CORAL, pi, autokernel, uditgoenka (agent) | the engine owns it → [[script-owned-keep-revert]] |
| Scope enforcement | leo-lilinxiao (allowlist + protected prefixes), research-loop (diff check) | pi (glob-free commit), CORAL ("no per-path allowlist") | allowlist without globs + protected prefixes |
| Ledger | leo-lilinxiao (`events.jsonl` + `derive_state` replay) | karpathy (`results.tsv`, no validation) | event-sourced, validated on read |
| Stop conditions | evo (required `--per-exp-timeout`), uditgoenka (plateau + `unknown`) | karpathy (NEVER STOP), FAROS (`maxIterations` never decremented) | composite, bounded by default → [[loop-stop-conditions]] |
| Dry run | research-loop (plan + hash-bound approval), uditgoenka (round 0) | leo-lilinxiao, GEPA, karpathy (none) | plan → hash → approve → gates |
| Noise | autokernel (trimmed median), research-loop (confirmation runs) | ten of fifteen (nothing) | noise floor + repeats; the evidence is negative and strong |
| Anti-Goodhart | GEPA (sealed split at the transport layer + `bwrap`) | FAROS, aideml (visible tests, LLM ranker) | hidden holdout at accept → [[reward-hacking-countermeasures]] |
| Harness portability | CORAL (4 adapters incl. `dsh`) | evo, GEPA, pi, uditgoenka (one harness, flags in the loop) | adapters, argv-only → [[headless-harness-invocation]] |

## What made the real wins

Only six of the fifteen have both a loop and a number, and every real win shares the same
five properties:

1. **A metric outside the loop's control.** Liquid's parse+render throughput measured by
   `bench.sh`; autokernel's `bench.py`; CIFAR accuracy on a fixed split. In the one case
   where the candidate could configure the evaluation path (tennis, 122 `LogitOffsetSpec`
   entries) the score rose to 0.8523 and fell back to 0.7449 once the referee was fixed.
2. **A correctness suite that is not the objective but can veto it.** Liquid's 974 existing
   tests; autokernel's five-stage harness (34/34 configs pass). pi's `checks_failed` exists
   precisely because a fast-but-broken edit otherwise wins.
3. **A fixed comparison basis.** karpathy's `TIME_BUDGET = 300` seconds is what makes
   successive `val_bpb` values comparable at all — a candidate cannot win by training longer.
4. **A bounded number of trials against a cost ceiling.** Liquid's ~120 experiments / 93
   commits; autokernel's 120 minutes per kernel. GPUMode's 1293 experiments for one 8.56x is
   the cost failure that shows why the ceiling matters more than the headline.
5. **Parallelism as a plateau breaker.** CORAL: one agent 1363→1350 cycles in 4.6 h; four
   agents 1363→**1103** in ~4.5 h. The single agent had stopped; the fan-out had not.

Numbers worth remembering, with their caveats: Liquid PR 2056 **53%** faster parse+render /
**61%** fewer allocations over **974** tests (**open and unmerged**, author-measured);
autokernel RMSNorm **5.29x** over eager PyTorch and **2.83x** over `torch.compile` at 83% of
peak bandwidth, softmax 2.82x, cross-entropy 2.21x (**pre-registered harness, and it
publishes its loss**: matmul 278 TFLOPS vs cuBLAS 800+); karpathy **0.997900 → 0.977287**
over 89 experiments (H100, 2.1%); steer CIFAR **0.9770** vs 0.9514 for a plain agent and
0.9585 for a hand-written reference. ^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## What failed

- **A loop with no ceiling.** karpathy's `program.md` says NEVER STOP and nothing counts
  iterations; uditgoenka makes "bounded by default" safety invariant #1 for the same reason.
- **A declared budget that is never enforced.** FAROS serialises `maxIterations = 3` and its
  runner is a single linear pass that never reads it — worse than no ceiling, because
  operators budget against it.
- **An LLM in the keep path.** FAROS's ranker is a preference model, not a measurement;
  the 56-system survey found LLM-as-judge both the most common and the weakest verifier.
- **A guard that is not the objective.** GEPA's KernelBench run reached pass@1 ~0.87 while
  speed returned to baseline.
- **Documentation drift.** Liquid's `autoresearch.md` claims a conformance suite its
  `autoresearch.sh` never runs.
- **Ceremony.** research-loop's ~20 CLI calls per experiment plus a ≥2-run confirmation, and
  a strategy contract frozen hard enough that a mid-campaign pivot needs a new campaign.
- **Harness lock-in.** evo's loop is `claude -p --resume --fork-session --permission-mode`;
  portability would be a rewrite, not a config change.

## Verdict

The transferable core is **not** the search algorithm — it is the accounting. Every system
that improved real code had a deterministic measurement it could not edit, a correctness
gate it could not talk past, a bounded trial count, and a record of what was kept. Every
system that failed at scale failed on one of those four, or on deciding who owns the revert.

For this template's contract, the ranking is: adopt the **verify/guard contract**, the
**script-owned trial lifecycle**, the **validated event ledger** and the **composite stop
policy** first; then the noise floor and the hidden holdout; then adapters. Search
sophistication (tree search, Pareto frontiers, reflection) is the last thing to add and the
least evidenced. See [[deterministic-keep-gate]] for the exit-code form this template
already committed to, and [[autoresearch-oss-landscape]] for the earlier 19-repo study of
loop mechanics.

## Related

- [[verify-guard-contract]] · [[script-owned-keep-revert]] · [[loop-stop-conditions]] ·
  [[reward-hacking-countermeasures]] · [[headless-harness-invocation]]
- [[autoresearch-contract]] — the three-file contract these mechanics slot into.
- [[deterministic-keep-gate]] · [[harness-portability]] · [[evaluator-legitimacy]]
- [[coral]] · [[faros]] — the multi-agent and the generate-and-rank reference designs.
