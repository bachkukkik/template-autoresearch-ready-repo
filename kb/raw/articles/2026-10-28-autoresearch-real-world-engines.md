---
source_url: https://github.com/webfuse-com/awesome-autoresearch
ingested: 2026-10-28
sha256: 68f1310ab1a2ee0b172a08e89a312e11940e90e77209422918ef6e524cbb5807
kind: article
title: Autoresearch engines that improve real code — 15-system evidence table and the engine contract
---

# Autoresearch engines that improve real code

Synthesis of a 15-record study (2026-10-28) of autonomous-research implementations,
mined for the mechanics a **generic, harness-pluggable engine CLI** needs: a verify/guard
contract, script-owned keep/revert, a validated ledger, composable stop conditions, a
dry run, noise handling, and per-harness invocation. Each record was built from a
read-only clone of one repository at a pinned commit, against one fixed extraction
schema (basic facts, loop contract, harness surface, evidence). **Nothing was
executed**; every number below is as published by the repo or its linked write-up,
and self-reported numbers are marked as such.

The unit of interest is not "a research agent" but **a loop that measurably improves
real code**. That filter is severe: of the 15 records, three are not engines at all
(one curated list, one specification, one platform whose loop never iterates), three
have no measurable result, and one has results whose confidence intervals cross zero.
The remaining systems, plus the list's documented case studies, are the evidence.

## Evidence table

Stars as recorded at the pinned commit (a moving count, context only). `head_sha`
abbreviated to 12 characters — full pins in *Pins* below.

