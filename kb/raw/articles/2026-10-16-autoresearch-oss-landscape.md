---
source_url: https://github.com/karpathy/autoresearch
ingested: 2026-10-16
sha256: b2e62b710079851625b7eb38f65017e4edf2465474bad5d177cd950a53312438
kind: article
title: OSS autoresearch landscape — 19 MIT/Apache-2.0 implementations
---

# OSS autoresearch landscape — loop mechanics, harness portability, evaluator integrity

Synthesis of a one-day landscape study (2026-10-16) of open-source
implementations of the Karpathy autoresearch pattern, mined for ideas
adaptable to this template.

## Method

`gh search repos 'autoresearch*'` on 2026-10-16 returned **184** hits; **71**
carried an MIT or Apache-2.0 licence (verified per repo via the GitHub license
API — `repos/<owner>/<name> --jq .license.spdx_id`). **16** were pre-registered
for relevance in the study outline (loop mechanics, harness portability,
code/repo optimization, integrity, scaling); **19** were studied in full — three
low-star candidates surfaced during execution and were kept. Every repo was read
at a pinned `head_sha`; clones were read-only and **nothing was executed**
(licences permit study; no code was copied — see the licence note).
Field survey covered three-role split, budget enforcement, ledger semantics,
loop driver, harness neutrality, anti-Goodhart, parallelism and observability.

The 19 repos cluster: **A** harness-portable skills/plugins · **B** codebase /
software-optimization loops · **C** multi-agent / infra / observability ·
**D** evaluator integrity / meta-research · **E** end-to-end research agents.

## Evidence table (stars as of 2026-10-16; head sha abbreviated to 12)

