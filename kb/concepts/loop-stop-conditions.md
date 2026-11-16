---
title: Loop Stop Conditions
created: 2026-10-28
updated: 2026-11-15
type: concept
tags: [autoresearch, research-method]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md, raw/articles/2026-11-15-downstream-frontier-distillation.md]
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

## The wall is arithmetic, not a check at the top (2026-11-15)

A backstop checked only at the top of an iteration **funds work it cannot finish**. The
downstream engine, run with `--max-wall 1680` and `--agent-timeout 750`, started a 750 s call
at t=900 s; the outer `timeout … 1800` then SIGKILLed it mid-call, so the measurement never
ran — and any salvage of that work never fired either. A bound may never kill the run it
bounds.

- **Reserve the tail in the predicate:** before starting an iteration, check that the
  remaining budget pays for it in full — `elapsed + agent_timeout + guard_timeout +
  repeats × verify_timeout >= max_wall` (3300 s at 900 + 600 + 3 × 600). The number is
  derived from the run's own config, not a literal: downstream's `ITERATION_TAIL = 120`
  paid guard/verify/decide and under-reserved a repeats-multiplied verify, so it was
  replaced by the exact reservation (2026-11-15). Use the *same* predicate at the loop top
  and for the stop reason, so "refused" and "why it stopped" are one function;
  `max_wall == 0` stays unlimited. A wall **at or below** the reservation is a preflight
  error (exit 2, naming the smallest usable wall) rather than a run that measures a
  baseline, finds iteration 1 unaffordable and exits 0 having done nothing.
- **Derive, but count the literals:** `ROUND_RESERVE 120`, `round = n·slot + reserve`
  (2,400 s for two 1,140 s seats), `MAX_WALL = round − 120` (`arena.py` literals the reserve,
  restated once), round-start budget `= round + 600`, and `cap × budget ≤ season wall`
  (7 × 3,000 s ≤ 21,600 s) — one derived chain with one literal to keep in step.
- **State the same wall in every layer that enforces it.** The wrapper's `timeout` and the
  inner `--max-wall` are one number, located structurally, and an argv carrying neither is a
  hard error: "an unbounded engine under a bounded seat is the bug, not a fallback". The
  first repair rewrote only the `timeout` argument, so an engine inside a 780 s seat still
  believed it owned 1,680 s and was killed from above; restating it in both places was a
  second PR.
- **Price the wall at the round, not at the worker.** A wrapper giving each worker a fresh
  full budget multiplies the cap by the worker count — two seats made a 3,600 s round against
  an 1,800 s cap, measured 2,915 s.
- **A worker below its floor of usefulness is not launched.** Record *not served* with an
  out-of-band exit code (`199` — no wrapper, shell or signal returns it), so a declined launch
  is never read as a timeout (124), a refusal (126) or a signal kill.
- **Leave the arithmetic honest.** With an 1,800 s round and a 750 s call, a 780 s seat starts,
  refuses to fund an iteration, and stops on the wall with 0 iterations. A round that is
  arithmetically a one-seat round should read as one — in the record, not in the log only.

The engine-side salvage that depends on this reservation is on [[deterministic-keep-gate]]
— the template stamps `salvaged` on a `keep` only, because a reverted tree banked nothing,
where downstream also sets the flag on a rejection; the per-competitor slot allocation and
the void-round rule are on [[fair-competition-invariants]]; where the refusal lands is
[[run-record-contract]].

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
- [[unattended-loop-recipe]] — who fires the loop when a human is not there, and the guards that stop it firing twice.
- [[autoresearch-engines-real-world]] — the 15-system evidence.