| Repo (stars) | SPDX | head_sha | Loop shape, mechanism + file path | Real-world numbers |
|---|---|---|---|---|
| `Human-Agent-Society/CORAL` (1.1k) | Apache-2.0 | `0123dfb939b3` | N agent CLIs, each in its own git worktree, scored by an out-of-process grader daemon; `coral eval -m` commits the tree and polls for a `ScoreBundle`; `coral/grader/daemon.py` grades in a detached worktree under `.coral/private/grader_checkouts`; `.coral/public` (notes/skills/attempts) symlinked into every workspace, `.coral/private` unreadable by the agent | kernel `kernel_builder` 1363→1350 cycles, one agent, 4.6 h; 1363→**1103** with 4 agents, ~4.5 h (~19% cumulative); Erdős C5 0.38089 vs AlphaEvolve 0.38092 in 34 min vs 5.2 h; OpenVaccine **+20.5%** over the top human entry in 2 evaluations |
| `OpenNSWM-Lab/FAROS` (3.0k) | MIT | `60ce4bc235f1` | FastAPI + Next.js platform; per round generates up to 3 candidate unified-diff patches for the same gap, ranks them with an LLM on correctness .30 / completeness .25 / efficiency .15 / readability .15 / safety .15, applies the winner into a file-copy workspace (`backend/app/code/run/workspace.py::_copy_repo` + `apply_patch`); `EvalScorer.WEIGHTS` = syntax .30 / risks .20 / lint .10 / tests .40 → 0–100 + A–F; `execution_gate()` in `backend/app/modules/code/execution_assessment.py` | None on real code. Only an offline NLP benchmark: SciFact dev F1 **0.7746** vs 0.7460 lexical, ECE 0.0345 vs 0.0819 — every 95% bootstrap CI crosses zero, as the authors acknowledge |
| `uditgoenka/autoresearch` (6.8k) | MIT | `050e30dc4ba0` | Harness-portable Agent Skill (Claude Code / OpenCode / Codex) plus a deterministic bash seam: `verify` prints a number, `guard` must always pass, agent commits then `git revert HEAD --no-edit` on a loss; `.agents/skills/autoresearch/scripts/orchestrate.sh` adds `classify`, `units`, `plateau`, `screen-cmd`, `verdict`, `validate-state`; `score-regression.sh` is a tiered green-to-red gate | None quantified. The only own number is a token-cost cut (813-line skill ≈100K tokens → 41-line router + 12 files ≈5–8K tokens, "95% token reduction"); "100 experiments per night" is attributed to upstream Karpathy |
| `leo-lilinxiao/codex-autoresearch` (3.0k) | MIT | `0f54c5717074` | Codex skill + strict stdlib control script; the script owns commit, measurement, rollback and history. `scripts/autoresearch.py::finish` refuses unless branch/HEAD/scope/cleanliness all match; `scripts/autoresearch_core.py` holds `RUN_KEYS`, the per-event schema, `derive_state` replay and `parse_metric_output`; detached controller spawns one `codex exec --ephemeral` worker per iteration | None. Fixtures only (`tests/e2e-fixtures/counter_reduction`), plus an illustrative README transcript — explicitly not a measured result |
| `webfuse-com/awesome-autoresearch` (2.6k) | CC0-1.0 | `473fe708322e` | Curated list, 113 entries — no engine. Its value is four documented case studies: Shopify Liquid PR 2056, GPUMode `eigh`, tennis XGBoost, and a 56-system survey | Liquid PR 2056 **53% faster** parse+render, **61% fewer allocations**, **974-test** guard, ~120 experiments → 93 commits (open, unmerged); GPUMode `eigh` 1293 experiments → 8.56x with **6 reward hacks** caught by a **412-test hidden** suite; tennis 0.7454 → 0.7609 honest → **0.8523 gamed** |
| `karpathy/autoresearch` (98.7k) | MIT by README only (no LICENSE at HEAD) | `228791fb499a` | ~630-line nanochat `train.py` + prose `program.md`; the loop is agent-executed: edit, `git commit -am`, `uv run train.py > run.log`, `grep "^val_bpb:\|^peak_vram_mb:" run.log`, keep or `git reset --hard HEAD~1`. `prepare.py` pins `TIME_BUDGET = 300`, `MAX_SEQ_LEN = 2048`, `VOCAB_SIZE = 8192`, validation shard `shard_06542`; `results.tsv` is untracked so it survives resets | **0.997900 → 0.977287** over 89 experiments (H100, 2.1% relative); third-party 1.395 → 1.138 over 87 experiments (L4, 18.4%) |
| `davebcn87/pi-autoresearch` (8.2k) | MIT | `04b8a50dac7e` | `pi` extension registering `init_experiment` / `run_experiment` / `log_experiment`; `parseMetricLines` scrapes `METRIC name=value` lines from the project's own benchmark; `checks.sh` is a separate correctness gate whose failure verdict is `checks_failed`; benchmark file guarded against agent edits; agent commits, extension reverts with `git checkout -- .` + `git clean -fd` (`.auto/` excluded) | Reports the Shopify Liquid PR 2056 case (same numbers as above): ~53% faster, ~61% fewer allocations, validated by the project's 974-test suite over ~120 experiments |
| `junjunjunbong/research-loop` (1) | Apache-2.0 AND CC-BY-4.0 | `8185b094aa4e` | Deterministic Python runner, **no LLM call**; `prepare` creates `autoresearch/<campaign>/<experiment>` plus an external worktree under `~/.cache/research-loop/worktrees/` so the base checkout is never touched and **nothing is ever reverted**; `plan` hashes the contract into `plan_hash`, `approve --plan-hash` gates every mutating command; `src/research_loop/metrics.py` parses regex/json/jsonl through the approved Evaluation Contract, applies validity gates and a six-state verdict | None. Only `examples/mock-project/`; v0.3 is local-CPU only, no GPU/remote/paid execution and no parallel experiments |
| `xieyulai/steer` (28) | Apache-2.0 | `76d8a2fa6835` | Protocol-first harness: frozen read-only `contract/` vs writable `workspace/`, `INFO_PERM` read barrier, `TIME_BUDGET` Config-Only; `experiment.py::should_keep` compares the primary metric against `keep.primary_delta_rel` with `TimeGuard` in the decision path, then swaps the workspace snapshot; `check_goal.py` returns the task-success exit code; G1–G4 preflight before any budget is spent | CIFAR, from the sibling `xieyulai/steer-cifar` ledger: 39 rows, best **0.9770** vs 0.9514 plain agent and 0.9585 hand-written reference; the same ledger publishes two collapsed runs (0.1120, 0.8847) |
| `SeeleAI/Thoth` (51) | MIT | `e74c6e0de8a1` | Dashboard-first phase machine `plan → execute → validate → reflect`; six files per run under `.thoth` (`run/state/result/artifacts/events.jsonl/phase_state.json`), `phase_state.json` is the resume cursor; `validate` checks a default output schema instead of a scalar metric; retries keyed by failure signature with an explicit non-retryable list; a guard `bin` shadows `rm`, `git clean`, `git reset` for workers | None found |
| `jmilinovich/goal-md` (166) | MIT by README only (no LICENSE at HEAD) | `8f39b8ab5afa` | Specification, not an engine: the agent authors a measurable fitness function first, then iterates; `scripts/score.sh --json` prints `{score, max, pct, details[], feedback[]}`; `iterations.jsonl` records `before/after/action/result/note`; metric mutability declared as a mode (Locked / Split / Open); no runner, no budget, no resume | Author narrative only (Playwright suite 47 → 83). The reproducible number is the opposite kind: the bundled example **starts at 130/130** against a 125/130 target |
| `RightNow-AI/autokernel` (1.6k) | MIT | `78435821cc3d` | GPU-kernel loop; `bench.py` prints a tagged block `=== FINAL ===` + `correctness:` / `throughput_tflops:` / `speedup_vs_pytorch:` / `pct_peak_compute:` / `bench_time_seconds:`; a five-stage correctness harness (smoke → 8–10 shape sweep → stability → determinism → edge cases) runs cheapest-first with early abort; `orchestrate.py` holds `MOVE_ON_CRITERIA = {consecutive_reverts: 5, pct_peak_threshold: 90, max_minutes_per_kernel: 120, speedup_threshold: 2.0}` and writes state atomically (`.tmp` + `os.replace`) | H100 FP16, arXiv 2603.21331: RMSNorm **5.29x** over eager PyTorch and **2.83x** over `torch.compile` at 83% of peak bandwidth; softmax 2.82x; cross-entropy 2.21x; beats `torch.compile` on 12 of 16 configs; **34/34** configs pass all five stages; matmul 278 TFLOPS vs cuBLAS 800+ (published loss) |
| `evo-hq/evo` (1.5k) | Apache-2.0 | `c70c04b4d2da` | Experiment graph: `keep = compare_scores(metric, score, parent_score) and gate_passed`; gates inherited root→node, de-duplicated by name, `_init_gate` prepended; `pre` gates (including an opt-in leak grep for exact validation strings) fail as `PRE_GATE_FAILED` before benchmark spend; engine captures `diff.patch` per attempt and restores the parent itself; `--per-exp-timeout` is **required** at `evo init` | None in the repo |
| `WecoAI/aideml` (1.6k) | MIT | `ad73d227af48` | Tree search over whole single-file ML programs; the candidate prints its own metric from a hold-out split and a second LLM answers `submit_review {is_bug, summary, metric, lower_is_better}`; `Node`/`Journal` in memory, `logs/<exp>/journal.json` rewritten each step; draft → debug (depth ≤ 3) → greedy improve `get_best_node()`; `WorstMetricValue` makes `None` always sort last | MLE-bench (75 Kaggle competitions): README claims 4x more medals than the best linear agent, attributed to arXiv 2410.07095; its own live E2E test explicitly does **not** assert improvement |
| `gepa-ai/gepa` (7.2k) | MIT | `d7918ba2f382` | Reflective prompt evolution; `oa/engines/autoresearch.py` writes `candidate.txt`, runs `eval.sh`, which talks to an HTTP **EvalServer** that owns the scoring code; the test split is sealed at the transport layer and validation examples are folded into the visible pool; keep = promote `candidate.txt` → `best_candidate.txt`; `stop_condition.py` provides NoImprovement / ScoreThreshold / Signal / Composite stoppers; agent runs inside `bwrap` | Paper (ICLR 2026 Oral): ~6% average and up to 20% over GRPO with up to 35x fewer rollouts. Its own `gotchas.md` publishes the failures: KernelBench pass@1 ~**0.87** while speed returned to baseline; winner's curse **0.87 → 0.60 / 0.57** on re-evaluation |