| Repo | SPDX | head sha | stars | One-line | Key mechanism + file path |
|------|------|----------|-------|----------|---------------------------|
| SantanderAI/autoguardrails | Apache-2.0 | 1ca0c9b2c005 | 129 | Karpathy-style loop searching one mutable `policy.md` to minimise attack-success-rate against a frozen eval suite | `snapshot_fixed_surface()` sha256-hashes every file except `policy.md`/`results.tsv`, raises `SurfaceDriftError` — `autoguardrails/loop.py:246-320` |
| wanshuiyin/Anti-Autoresearch | MIT | fc6b32711539 | 164 | Reviewer-side integrity forensics: a deterministic span-anchored hashed evidence ledger is the only structure auditors read; LLM auditors only *propose*; a rules-only adjudicator decides | `tools/adjudicate_findings.py`, `build_claim_ledger.py`; `references/integrity-forensics-contract.md` |
| EdwardOptimization/Bilevel-Autoresearch | MIT | 2010e958028f | 208 | Bilevel loop: an inner loop optimises a task artifact; an outer loop optimises the inner loop (config first, then generated mechanisms via `importlib`) | `domains/train_opt/outer.py`; MAD noise floor in `mechanisms/adaptive_optics.py` |
| davebcn87/pi-autoresearch | MIT | 04b8a50dac7e | 8184 | `pi` terminal-agent extension turning it into a domain-agnostic experiment loop, with a MAD-based confidence score | `extensions/pi-autoresearch/index.ts` (`computeConfidence`, MAD); `.auto/log.jsonl` ledger |
| uditgoenka/autoresearch | MIT | 050e30dc4ba0 | 6575 | Multi-harness skill/plugin (Claude Code, Codex, OpenCode, any agent), 14 subcommands + an orchestrator over a deterministic shell seam | `.agents/skills/autoresearch/scripts/orchestrate.sh`; `scripts/transform.sh` (sed-emitted harness ports) |
| leo-lilinxiao/codex-autoresearch | MIT | 0f54c5717074 | 2931 | Codex skill + a strict stdlib Python control script owning measurement, commits, rollback and a validated append-only event history | `scripts/autoresearch_core.py` (`derive_state`, per-event validation); `autoresearch-results/events.jsonl` |
| TheGreenCedar/codex-autoresearch | Apache-2.0 | fbc07c5f8ea4 | 834 | Large Codex plugin: an ACCEPTED experiment contract is the sole evaluator, with a decision compiler, cumulative budgets and once-only ledger logging | `plugins/codex-autoresearch/lib/benchmark/budget-contract.ts`; `docs/investigations.md` |
| aiming-lab/AutoResearchClaw | MIT | be4ba4755bf1 | 14679 | 23-stage idea→paper pipeline with a HITL co-pilot, sandboxed edit-run-eval, multi-agent debate and an anti-fabrication registry | `researchclaw/experiment/harness_template.py` (injected, non-editable); `researchclaw/pipeline/verified_registry.py` |
| RUC-NLPIR/Arbor | Apache-2.0 | 7cdaf1fa6d77 | 1112 | Two-agent (Coordinator + Executor) controller growing a persistent hypothesis tree; merges into trunk only on a held-out test margin | `src/coordinator/tools/git_ops.py` (B_test merge gate); `src/coordinator/idea_tree.py` |
| stas4000/autoresearch-loop | MIT | 23ee272096ee | 0 | 73-line README pattern (no code): an overnight loop optimising one asset against one honest number, keep only clear wins | `README.md` (one change per round; the scorer is untouchable) |
| cyzlmh/autoresearch-loop | MIT | 5182057ebb59 | 1 | Dependency-free filesystem producer/consumer lab: the agent that proposes a hypothesis never decides whether it held | `lab/publish_task.py` (hash + atomic publish); `lab/experiment_validator.py` (the gate) |
| HacksterT/harvester | MIT | 36dd25c5edc1 | 0 | Self-improving code-maintenance service applying the loop to repos: a scanner files an issue, a label dispatches an overnight agent, a draft PR awaits review | `README.md` |
| evo-hq/evo | Apache-2.0 | c70c04b4d2da | 1472 | Harness-agnostic plugin + CLI: `discover` instruments a benchmark and gates; `optimize` runs an LLM tree-search over parallel worktree subagents | `plugins/evo/src/evo/core.py` (`compare_scores:1110`, `_finite_score:1101`); `cli.py` (`per-exp-timeout:2454`) |
| CyrusNuevoDia/gepa-research | Apache-2.0 | a7cd91d5c090 | 99 | Fork of evo that replaces the hand-written orchestrator with the GEPA library (reflection + Pareto search) | `plugins/gepa-research/src/gepa_research/gepa_adapter.py`; `core.py` |
| RightNow-AI/autokernel | MIT | 78435821cc3d | 1597 | Autoresearch for GPU kernels: extract bottleneck kernels, optimise each in a fixed ~90 s edit-bench-keep/revert loop | `bench.py` (`_Timeout`, SIGALRM); `orchestrate.py`; `results.tsv` (explicit 1% threshold) |
| smallnest/autoresearch | MIT | 3bb689826b9d | 571 | Fully-automated software-development loop: multiple LLM CLIs round-robin implement + cross-review an issue against hard (build/lint/test) and soft (≥85) gates | `run.sh`; `lib/scoring.sh`; `lib/agent_logic.sh` |
| Human-Agent-Society/CORAL | Apache-2.0 | 0123dfb939b3 | 1072 | Infrastructure for N coding-agent CLIs, each in its own worktree, sharing state and scored by a grader daemon | `coral/agent/registry.py`; `coral/template/coral_md.py` (`generate_coral_md`); `coral/grader/daemon.py` |
| iii-experimental/n-autoresearch | Apache-2.0 | 26f239c4f058 | 101 | The loop re-implemented as infrastructure on the iii Worker/Function/Trigger engine; the agent stays external and talks REST | `workers/orchestrator/orchestrator.py`; hard kill in `workers/gpu/src/functions/train.rs`; `prepare.py` `TIME_BUDGET=300` |
| jhochenbaum/pi-autoresearch-studio | MIT | 96920ee87261 | 156 | Control plane for the `pi` loop: a TUI + web dashboard over the JSONL ledger, a plan editor, and a cherry-pick PR workflow | `src/data/parser.ts`; `src/tui/dashboard.ts` (delegates the noise floor to davebcn87/pi-autoresearch) |

## Cross-repo patterns (what recurs, and where)

### (a) Deterministic keep gate / exit-code contract (0 keep · 1 discard · 2 invalid)

The transferable rule: the keep/discard decision is a **deterministic, LLM-free
function** with an explicit exit-code contract, not a judgment.
- **evo** — `evo run <id>` runs the registered benchmark and every inherited gate;
  it commits only if the score compares better **and** all gates exit 0, printing
  `COMMITTED | EVALUATED(score_regressed|gate_failed) | FAILED | GATE_FAILED |
  PRE_GATE_FAILED`. `compare_scores` is non-strict (ties commit); NaN/Inf rejected
  (`core.py`). Not a `0/1/2` exit-code triple — the taxonomy is the print vocabulary.
- **n-autoresearch orchestrator** — the `experiment::complete` function decides
  keep vs discard automatically (`improved = val_bpb < current best`) and returns
  `action='keep_commit' | 'git_reset'`; crash → `status='crash'`, `action='git_reset'`.
- **leo-lilinxiao** state machine — the control script is the sole evaluator and
  `derive_state` enforces the machine: a `keep` must strictly improve the metric
  AND have `guard='pass'` AND `revert_commit=null` AND `head=trial_commit`; a
  `discard` must point at its revert commit; `complete` only when target reached.
- **Arbor** merge margin — the merge tool runs the held-out `B_test` itself and
  rejects the merge unless `verified test_score >= trunk_score`; `merge_threshold`
  default 5.0 (min held-out % gain) is a soft guideline beside the tool-side check.

