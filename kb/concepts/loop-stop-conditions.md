---
title: Loop Stop Conditions
created: 2026-10-28
updated: 2026-10-28
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: high
---

# Loop Stop Conditions

A loop with no stop is not a loop, it is a bill. Across the fifteen studied engines the
systems that produced usable results were the ones that ended on a **verdict**; the ones that
ended on **budget exhaustion** were the ones whose headline came from trial count rather than
convergence. ^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## The five conditions

| Condition | Best implementation | Common absence |
|-----------|--------------------|----------------|
| **Target reached** | leo-lilinxiao — a `complete` event is accepted only if the retained metric really satisfies the target, re-checked on replay; GEPA `ScoreThresholdStopper`; research-loop `absolute_improvement` / `relative_improvement` / `metric_value` | karpathy has no target; evo has "no target score in the loop" |
| **Plateau** | uditgoenka — trailing window of 5 derived `units remaining`, net progress = last strictly below first, so an oscillating-flat loop reads PLATEAU; CORAL `streak_for_epsilon` → reflect/consolidate/pivot; GEPA `NoImprovementStopper(patience)` | karpathy, evo, leo-lilinxiao, research-loop, FAROS; autokernel uses a revert streak as a proxy |
| **Max iterations** | uditgoenka 25 per subcommand (20 fix/scenario, 15 debug, 10 learn) plus `--max-cycles 50`; Thoth 10; aideml 20; research-loop `max_experiments` 1..100 | karpathy's document says NEVER STOP |
| **Wall budget** | research-loop takes `min(environment.timeout, experiment_timeout_seconds 1800, remaining campaign 7200)`; autokernel 120 min/kernel plus a 30 s `SIGALRM` per stage; Thoth 8 h | autokernel's 90 s benchmark warning is soft where a hard limit belongs |
| **Consecutive crashes** | autokernel `consecutive_reverts: 5`; pi's 20-consecutive-failure circuit breaker; Thoth retry limit 2 keyed by failure signature with an explicit non-retryable list | karpathy, evo, leo-lilinxiao (a crash is an error, uncounted) |

## Four design rules

1. **Bounded by default.** uditgoenka makes it safety invariant #1; `Iterations: unlimited` is
   an explicit opt-in. FAROS is the anti-pattern: `maxIterations = 3` is serialised into the
   session config and the runner never reads it — a ceiling that is declared but unenforced is
   worse than none, because operators budget against it.
2. **A disjunction, not a threshold.** autokernel's `MOVE_ON_CRITERIA` fires on whichever of
   `consecutive_reverts 5`, `pct_peak_threshold 90`, `speedup_threshold 2.0` or
   `max_minutes_per_kernel 120` comes first. Any single criterion can be gamed or can stall;
   the disjunction converges. Its own lesson: most kernels end on the 120-minute budget, i.e.
   one aggressive criterion dominates the rest.
3. **Refuse to start unbounded.** evo makes `--per-exp-timeout` **required** at `init`, so a
   missing timeout is a startup error rather than a silent infinite loop. This is the cheapest
   structural guarantee in the corpus.
4. **`unknown` is a state, not a zero.** uditgoenka excludes uncomputable cycles from the
   plateau counter, and turns five consecutive unknowns into `BLOCKED` with exit 3, so a
   crashed runner is never read as "still improving" — the classic silent failure of numeric
   loops. research-loop's `status` returns an explicit `termination_reason`
   (target-confirmed | experiment-budget-exhausted | campaign-timeout-exhausted) for the same
   reason.

## Plateau needs a derived scalar

Plateau on the raw metric is fragile: an oscillating metric nets flat while individual values
move. uditgoenka's derived scalar is `failing_tests + open_hard_regressions +
(metric_delta / metric_target)` — "units remaining", strictly decreasing when the loop is
making progress — and it prints `unknown` with exit 2 when an input is missing or the target is
zero. CORAL's version is `streak_for_epsilon`: consecutive attempts whose improvement is below
an epsilon, which escalates the prompt from reflect → consolidate → pivot rather than stopping.
GEPA's is patience over a window, exposed as `--plateau N`.

## Dry run is a stop condition too

Two of the three dry-run shapes are really "stop before spending":

- **Round 0 (uditgoenka)** — prove the predicate command runs and returns a value, screen every
  derived command, print the projected cycle budget, and stop there under `--dry-run`.
- **Plan + hash-bound approval (research-loop)** — `plan` prints the resolved contract
  (baseline_required, max_experiments, smoke_argv, full_argv, primary_metric,
  modification_scope, protected_paths, base_commit) and hashes it; `approve --plan-hash`
  re-derives and refuses a mismatch; every mutating command calls `ensure_approved`.
- **Baseline-as-preflight (leo-lilinxiao)** — no `--dry-run`; `init` runs verify and guard once
  on a clean branch and refuses to continue if the command dirties the repo, moves HEAD, writes
  control state, or produces an unparseable metric.

## Where this leaves a generic engine

`--target X` · `--plateau N` (on a derived units-remaining scalar, not the raw metric) ·
`--max-iterations N` · `--budget <duration>` · `--max-consecutive-crashes N`, with **at least
one required** and a default of all four bounded. `--dry-run` runs the round-0 gates and prints
the resolved contract without writing state. `status` must print the active conditions and the
reason the run stopped, or is still running. See [[fixed-time-budget]] for the per-attempt
budget this composes with.

## Related

- [[fixed-time-budget]] — the per-attempt comparability primitive.
- [[verify-guard-contract]] — what the stop conditions are evaluated against.
- [[script-owned-keep-revert]] — the component that enforces them.
- [[deterministic-keep-gate]] — the per-iteration decision, versus the per-run stop.
- [[autoresearch-engines-real-world]] — the 15-system evidence.