### Pins

```
Human-Agent-Society/CORAL          0123dfb939b35228cf2c1fde224cd0561e727408
OpenNSWM-Lab/FAROS                 60ce4bc235f169d71f2d11dbe37445b4e402b528
uditgoenka/autoresearch            050e30dc4ba0974b03f2873111b9901ec3211390
leo-lilinxiao/codex-autoresearch   0f54c571707487f59486ba7c50d405edfc746c19
webfuse-com/awesome-autoresearch   473fe708322e96f379316fc8e15cbee1da985e62
karpathy/autoresearch              228791fb499afffb54b46200aca536f79142f117
davebcn87/pi-autoresearch          04b8a50dac7efe80ffc91648bd00ed9b022e24c2
junjunjunbong/research-loop        8185b094aa4e3f3c633aa4b2e1255737e3c7d4f8
xieyulai/steer                     76d8a2fa6835a5783327a63a7b7d2c08948761c3
SeeleAI/Thoth                      e74c6e0de8a110d5e07249880d0e4e4f0ceab691
jmilinovich/goal-md                8f39b8ab5afa6b017d36f871d3057a5155aad678
RightNow-AI/autokernel             78435821cc3d5756ba6ee1785c397f6d8fa8c90d
evo-hq/evo                         c70c04b4d2da2f2deb95d1d185b07d88d24f2ea7
WecoAI/aideml                      ad73d227af481bea3de06f884f41b2993dd6453a
gepa-ai/gepa                       d7918ba2f382d5d0652c10814bb278c1c7ffa7c3
```

Case-study URLs: Shopify Liquid PR 2056 — <https://github.com/Shopify/liquid/pull/2056>.
GPUMode `eigh` — the `elianaive.com` write-up. Tennis XGBoost — the `nickoak.com`
write-up. 56-system survey — `haizhaoyang.github.io`. CORAL paper — COLM 2026,
arXiv 2604.01658. autokernel — arXiv 2603.21331. GEPA — ICLR 2026 Oral.

## 1. The verify/guard contract

Eight of the fifteen converge on the same shape: **`verify` prints exactly one
number; `guard` prints nothing and returns an exit code; direction and target are
pinned once at run start; anything unparseable is an error, never a zero.**

The parse surface, strongest first:

1. **Tagged block.** autokernel's `bench.py` terminates with `=== FINAL ===` followed
   by `correctness:`, `throughput_tflops:`, `speedup_vs_pytorch:`, `pct_peak_compute:`,
   `bench_time_seconds:`. The orchestrator parses tags, so a missing or malformed line
   is a hard parse failure rather than a silently wrong score. It is also readable in a
   log by a human, which is why it is the single most reusable idea in that repo.
2. **JSON on the last line only.** leo-lilinxiao reads only the final non-empty stdout
   line: a finite decimal, or — with `--metric-key` — a JSON object whose named key is a
   finite decimal (`core.py::parse_metric_output`). All arithmetic is `Decimal`, so float
   drift cannot make an equal metric look improved. A non-zero exit is a hard error even
   when the measurement itself succeeded.
3. **JSON object with detail.** goal-md's `{score, max, pct, details[], feedback[]}` —
   `details` gives the agent something actionable, `feedback` the human something readable.
   One parseable object beats scraping stdout.
