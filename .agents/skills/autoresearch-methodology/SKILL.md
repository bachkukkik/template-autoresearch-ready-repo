---
name: autoresearch-methodology
description: Use when instantiating or registering an autoresearch loop.
---

# Autoresearch Methodology — template instantiation for any X

**Triggers:** "optimize X to be better, cheaper, faster using autoresearch";
"register the autoresearch methodology"; "run an autonomous research loop on X".

Registered 2026-09-26 from deep research on karpathy/autoresearch (upstream) +
slash-roast/slash-commerce-pipeline-autoresearch (first real-world instance).
Canonical ingest: `kb/raw/articles/2026-09-26-autoresearch-methodology-registration.md`
(in template-autoresearch-ready-repo). Full 7-item report archived in that
repo's research scaffold.

## The invariant core (never substitute)

1. **Three mutability classes in one loop:**
   - NOBODY edits the evaluator (owns metric + eval inputs + budget; import-only;
     CI object-identity anti-cheat test: `candidate.evaluate is evaluator.evaluate`)
   - HUMAN edits the policy file (`program.md` — job, rules, simplicity criterion,
     crash policy, NEVER STOP)
   - AGENT edits exactly ONE artifact.
2. **Fixed wall-clock budget per candidate** (iso-compare; record platform+budget with every claim).
3. **Append-only keep/discard ledger** (commit | metric | cost | status{keep,discard,crash} | description;
   untracked; read the metric from the run LOG, never the agent's self-report).
4. **Loop:** tune → commit → run → metric → strict improvement ⇒ keep, else reset.
   Baseline run first. NEVER STOP.

## Preconditions (refuse the task if unmet)

- Scalar metric with known direction ("if you can score it, you can auto-research it")
- Automated evaluation, no human in the loop
- One editable artifact the agent can mutate

## Instantiation recipe (in order)

1. Name X + the one editable artifact; declare all else out of bounds.
2. Freeze evaluator (module + policy YAML it reads; policy-as-data, never code).
3. Fixed budget in evaluator constants; instrument duration+cost+size from the FIRST snapshot
   (measured lesson: the instance skipped this and could optimize only 2 of its 3 goals).
4. Ledger + `compare` exit contract (0 keep / 1 discard / 2 invalid snapshot).
5. Write `program.md`; tier metrics T0 exact-gating / T1 pinned-or-refused /
   T2 statistical-nogate / T3 counted-judgment.
6. Baseline first; then run the loop.

## Scaling ladder — add a layer ONLY to answer an observed failure

| Add | Only when |
|---|---|
| Kanban candidate queue (cards, ≤N workstreams, hard per-card ceiling, re-seed cron = closure operator) | wall-time/cost are themselves objectives |
| Watchdog/janitor (deterministic, LLM-free, dry-run default) | silent stalls/wedges observed |
| Attacker board (PoV contract: no proof-of-violation, no points; context rationing) | metric saturated or lied (Goodhart) |
| Optimizer board (dual ascent: λ prices attacker-yield floor τ, μ prices a slot) | two producers compete for one budget |
| Conductor referee | pinning / information-asymmetry abuse observed |

Game mapping: defender=Stackelberg leader (verifier-first), attacker=best responder,
board chain=Markov chain (re-seed makes it ergodic), seasons=PBT + Pareto league.

## Failure modes to warn about (all measured in the instance)

- Goodhart: metric improved −55% while output collapsed — always sample real output, never trust the frozen scalar alone.
- Evaluator illegitimacy: wrong log path ⇒ ~38% cost undercount; constant placeholder cost.
- Unmeasured cost/time ⇒ 2 of 3 headline goals unoptimizable.
- Cap-ceiling wedges: a tick inside the cap silently drops a window, exit 0.
- Saturated series read as progress: no favourable-direction claim unless the series moves.
- Regulator that cannot bind (λ,μ provably ≡0 under the parameterization) = dead code; verify multipliers move.

## Calibration lessons (from the three worked examples, 2026-09-26)

Three full runs (music-abc text LM −42% val_bpb; iris kNN 0.933→1.000 accuracy, higher-is-better; non-ML hot path 8.4× speedup under an exact-output gate) validated the template. Non-obvious lessons:

- **The loop catches driver bugs for free**: an anchor bug that patches the wrong site yields an identical metric → mechanical discard. If a candidate ties the incumbent exactly, suspect a mutation that never fired.
- **Reset must fire on crash, not just discard** — otherwise HEAD ends on the broken commit.
- **Seed/split choice with zero headroom is a legitimate recorded decision**: if the baseline IS the family ceiling, pick a split with headroom and document the scan (metric, rule, dataset unchanged).
- **Exact-output gates must be shape-proof**: a spot-check on a few fields can pass a badly wrong candidate; compare the full output. Add a labeled `attack:` (fast-but-wrong) candidate once to prove the gate fires.
- **Strict improvement blocks simplification**: add a noise floor — keep if metric ≤ incumbent×(1+ε) AND code shrinks; otherwise the simplicity criterion is dead letter.
- **Timing fields are T2**: jitter is expected between runs; never treat a wall-clock delta within ~10% as signal.

## When NOT to use

- Success is subjective or requires human judgment per iteration (T3 judgment fields cannot gate).
- Evaluation is slow/expensive relative to candidate value — the loop economics fail.
- No local-move structure: a candidate must be a small mutation of the previous keeper.
- Noise σ comparable to the target improvement delta.