### (b) Budget enforced in code (not just prose)

- **n-autoresearch** — two layers: `prepare.py` defines `TIME_BUDGET=300`; `train.py`
  imports it and its loop `while True: … if step > 10 and total_training_time >=
  TIME_BUDGET: break` stops at exactly 5 wall-clock minutes. The Rust GPU worker
  wraps `uv run train.py` in `tokio::time::timeout(kill_timeout, …)` so an
  overrunning run is hard-killed to `status='timeout'` regardless of agent code
  (`workers/gpu/src/functions/train.rs:36-40`).
- **TheGreenCedar** — `lib/benchmark/budget-contract.ts` builds `BudgetStatus` from
  `packetBudget` + `wallClockBudgetSeconds`; `packetsUsed` counts only
  accepted-contract packets; on exhaustion it emits a `stopReason` + `nextAction`.
  Cumulative: "changing a hypothesis, repairing code, revising an evaluator, or
  restarting an agent does not reset accumulated costs".
- **autokernel** — fixed ~90 s per experiment, enforced in-band by `_Timeout`
  (SIGALRM, 30 s per correctness stage) plus a documented soft ceiling (kill if
  > 3 min), with orchestrator caps `max_minutes_per_kernel=120`,
  `speedup_target=2.0x`, `consecutive_reverts=5` (`bench.py`, `orchestrate.py`).

### (c) Noise floor / confidence

- **autokernel** — an explicit **1% threshold**: "Improved means at least 1% gain";
  noise-level changes are reverted unless the code is simpler; the metric is read
  from `run.log`, never the agent's self-report; `bench` uses `triton do_bench`
  warmup=25/rep=100 (median).
- **davebcn87/pi-autoresearch** — MAD-based confidence score =
  `|best_kept_metric − baseline| / MAD(all metric values in the current segment)`;
  needs ≥3 points, `null` when MAD=0; bands ≥2.0 green / 1.0–2.0 yellow / <1.0 red —
  **advisory only**, never auto-discards (`extensions/pi-autoresearch/index.ts:418-459`).
- **Bilevel-Autoresearch** — `AdaptiveOptics` estimates the measurement noise floor
  with the MAD of recent deltas, scales by 1.4826 to σ, floors it at 5e-4, and
  computes `SNR = |Δbpb|/noise_std`; SNR>2 CLEAR, 1–2 MARGINAL, <1 BELOW SEEING, and
  it injects a "make changes > 2σ" hint into the proposal prompt
  (`domains/train_opt/mechanisms/adaptive_optics.py`).
- **autoguardrails** — repeats the whole suite N times (default 2); `stable` requires
  exactly one distinct rounded `(asr, benign_pass)`; an unstable candidate is
  **discarded** (never "keep the lucky run"); `tie_tolerance 0.005`, and on a tie
  the candidate with lower `policy_complexity` is accepted (`loop.py:196-260`).

### (d) Protected-surface hashing (the evaluator cannot be silently edited)

- **autoguardrails** — `snapshot_fixed_surface()` sha256-hashes every file under
  root except `policy.md`/`results.tsv`, then `assert_protected_surface_unchanged()`
  compares against `.autoguardrails/protected_manifest.json` and raises
  `SurfaceDriftError` naming added/removed/changed paths (`loop.py:246-320`; tested by
  `tests/test_loop.py:81`).
- **cyzlmh** — the task bundle (`spec.md` + `task.json`: hypothesis, inputs,
  resource envelope, success gates) is hashed at publish time and moved by one
  atomic rename; the consumer can read but not change it, and the bundle is
  re-verified at seal time ("HARKing prevention as a mechanism instead of an
  instruction"). Sealing (`artifact_manifest.json`, SHA256 per canonical file) is
  done by the wrapper **outside** the executor and is idempotent (`lab/publish_task.py`,
  `lab/experiment_validator.py`).
- **AutoResearchClaw** — `harness_template.py` is injected into the sandbox at run
  time and its docstring states "This file is NOT editable by the LLM agent …
  inspired by karpathy/autoresearch's immutable prepare.py"; it owns the time
  budget (`should_stop()` at 80%), metric reporting and finalization.

### (e) Ledger validation

- **leo-lilinxiao** — `autoresearch-results/events.jsonl` is append-only and
  **strictly** validated: exact-key schema, matching `run_id`, an exact sequential
  `seq`, finite `Decimal` metrics (no NaN/Infinity, duplicate JSON keys rejected);
  `derive_state` then enforces the whole state machine, and "active history reached
  the target but lacks a complete event" is itself an error (there is no `crash`
  status — a failing command is an `error` terminal event).