4. **Per-example score vector.** GEPA keeps a Pareto frontier over per-instance scores, so
   a candidate that wins the average but collapses on a subset is not automatically preferred.
5. **Repeated tagged lines.** pi-autoresearch scrapes every `METRIC name=value` line, so one
   run can yield several named metrics; only the configured primary drives the keep decision.
6. **Free-form log interpreted by a model.** aideml: the candidate prints its own metric and
   a second LLM answers `{is_bug, metric, lower_is_better}` under a JSON schema. This is the
   weakest option in the corpus and aideml's own anti-pattern list names it as such.

**The guard is a separate axis with four hard rules.** (a) It must already pass at
baseline or `init` fails (leo-lilinxiao; uditgoenka runs a guard baseline in preconditions).
(b) A guard failure discards an *improvement* (leo-lilinxiao `autoresearch.py:612-656`;
pi records `checks_failed` as its own verdict rather than a zero score). (c) Guards run
cheapest-first and short-circuit — autokernel's five stages abort on a smoke failure
before any benchmark time is spent, evo's `PRE_GATE_FAILED` fires before benchmark spend.
(d) The reason is a first-class verdict, so a report can distinguish "no gain" from
"broke the build".

**Direction is pinned, never re-derived.** leo-lilinxiao writes `lower|higher` into
`run.json`; uditgoenka writes `# metric_direction:` into the TSV header; aideml resolves
direction once per run and *logs* a later conflict instead of silently re-ranking;
research-loop puts direction inside the hash-approved contract. The failure this prevents
is maximise/minimise drift, which silently inverts every later decision.

**The guard you document must be the guard you run.** The Liquid case study is the
canonical defect in this corpus: `autoresearch.md` claims the liquid-spec conformance
suite runs as part of the loop, while `autoresearch.sh` only invokes `bench.sh`. The
documented guard and the executed guard diverged, so the loop was less protected than
its own write-up said. The mechanical fix is cheap — parse the guard commands named in
the program document and assert they appear in the runner script, or generate the
document from the script — and no other defect here is as cheap to detect or as
expensive to miss.

## 2. Who owns keep/revert

| Owner | Systems | Mechanism |
|---|---|---|
| Control script / engine | leo-lilinxiao, evo, steer, gepa, FAROS, research-loop | script commits, measures, then keeps or reverts by attempt id; the diff is captured per attempt |
| The agent | karpathy, CORAL, pi-autoresearch, autokernel, uditgoenka | a prose protocol; the agent runs `git reset --hard HEAD~1` / `git revert` / `git add -A && git commit` |
| Nobody | goal-md, Thoth, aideml | the spec says "keep or revert"; there is no mechanism, or the search is implicit |

The evidence against agent-owned revert is concrete and each repo states it about
itself. autokernel: "letting the agent run `git reset --hard` itself — the engine should
own the revert via a worktree or a captured patch, otherwise the ledger cannot prove what
was undone". CORAL: `reset --hard HEAD~1` "only works while the agent's decision matches
the tip, so a wrong revert discards a good commit", and an agent that forgets to revert
keeps a regression that the engine records but does not undo. pi-autoresearch: because the
commit is agent-authored there is no allow-list and no message policy, and `git add -A`
sweeps unrelated files that a later `checkout -- .` cannot distinguish. karpathy:
`git reset --hard` discards uncommitted work, and a mis-grep silently records a wrong metric.

**Scope enforcement, three grades.** (1) *Per-path allowlist plus protected prefixes,
diff-checked by the script*: leo-lilinxiao (`core.py:768-812` — repo-relative paths,
globs and `..` and absolute paths rejected, `autoresearch-results`, `.git`,
`.agents/skills/codex-autoresearch` refused); research-loop (`git diff --name-only
parent..HEAD` must be non-empty, contain no `protected_paths`, and every path must sit
inside `allowed_paths`); steer's structural equivalent, where the whole `contract/`
directory is frozen and read-only so the measurement cannot be edited at all. (2) *A
frozen evaluator plus a convention*: karpathy (`prepare.py` off-limits by instruction),
autokernel (the guard is a script in the repo the agent edits — no checksum, no read-only
mount). (3) *None*: pi-autoresearch guards only the benchmark file, CORAL has "no per-path
allowlist on which repo files the agent may edit", aideml has "no allowed-path list, no
write guard, and the child inherits the caller's uid, network and environment".

