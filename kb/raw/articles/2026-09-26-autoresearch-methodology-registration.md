---
title: Autoresearch methodology — registered template pattern (better/cheaper/faster on any X)
date: 2026-09-26
kind: article
source_url: https://github.com/karpathy/autoresearch
source_type: primary-upstream + real-world instance diff
ingested: 2026-09-26
sha256: 2879373f9e76b14f7549e9a359b61e2c006425cc24c8884266a7c3fb8bb6cc8b
tags: [autoresearch, methodology, optimization, kanban, game-theory, markov-chain, template]
---
# Autoresearch methodology — the registered template pattern

Deep-research registration of the autoresearch methodology, distilled from
karpathy/autoresearch (upstream, master, ~97k stars) and its first real-world
instance, `slash-roast/slash-commerce-pipeline-autoresearch` (private; commerce
pipelines). Full 7-item investigation archived 2026-09-26 in this repo's
research scaffold; this page carries the load-bearing findings.

## 1. The essence — three mutability classes inside one loop

The transferable pattern is NOT the ML training loop. It is the separation of
three mutability classes inside one loop, plus two structural commitments:

- **(a) NOBODY-EDITS evaluator** — owns the metric, the eval inputs, and the
  budget. Upstream: `prepare.py` (`evaluate_bpb`, `TIME_BUDGET=300`, pinned
  val shard). Instance equivalent: `pipeline/scripts/metrics-contract.py` +
  policy YAML. Import-only; a mechanical anti-cheat assertion
  (`train.evaluate_bpb is prepare.evaluate_bpb`, AC-TPL-041) makes
  redefinition fail CI rather than be noticed by reading.
- **(b) HUMAN-EDITED policy** — `program.md` states the job, the rules, the
  simplicity criterion, the crash policy. The only human lever during a run.
- **(c) AGENT-EDITED artifact** — exactly one file the agent may mutate
  (upstream `train.py`; per-domain: config, images, tests, SKILL.md, …).
- **(d) Fixed resource budget** per candidate (wall-clock, iso-compute) so no
  candidate wins by spending more. Platform-bound: record platform + budget
  with every claim.
- **(e) Append-only keep/discard ledger** — `results.tsv`
  (`commit / metric / memory / status{keep,discard,crash} / description`),
  untracked by git; every decision auditable and re-derivable.