- **uditgoenka** — results are a per-subcommand TSV
  (`iteration  commit  metric  delta  status  description`; status in
  `baseline | keep | discard`) and the `regression` subcommand emits a
  STABLE/UNSTABLE verdict via `scripts/score-regression.sh` (weighted dims, worst
  subscore, `STABLE iff stability_score >= 95`) with **exit 0 STABLE / 1 UNSTABLE /
  2 ERROR**. Its deterministic routing seam is "an explicit state JSON, validated
  before routing (`classify | next-hop | units | plateau | verdict | validate-state`)".

### (f) Harness portability

- **CORAL** — a runtime registry maps names/aliases to `AgentRuntime` classes
  (`coral/agent/registry.py`); each runtime declares its native shared-state dir;
  `CORAL.md` is **generated** with that dir substituted
  (`coral/template/coral_md.py:generate_coral_md(..., shared_dir=...)`) so paths are
  correct on any harness; the worktree symlinks the dir to `.coral/public`.
  Supported runtimes: claude_code, codex, dsh, cursor_agent, kiro, opencode, pi, and
  a custom `module.path:ClassName`.
- **Arbor** — the strongest of the cluster: in keyless mode Arbor **never calls an
  LLM**; the host agent's model drives the loop while Arbor contributes deterministic
  tools (Idea Tree, evaluation, worktree isolation, guarded merges, reports) over MCP.
  The same logic ships as 11 plain-Markdown skill directories, and `arbor install`
  auto-detects the harness (`--claude`/`--codex`/`--project`).
- **uditgoenka** — canonical source is `.claude/`; `scripts/transform.sh` emits harness
  ports with **sed rewrites** (`.claude/` → `.opencode/`, → `plugins/autoresearch/` +
  `.agents/skills/`, → `claude-plugin/`) and `AGENTS.md` is the portable entry
  document. The generated copies **drift** — a symlink (one source, N pointers) would
  not; this is the opposite of this repo's `.agents/`-canonical + symlink rule.

### (g) Correctness / held-out gates

- **evo** — gate commands (exit 0 pass, non-zero fail) are registered on nodes and
  inherited by descendants; a benchmark built from scratch **must** be paired with a
  real gate (mandatory); a 60/40 held-out validation slice adds a score-floor gate; a
  deterministic leak pre-gate greps for exact validation/gold strings; and
  `finetuning/references/false-progress.md` enumerates five non-improvement patterns
  (training on held-out, embedding eval items, reverse-engineering the verifier from
  failures, submitting an untrained checkpoint, optimising a different objective than
  scored).
- **Arbor** — the dev/held-out split is the central guardrail: executors iterate
  freely on `B_dev` but a change merges only if it clears a margin on `B_test`,
  verified by the tool; `path_guard.py` keeps the agent off private data;
  `contamination.py` adds a canary scan.
- **autoguardrails** — dual-metric acceptance: a candidate that refuses everything is
  rejected because `benign_pass` must not drop >2pp below the incumbent; the
  empty-policy baseline (`asr_unguarded`) is reported on every row so `policy_delta`
  is the honest effect size; and the frozen-suite lineage rule says "if you change
  `eval_suite.jsonl`, start a new experiment lineage instead of comparing against old
  results".

## Not adopted (scope creep)

- **AutoResearchClaw** — its 23-stage idea→paper pipeline, multi-agent debate and
  HITL co-pilot are an end-to-end research product; only its immutable-harness and
  VerifiedRegistry ideas transfer.
- **Arbor** — its product surface (UI interaction modes, session store, MLE/Kaggle
  plugins) is out of scope for a template; only the B_dev/B_test merge gate and the
  Markdown-skill portability transfer.
- **Multi-GPU / leased infra** — n-autoresearch's GPU leasing pool and the dual-4090
  reference are infrastructure, not doctrine.
- **Dashboards** — pi-autoresearch-studio, the evo/CORAL web+API surfaces and the
  `contract/examples/dashboard.html` hand-transcription pattern are presentation; a
  template's ledger is the TSV/JSONL, not its visualisation.

## Licence note

Every repo above is MIT or Apache-2.0 and was read read-only. **No code was
copied**: the ideas above are re-implementations of mechanisms, and MIT/Apache-2.0
attribution obligations apply only to copied source code, not to reimplemented
design ideas or to the facts recorded here. Where a mechanism is adopted, it is
reimplemented in this repo's own idiom under this repo's own licence.

## Open questions / limits

- The study is a single-day snapshot at pinned `head_sha`s; star counts and head
  SHAs move.
- Several "mechanisms" are documented-but-unverified in the upstream repos (e.g.
  Arbor's contamination LLM probe is a stub; evo's `verifyRepeats` confirm-loop is a
  log note). Treat them as design readings, not measured behaviour.
- The `0 keep / 1 discard / 2 invalid` triple is explicit in this template's own
  methodology registration and in uditgoenka's regression verdict; in evo and
  n-autoresearch it is a print/action vocabulary rather than a process exit code.