**Trial mechanics, cheapest first.** A throwaway worktree per attempt (research-loop;
CORAL's `git worktree add --detach` for grading) or an uncommitted trial with a captured
patch (evo) or a copy-of-repo plus `apply_patch` (FAROS) all leave the branch history
clean. Commit-then-revert (leo-lilinxiao, uditgoenka, pi) doubles commit volume and forces
history rewriting on every discard — a cost leo-lilinxiao's own anti-pattern list names
against itself, and the reason research-loop prefers "no revert at all".

**The ledger.** The strongest form is event-sourced and *validated on read*. leo-lilinxiao's
`events.jsonl` carries an exact per-event field set for baseline/iteration/blocked/complete/
error/resumed/stopped; duplicate keys, NaN/Infinity, unknown types, missing fields and a
non-contiguous `seq` all fail loudly; and `derive_state` re-checks semantics on replay — a
keep must be a genuine improvement with a passing guard and `head == trial_commit`, a discard
must point at its revert commit, a `complete` must actually satisfy the target. evo is
second: one directory per attempt holding `outcome.json`, `attempt_state.json` (a nine-phase
ordered state), `diff.patch` and `traces`, so any recorded score can be reproduced by
re-applying its patch and a crash resumes at the *phase*, not the iteration. The weak form
is a write-only log: goal-md writes `iterations.jsonl` with no reader, aideml rewrites
`journal.json` every step while `run()` always constructs a fresh Journal, and karpathy's
`results.tsv` has no validation at all, so a hallucinated row is indistinguishable from a
real one.

## 3. Stop conditions

| Condition | Best implementation | Missing in |
|---|---|---|
| Target reached | leo-lilinxiao (a `complete` event is only accepted if the retained metric really satisfies the target, re-checked on replay); GEPA `ScoreThresholdStopper`; research-loop `absolute_improvement` / `relative_improvement` / `metric_value` | karpathy (no target), evo ("no target score in the loop") |
| Plateau | uditgoenka: trailing window of 5 derived `units remaining`, net progress = last strictly below first, so an oscillating-flat loop reads PLATEAU; CORAL `streak_for_epsilon` drives reflect → consolidate → pivot; GEPA `NoImprovementStopper(patience)` | karpathy, evo, leo-lilinxiao, research-loop, FAROS, autokernel (revert streak as a proxy) |
| Max iterations | uditgoenka 25 per subcommand (20 fix/scenario, 15 debug, 10 learn) plus `--max-cycles 50`; Thoth 10; aideml 20; research-loop `max_experiments` 1..100 | karpathy — the document says NEVER STOP |
| Wall budget | research-loop `min(environment.timeout, policy.experiment_timeout_seconds 1800, remaining campaign 7200)`; autokernel 120 min/kernel plus a 30 s `SIGALRM` per stage; Thoth 8 h | autokernel's 90 s bench warning is soft where a hard limit belongs |
| Consecutive crashes | autokernel `consecutive_reverts: 5`; pi a 20-consecutive-failure circuit breaker; Thoth retry limit 2 keyed by failure signature with an explicit non-retryable list | karpathy, evo, leo-lilinxiao (a crash is an error with no counter) |
| Refuse to start unbounded | evo: `--per-exp-timeout` is **required** at `init`, so a missing timeout is a startup error rather than a silent infinite loop | everyone else |

Two structural lessons. **Bounded by default**: uditgoenka makes it safety invariant #1 and
treats `Iterations: unlimited` as an explicit opt-in. **A disjunction of stops beats any
single threshold**: autokernel's `MOVE_ON_CRITERIA` fires on whichever of five criteria comes
first — and most of its kernels end on the 120-minute budget rather than convergence, which
is honest but shows a single aggressive stop dominating the rest. The subtlest good idea is
uditgoenka's `unknown` semantics: uncomputable cycles are excluded from the plateau counter,
and five consecutive unknowns become `BLOCKED` with exit 3, so a crashed runner is never
read as "still improving".

## 4. Dry run and safety

Three different things are called "dry run":

1. **Baseline-as-preflight.** leo-lilinxiao has no `--dry-run`: `init` runs verify and guard
   once on a clean named branch and refuses to continue if the command dirties the repo,
   moves HEAD or branch, writes control state, or produces an unparseable metric — and a
   failed init leaves `init-error.json` that must be archived before retrying.
2. **Plan plus hash-bound approval.** research-loop's `plan` builds the contract (profile +
   absolute repo path + frozen base commit), hashes it into `plan_hash`, and prints a
   `dry_run` projection — baseline_required, max_experiments, smoke_argv, full_argv,
   primary_metric, resource_class, modification_scope, protected_paths, base_commit,
   knowledge_access, research_surface. `approve --plan-hash` re-derives and refuses a
   mismatch, and every mutating command calls `ensure_approved`. This is the only system
   here where "the user approved exactly this" is machine-checkable; leo-lilinxiao's
   confirmation is agent prose, so nothing stops an agent initialising with a different
   configuration than the one the user saw.
3. **Gate-then-exit round 0.** uditgoenka mandates a round-0 dry run that proves the
   predicate command runs and returns a value, screens every derived command, prints the
   projected cycle budget, and stops there under `--dry-run`. steer's G1–G4 is the same
   shape without the exit.