**Loop:** tune → commit → run → `grep` scalar metric from the LOG (never the
agent's self-report) → strict improvement ⇒ advance branch, else `git reset`.
First run is always the baseline. NEVER STOP (one documented stop mechanism).
Crash/timeout are legal logged outcomes with fast-fail guards. Simplicity
criterion as anti-bloat tie-break (deletion wins are prized).

Evaluator/optimizer separation makes the objective **exogenous**: it removes
"make the metric easier" from the action space and relocates residual risk
from cheating (supervisable) to proxy-legitimacy / Goodhart (designable).

**Portability proof:** the slash instance changed the upstream `contract/` by
exactly **zero bytes** (all three files byte-identical to the template) and met
its objective by re-instantiating the same shape one layer down in `pipeline/`.
Only the DATA side ever moved (embedded corpus, stdlib-only, domain hooks,
`--results` auto-append, added Caveats section).

## 2. Optimization target — better/cheaper/faster made measurable

Instance goal: **max test coverage, min wall time, min LLM cost** under eight
standing constraints. The slogan resolves to seven field families
(better-UX, better-security, cheaper-images, cheaper-tests, cheaper-LLM,
faster-prod, faster-iterate) reduced to counts/byte-sums, then tiered:

| Tier | Meaning | Gate? |
|------|---------|-------|
| T0 | exact, reproducible (image bytes, test counts) | may gate |
| T1 | exact but drifting — value real, delta unattributable without pin (`audit_db_date`, `price_table_sha`, `ui_repo_commit`) | only beside a recorded pin; exit 2 if pin absent or moved |
| T2 | statistical (median-of-N; measured 11–13% wall-second spread on identical input) | `gate: false` enforced by policy lint |
| T3 | judgment → counted (only the violation count) | count only |

`compare --prev/--next` exit contract: **0 keep / 1 discard / 2 invalid
snapshot**; an unmeasured gate forces 2. Wave-1 instance wins: lean images
(fleet 2711→1927 MB, −29%, boot-verified per service), CI economy (10→6 jobs,
p50 ≤12 min instrumented), deterministic metrics contract (21 field-instances).

**Evaluator legitimacy:** the only admissible judge is the deterministic,
LLM-free script — determinism makes cycle deltas content-attributable; an LLM
judge reintroduces exactly the variance the loop engineered out.

**Honesty gap (measured):** docs/10 shows the instance optimizes 2 of its 3
headline dimensions — per-cycle wall time and LLM cost were NOT recorded at all
(league `cost` = constant 1.0; `estimated_cost_usd` 0/2757 sessions), while
D/escape_rate/tau saturated and `gap_debt` rose 31→467→87. Template rule:
ship duration+cost+coverage fields in the FIRST snapshot; never claim a
favourable direction unless the series is `moving`.

## 3. Generative process — the kanban factory (and the game layer)

**Single loop → factory.** When the objective itself includes wall-time/cost,
candidates become cards on a queue: fixed DAG of hand-authored cards per
cycle, gateway dispatcher, ≤3 concurrent LLM workstreams, 7200 s hard ceiling
per card, cycle = DAG run keyed by idempotency prefix, season = outer loop at
K=3 cycles. Re-seed crons + `chain-orchestrator.sh` close the loop (new cycle
on upstream-terminal, backstop idle, or never-ran). Self-healing: watchdog
classification + digest, janitor zombie reclaim, default-deny policy resolver
(`--apply --max-actions 3`), LLM-free blocked-resolution predictor.

**Why a card-graph beats one agent loop:** parallelism under the shared cap
(zero-token queueing, `max(a,b,c)` fan-out), separation of concerns /
anti-Goodhart (one writer per track, context rationing, independent arbiter),
resumability (DB as durable job store), audit trail (handoff + exec-summary
comments), human-free operation.

**Game layer (add only when the metric saturates or lies):**
- **Defender** (Stackelberg leader) commits first — verifier-first topology,
  failing test written before the fix; released claims only.
- **Attacker** (best responder) hunts with point-of-view campaigns; PoV
  contract (no proof-of-violation, no points) + context rationing (reads only
  released claims, no kb authority) make its failing PoVs external ground
  truth the defender cannot fabricate — the holdout that stops Goodhart.
- **Optimizer** (mechanism designer) prices the budget: `max Q_d s.t. Y_a ≥ τ,
  d+a ≤ 3`; λ = shadow price of the attacker-yield floor, μ = shadow price of
  one LLM slot; `λ←max(0, λ+η(τ−Y_a))` is projected dual ascent; the update
  is the PID integral term.
- **Conductor** (referee) polices information asymmetry (symmetric referee
  block), pinning/pin abuse, and layered hot-fixes (never bypasses the
  janitor; byte-identity audited by read-back).
- **Survivor ledger + league:** declined attack classes → `hunted_classes` /
  `campaign_prompts` seed the next cycle (static graph, learning content);
  Pareto-dominance league on (mean classes, mean D) renders
  PROMOTE/KEEP/RETIRE per graph variant — PBT (Jaderberg 2017) fused with
  AlphaStar-league selection.

**Measured caveat:** in 22 live cycles the regulator never fired (λ=μ=0,
slot_mix constant {2,1}) — the dual CANNOT move under the recorded
parameterization (τ saturated above realized attacker yield ⇒ λ≡0 by
complementary slackness; d+a always equals cap ⇒ μ≡0 by construction). A
regulator that cannot bind is dead code; template rule: verify the
multipliers actually move before trusting the mechanism.

## 4. Formal mapping (canonical sources)

| Mechanism | Formal concept |
|---|---|
| keep/discard branch loop | elitist (1+1)-ES / stochastic hill climbing; MDP with state = codebase+ledger, action = edit, reward = Δmetric, policy = the LLM (arXiv:1706.02887) |
| board chain | finite Markov chain; statuses = states, dispatcher = transition kernel, done/blocked = absorbing; the re-seed cron is the closure operator making the chain irreducible/aperiodic ⇒ ergodic with stationary status distribution |
| defender×attacker | Stackelberg security game; scored by minimax exploitability gap; campaign set per cycle = mixed strategy |
| optimizer λ/μ | Lagrange multipliers / projected dual ascent on `L = Q_d + λ(Y_a−τ) + μ(3−d−a)` |
| league/Pareto seasons | population-based training (arXiv:1711.09846) + AlphaStar league selection |
| metric risk | Regressional Goodhart (arXiv:1803.04585) — sample on-policy output, never trust the frozen scalar alone |

## 5. Instantiation recipe — "optimize X better/cheaper/faster using autoresearch"

**Preconditions (refuse if unmet):** (1) scalar metric, known direction;
(2) automated evaluation, no human in the loop; (3) one editable artifact the
agent can mutate. ("If you can score it, you can auto-research it.")

1. Name X and the ONE agent-editable artifact; declare everything else out of bounds.
2. Freeze the evaluator: immutable module, import-only, object-identity anti-cheat test in CI.
3. Policy-as-data: tiers, keep-direction, gates, pins, candidate ranking in YAML the evaluator reads — never in code, never in cards.
4. Fixed wall-clock budget in the evaluator's constants; instrument duration/cost/size fields from the first snapshot.
5. Keep/discard ledger, append-only, untracked; `compare` 0/1/2 exit contract.
6. Write `program.md`: goal, budget, can/cannot rules, simplicity criterion, crash policy, NEVER STOP, Goodhart caveat.
7. Cheapest-stack eval harness; baseline run first, always.
8. Tier every metric field T0/T1/T2/T3; T1 gates only beside a recorded pin.
9. Add a candidate queue (kanban factory) only when wall-time/cost are themselves objectives.
10. Sync rule: single authoritative side; repo canonical, live = deploy target; `--check`/`--apply` with a confirmation guard.
11. Add the adversary only when the metric saturates or lies (PoV contract mandatory).
12. Add the optimizer only when two producers compete for one budget.
13. Cap/cadence invariants: hard ceiling per candidate, backstops, re-seed cadence — and verify windows cannot be silently dropped.
14. Watchdog/janitor last; deterministic, LLM-free, dry-run by default.

**Ladder rule:** add a layer only to answer an OBSERVED failure — queue ←
cost/time must be optimized; adversary ← metric saturated or lied; optimizer ←
budget contention; cap invariant ← silent window loss; watchdog ← silent stall.
The minimal viable instance is the single-loop contract alone (~13 AC-TPL
tests); everything above it is purchased by evidence, and may be retired again
(the instance retired model pinning and re-instated it one layer lower at
execute time).

**Known failure modes (all measured in the instance):** Goodhart (val_bpb −55%
while output collapsed into `import torch` repetition); evaluator illegitimacy
(routing-log path wrong for 2/3 profiles ⇒ ~38% cost undercount; constant-1.0
placeholder cost); unmeasured cost/time (22 cycles, no duration/cost field);
cap-ceiling wedges (tick inside cap silently drops a window, exit 0); saturated
series read as progress (D pinned 99.92–100.00, escape_rate structurally 1.0).

## Evidence table (multi-source)

| Source | What it grounds |
|---|---|
| https://github.com/karpathy/autoresearch — `program.md` (upstream master, files sha256-verified 2026-09-26) | contract trio, loop invariants, simplicity criterion, NEVER STOP |
| slash-commerce-pipeline-autoresearch `docs/02` (verdict works; 17 AC-TPL tests green 2026-09-26) | contract adaptation; invariance of the three-role split |
| same repo `docs/07, 11, 15, 18` (partial / works / works / works) | kanban factory, dynamic scheduling, ops source-of-truth, self-healing |
| same repo `docs/09, 10, 13` (partial / partial / works) | game layer, research metrics honesty gap, conductor |
| same repo `docs/19` (verdict works, 2026-09-25) | better/cheaper/faster Wave 1, metrics contract, T0–T3 tiers |
| same repo `docs/16, 17` (works) | LLM-free predictor + default-deny resolver |
| template-agentic-ready-repo `AGENTS.md` (25-heading skeleton, placeholder title) | doctrine layer separable from contract/ops |
| Goodhart arXiv:1803.04585; (1+1)-ES arXiv:1706.02887; PBT arXiv:1711.09846; Stackelberg/Pareto/Markov canonical refs | formal mapping |

## Open questions

- The Goodhart/"sample generated output" caveat is NOT upstream karpathy — it
  was added by this template lineage's `contract/program.md` (Caveats section);
  the two linked upstream X threads were not checkable.
- The slash instance's shipped contract is still a byte-level char-LM demo;
  genuinely non-text evaluators (web load time, cost ledgers) exist as
  prescriptions, not as shipped harnesses.
- Dual regulator inertness (KR2), season loop (PBT) designed-not-observed,
  Markov transition matrix never estimated from data — formal layers are
  structural readings, not measured dynamics.