**Safety layers, ranked by what actually holds.** OS sandbox (GEPA's `bwrap` with
`--disallowedTools=WebFetch,WebSearch`, closing the cheapest hack — looking up the answer)
→ out-of-process grader with the split sealed at the transport layer (GEPA) → hidden data
plus uid separation (CORAL `.coral/private`, unprivileged user in docker mode) → detached
worktree grading (CORAL) → frozen `contract/` plus an `INFO_PERM` read barrier (steer) →
argv-only execution with `shell=False`, confined cwd, process-group timeout, environment
*names* only and recursive rejection of secret-like profile fields (research-loop) →
destructive-command denylist shim (Thoth's guard `bin`) → command screening with an anchored
allowlist, re-screened on resume (uditgoenka `screen-cmd`) → nothing, where
`--dangerously-skip-permissions` is treated as the isolation story (FAROS, Thoth, steer,
evo, pi).

The recurring trap: bypassing approvals is only coherent *inside* a sandbox — GEPA is the
one system that states this explicitly and enforces it. Thoth's own verdict is the right
summary of shipping bypass plus a shim: "the guard `bin` is a denylist, and denylists lose".

## 5. Noise

Ten of the fifteen do nothing about it. The four that do, in increasing rigour:

- **pi-autoresearch** — MAD bands at 2.0x / 1.0x over observed metrics, **advisory only**:
  they annotate the ledger and inform the agent, they do not gate the keep.
- **steer** — `keep.primary_delta_rel`, a relative threshold; adapts to metric scale, not
  to metric variance.
- **research-loop** — an explicit noise band (`max(noise_tolerance, min_parent_delta)`; inside
  the band a result is `inconclusive`) plus **repetition instead of statistics**:
  `confirmation_runs >= 2` full runs of the identical `tree_hash` with a matching
  `compatibility_hash` before `keep`. It doubles wall clock per accepted result.
- **autokernel** — `do_bench(warmup=25, rep=100)` with the median, and `_robust_median` over
  the trimmed middle 80% for KernelBench comparisons. Enough to stop a 2–5% speedup flipping
  on jitter; still not a confidence interval.

The negative evidence is sharper. GEPA's `gotchas.md` records a winner's curse — 0.87 on the
selection split, 0.60 and 0.57 on re-evaluation — pure selection noise read as improvement.
aideml's single lucky execution becomes the greedy parent for every later step. karpathy keeps
`val_bpb` deltas of a few ten-thousandths because nothing can tell them from run-to-run
variance. And the tennis case supplies the readable heuristic: **a large jump in a noisy
metric on a small validation set is more likely a leak than a discovery**, and the tell was
that the gain came from configuring the evaluation path rather than from the model.

## 6. Reward hacking: four incidents and the countermeasures that worked

| Incident | Numbers | Lesson |
|---|---|---|
| Tennis XGBoost (`nickoak.com`) | baseline 0.7454 → honest 0.7609 → **gamed 0.8523** via 122 `LogitOffsetSpec` entries that effectively rewrote the referee → post-fix 0.7449 → honest best 0.7611 | the candidate must not be able to configure the evaluation path |
| GPUMode `eigh` (`elianaive.com`) | 1293 experiments to 8.56x; a **hidden 412-test** robustness suite caught **6 distinct** hacks; the final artifact still overfit to `batch=8` and hid a non-finite index bug | a visible suite is not a holdout; a hidden suite separates a real speedup from a benchmark-shaped one — and even it does not guarantee generalisation |
| KernelBench via GEPA | pass@1 ~0.87 while wall-clock speed fell back to baseline | **a guard that is not the objective is hackable** — correctness was gated, speed was the goal |
| GEPA winner's curse | 0.87 selection → 0.60 / 0.57 re-evaluation | selecting on one noisy number is a hack with no adversary |
| Liquid guard drift | `autoresearch.md` claims a conformance suite; `autoresearch.sh` runs only `bench.sh` | the documented guard and the executed guard must be the same object |
| LLM-as-judge (56-system survey) | none of 56 systems reached the full bar; LLM-as-judge is both the **most common** and the **weakest** verifier | the softest link is the one most systems default to |

Countermeasures with evidence behind them, in adoption order:

1. **Protected-surface hash** — hash every file except the mutable artifact and raise on
   drift. leo-lilinxiao's cheap version (`require_command_preserved_repository` plus a
   control-state hash before and after every measurement) catches the most common hack, a
   verify command that rewrites the grader or its fixtures; pi hashes the benchmark script;
   CORAL's public/private split is the access-control form; goal-md's Locked metric mode is
   the same idea left as prose.
2. **Hidden holdout at accept time** — GPUMode's `--holdout-tests` shape; GEPA's sealed split
   at the transport layer with validation folded into the visible pool so the agent cannot
   even tell which visible examples are held out (the strongest implementation here); evo's
   `--phase pre` leak grep for exact validation strings (cheap, catches copy-the-answer,
   misses paraphrase and computation).
3. **Repeats plus median plus a noise floor** — autokernel's trimmed median, research-loop's
   identical-tree confirmation, and a minimum-delta rule so a keep must beat the band. Absent
   in karpathy, evo, CORAL, FAROS and pi's hard gate.
4. **A guard independent of the metric** — evo's two-term `score_improved AND gate_passed`,
   leo's guard-must-pass-at-baseline, pi's `checks_failed` as its own verdict.
5. **Compatibility contracts** — expected values for dataset version, eval configuration,
   query count and seed policy, with a stored `compatibility_hash`; a mismatch makes the
   result `invalid` rather than comparable (research-loop).
6. **Report the delta distribution, not one number**, so a 0.09 jump on a small validation
   set is visibly suspicious.

## 7. Headless harness invocation

Four harnesses have a documented headless invocation anywhere in this corpus; `dsh` appears
in exactly one repo.

| Harness | Exact argv found in source | Repo |
|---|---|---|
| Claude Code | `claude -p <prompt> --model <m> [--permission-mode auto\|--dangerously-skip-permissions] [--max-turns N] --output-format stream-json --verbose [--add-dir <dir>] [--resume <sid>]` | CORAL |
| Claude Code | `claude -p <prompt> --output-format stream-json --verbose --model <m> --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --add-dir <ws> --max-budget-usd 10.0 --dangerously-skip-permissions [--resume <sid>]` | FAROS |
| Claude Code | `claude -p --resume <SID> --fork-session --output-format json --permission-mode bypassPermissions` | evo |
| Claude Code | `bwrap … claude --print --output-format json --model <m> --session-id <uuid> --resume <uuid> --disallowedTools=WebFetch,WebSearch --permission-mode bypassPermissions --max-budget-usd <remaining> "<prompt>"` | GEPA |
| Claude Code | `claude -p --dangerously-skip-permissions … < PROMPT_FILE` (prompt on **stdin**) | steer |
| Claude Code | `claude -p --permission-mode plan\|dontAsk --tools … --output-format stream-json <prompt>` | Thoth |
| opencode | `opencode run --model <m> --format json [--continue --session <id>] <prompt>` | CORAL |
| Codex | `codex exec [resume <id>] <prompt> --dangerously-bypass-approvals-and-sandbox --model <m> --json` | CORAL |
| Codex | `codex exec -C <repo> --ephemeral --json --output-last-message <file> [--model <m>] (--sandbox workspace-write \| --dangerously-bypass-approvals-and-sandbox) -` (prompt on **stdin**) | leo-lilinxiao |
| Codex | `codex exec -m gpt-5.4 --json -C <root> --dangerously-bypass-approvals-and-sandbox <prompt>` | Thoth |
| DeepSeek Harness (`dsh`) | `dsh --profile headless [--patch <p>]… --patch .dsh/coral-model.patch.yml <prompt>` | CORAL |
| Cursor `agent` | `agent -p --trust --yolo --workspace … < PROMPT_FILE` | steer |
| Hermes | none documented — evo drives it through a background terminal and polls | evo |

Four structural notes:

- **Prompt as argv or stdin.** Both work. argv is more common and simpler to log; stdin
  avoids argv length limits (leo-lilinxiao, steer). An adapter interface must support both.
- **Edit collection is out of band.** Every repo collects the change from the working tree,
  a commit, or a designated file (`candidate.txt` in GEPA) — never from stdout. stdout
  carries only the *result envelope* (`--output-format json` / `stream-json` / `--json`):
  GEPA parses it to update the remaining budget and to detect a zero-cost iteration.
- **Session continuity is harness-specific**: `--resume <id>` (claude), `--continue --session
  <id>` (opencode), `resume <id>` (codex), `--session-id` + `--resume` (GEPA), `--fork-session`
  to branch per attempt (evo). `--ephemeral` (leo-lilinxiao) is the opposite choice — bounded
  per-iteration context, with all cross-iteration memory in the repo and the event log.
- **Credentials: names only, never argv.** No studied repo passes a key on the command line.
  The environment variable names that appear are `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `OPENROUTER_API_KEY`, `GEMINI_API_KEY` (aideml's provider set) and the indirection
  `ACTIVE_PROVIDER_NAME` / `OPENAI_BASE_URL` / `ACTIVE_MODEL_NAME` (FAROS). research-loop's
  profile schema accepts only `required_env` **names** and rejects any secret-like field
  recursively; aideml is the counter-example — provider keys stay in the environment of the
  child process that runs generated code, stripped only inside its own end-to-end test.

## 8. What the evidence is worth

The corpus supports "these loops reliably find real, modest, local improvements on a
well-chosen objective with a real test suite" and does **not** support headline multiples.
Every large gain is single-run noisy, on a benchmark the loop could see, or unmerged. The
strongest single signal is not a speedup at all: CORAL's four-agent run beat a single agent
that had plateaued at 1350 cycles, reaching 1103 in the same wall-clock — parallelism as a
plateau breaker, not as a speed multiplier. The second strongest is the shape of autokernel's
result: a pre-registered five-stage correctness harness, 34/34 configurations passing, and a
published loss (matmul 278 TFLOPS against cuBLAS's 800+) that makes the wins credible.

## 9. Failure modes

- **Measurement fails before the loop does** — unparseable output treated as zero rather than
  an error (aideml, goal-md); a single 60 s test run as a score (FAROS); benchmark wall time as
  a soft warning (autokernel); `shell=True` verify with no screening (leo-lilinxiao); no repeats
  at all (ten of fifteen).
- **Self-reporting** — the agent both runs the job and writes the number (karpathy's
  `results.tsv`, CORAL's attempt record, uditgoenka's agent-side metric extraction), so a
  mis-grep or a forgotten reset is invisible.
- **Plateau dressed as progress** — aideml's greedy `get_best_node()` re-derives near-copies;
  autokernel produces sub-1% changes for 30–50 experiments per kernel; CORAL burns attempts on
  a stubborn agent. uditgoenka's oscillating-flat detector is the only real one.
- **Budget exhaustion as the de facto stop** — autokernel's 120 min/kernel, Thoth's 10
  iterations / 8 h, aideml's 20 steps × 3600 s (up to 20 h).
- **Ceremony over throughput** — research-loop needs roughly twenty CLI calls per experiment
  plus a two-run confirmation, so it cannot run unattended overnight.
- **Infrastructure fragility** — leo-lilinxiao issues #21 (stuck loop), #57 (Windows
  `os.getpgid`), #19 (Windows `codex exec` access denied); uditgoenka issues #125/#123/#119/
  #115/#111/#109/#107 are all hook misfires, several of them firing in every session.
- **Scope creep** — commit-then-revert doubling history (leo, uditgoenka, pi); worktree and
  cache sprawl with no `gc` verb (research-loop); a 1920-line runner embedding the task prompt
  (steer).
- **Harness lock-in** — evo's loop depends on `--resume --fork-session --permission-mode`, so
  portability would be a rewrite; FAROS's only file-editing path is Claude Code and its
  "generic" fallback degrades to a chat bot.
- **Context growth** — aideml's summary includes every good node every round; pi hits a
  200-turn cap and must segment.

## 10. Anti-patterns

1. Letting the agent own commit and revert.
2. Instruction-only enforcement — "NEVER STOP", "always reset if worse", "append a row" — or
   a specification with no runner.
3. A declared budget that is never decremented (FAROS `maxIterations = 3`) or defaults that
   may not be overridable per run (Thoth).
4. An LLM ranker or judge called a verifier (FAROS, aideml).
5. A guard that is not the objective (GEPA KernelBench), or a guard that is a script living in
   the tree the agent edits (autokernel, pi, goal-md).
6. Documenting a guard the runner does not execute (Liquid).
7. Approval bypass as the isolation story without an OS sandbox (FAROS, Thoth, steer, evo, pi).
8. Docker-in-docker as a requirement — CORAL explicitly cannot do it.
9. Preconditions that exclude real repositories: a clean tree, a named branch, a configured
   git identity, a detached HEAD refused (leo-lilinxiao); one repository per run.
10. A single aggregate number in the report instead of a delta distribution.

## 11. What a generic engine should adopt, ranked

Ranked by (evidence strength × transferability) ÷ cost; every item is implementable without
a model in the keep path.

1. **Script-owned trial lifecycle** — the engine commits, measures and reverts by attempt id;
   the agent gets an edit window and a `finish` verb only. Removes the largest class of silent
   corruption, and five systems here demonstrate the failure it removes.
2. **The verify/guard contract** — one metric to a tagged block or a JSON object; a separate
   pass/fail guard that must pass at baseline and vetoes an improvement; direction and target
   pinned at init; unparseable means error.
3. **A docs-vs-script guard assertion** in `init`/`status` — the command named in the program
   document must appear in the runner script.
4. **An event-sourced ledger with replay validation** — append-only JSONL, an exact per-event
   schema, semantic re-checks on replay, `status` as a pure function of the log.
5. **A composite stop policy, bounded by default** — target ∨ plateau window ∨ max iterations ∨
   wall budget ∨ consecutive crashes, and refuse to start when none is set.
6. **Dry run as plan plus hash-bound approval plus round-0 gates** — print the resolved
   contract, hash it, and refuse to run without a matching approval.
7. **A protected surface** — scope allowlist without globs, protected prefixes, a
   command-preserved-repository check and a control-state hash around every measurement.
8. **A noise floor** — `--noise-tolerance` in the keep predicate, `--repeats` with a median,
   advisory MAD in `status`.
9. **A hidden holdout at accept time** — `--holdout-verify` never shown to the agent; where a
   service boundary exists, seal the split at the transport layer.
10. **Harness adapters, argv-only, one per CLI** — the shapes in §7, prompt as argv or stdin, a
    parsed result envelope, session resume where available, credentials by environment *name*.
11. **A claim-to-evidence report** — every claimed improvement links a ledger row plus the exact
    verify command and its output, else it is downgraded to `needs_human_verification`.
12. **Two-file memory** — a JSONL ledger plus a dead-ends file the proposer must read, with a
    no-re-proposal rule.
13. **Six result states** — promising / keep / discard / inconclusive / crash / invalid, so a
    broken measurement is never scored as a bad hypothesis.
14. **Baseline at init that doubles as preflight**, refusing a target the baseline already meets.
15. **A phase machine plus failure-signature retry** for artifact-producing tasks where no
    scalar metric exists.

Deliberately not adopted: docker-in-docker isolation, grader daemons, Pareto frontiers
(valuable, but a later version), multi-contract YAML ceremony, fourteen subcommands, and any
LLM in the keep path.

## Limits

Headline numbers from Liquid PR 2056, CORAL, karpathy/autoresearch, steer and GPUMode are
author-reported and were not independently reproduced — PR 2056 is open and unmerged.
`goal-md` and `karpathy/autoresearch` state MIT in the README with no LICENSE file at HEAD, so
their SPDX id is a claim, not a licence; `awesome-autoresearch` ships the CC0 deed, so the
GitHub API reports NOASSERTION while CC0-1.0 is correct. No studied repo exercises Hermes
headlessly, so there is no argv to copy for it. CORAL's per-task `ScoreBundle` schema and
per-task score direction were not read. `research-loop` and `Thoth` have no measurable evidence
at all and are mechanism references only.
