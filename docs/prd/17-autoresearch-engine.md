# PRD 17 — Autoresearch Engine: a Generic, Harness-Pluggable Loop for Real Code

> Intent: turn this template from a *description* of the autoresearch loop into an
> **engine** that can be pointed at any git repository and improve real code under a
> script-owned keep/revert contract, driven by any of four agent harnesses (Hermes,
> Claude Code, opencode, DeepSeek Harness), with dry-run and real-run modes that are
> provable on this host.
> Grounded in: [autoresearch-engines-real-world](../../kb/comparisons/autoresearch-engines-real-world.md),
> [verify-guard-contract](../../kb/concepts/verify-guard-contract.md),
> [script-owned-keep-revert](../../kb/concepts/script-owned-keep-revert.md),
> [loop-stop-conditions](../../kb/concepts/loop-stop-conditions.md),
> [reward-hacking-countermeasures](../../kb/concepts/reward-hacking-countermeasures.md),
> [headless-harness-invocation](../../kb/concepts/headless-harness-invocation.md),
> [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md),
> raw source [raw/articles/2026-10-28-autoresearch-real-world-engines.md](../../kb/raw/articles/2026-10-28-autoresearch-real-world-engines.md).

## Context

**Problem (triage, 2026-10-28).** The template's loop worked as code but failed to
improve anything real. Root causes, observed in the tree at `afcab6c`:

1. **No engine.** `contract/` hard-wires one toy metric (`val_bpb` on a
   stdlib bigram); every worked example re-implements keep/discard in its own
   `loop_driver.py` / `agent_driver.py`. Nothing can be pointed at another repo.
2. **No harness drives an edit.** The only live example (ex4) posts raw HTTP to a
   chat-completions endpoint and pastes back a whole file; its recorded run was 1 keep,
   1 discard and 3 unusable rounds out of 5.
3. **No real-code target.** Every example is a synthetic workload written for the template.
4. **Ungrounded design.** The KB had never ingested the systems that *do* report
   real-code wins (pi-autoresearch on Shopify Liquid #2056: 53 % faster parse+render,
   974-test guard, ~120 experiments; CORAL kernel 1363→1103 cycles; autokernel RMSNorm
   5.29×) or their shared mechanics.

**What the research says works** (15 systems, kb comparison above): a *script* — not
the agent — owns commit, measurement and revert; a verify command prints the metric and
a guard must pass; edits are confined to a scope and the evaluator files are protected;
repeated measurement with a median and a noise floor; bounded stops (target, plateau,
iteration ceiling, wall budget); a dry-run round 0; an append-only, replay-validated
event log; and a report whose every claimed gain links to evidence (FAROS ReviewX).
Reward hacking is real (tennis referee rewrite 0.76→0.85 "gamed"; GPUMode eigh — six
hacks caught only by a hidden 412-test suite), so the guard must include a differential
oracle the agent cannot see or edit.

**Users.** (a) A developer who wants an overnight loop on their own repo with any of the
four harnesses; (b) a template adopter who needs a verified, documented starting point.

**Constraints.** Stdlib-only engine (no new runtime deps); no `shell=True`; every
subprocess bounded by a timeout; credentials reach the agent harness only — the
verify/guard child environment is scrubbed of secret-named variables; no secret value in
any tracked file (record variable NAMES only).

## Scope

In: `engine/` (package + wrapper + runbook), adapters for `claude`, `opencode`,
`hermes`, `dsh`, plus `command` and `replay`; a real-OSS worked example
`contract/examples/ex5-real-oss-speedup/`; live-run evidence for all four harnesses.
Out: multi-agent populations / worktree fan-out (CORAL), LLM-as-judge verifiers, paper
generation (FAROS/AI-Scientist scope), GPU workloads. The existing karpathy contract and
ex1–ex4 stay as they are (PRD-02 / PRD-11) — the engine is additive.

## Success Criteria

- **SC1 — One engine, any repo.** `autoresearch init` registers a run on any git repo
  from `--verify`, `--guard`, `--metric-name`, `--direction`, `--scope`, optional
  `--target`, `--noise-floor`, `--repeats`, `--protect`, `--program`, `--goal`; it refuses
  a dirty tree, a detached HEAD, a glob or missing scope, and an existing run without
  `--force` (which archives, and only after every argument validates).
  _Verify:_ `tests/unit/test_engine_config.py` (AC-ENG-040..045).
- **SC2 — The script owns keep/revert.** Each iteration: agent edit → changed paths →
  `no_change` | `scope_violation` | `protected_violation` | commit → guard (`guard_failed`)
  → verify × repeats, median (`crash` on failure) → `decide` → keep or revert. Every
  non-keep path reverts through one helper that restores the incumbent and removes the
  agent's untracked files, never touching `.autoresearch/`.
  _Verify:_ `tests/unit/test_engine_loop.py` (AC-ENG-050..059, 077..079).
- **SC3 — The evaluator decides, with a noise floor.** `decide` keeps only a strict
  improvement beyond a relative noise floor, using the incumbent's magnitude (correct for
  zero and negative metrics); the metric is parsed from `METRIC name=value`, `name: value`
  or a bare final float; verify/guard run with secret-named variables scrubbed.
  _Verify:_ `tests/unit/test_engine_decide.py` (AC-ENG-010..012),
  `tests/unit/test_engine_measure.py` (AC-ENG-001..005).
- **SC4 — Bounded by default.** Stops: `target`, `plateau` (K consecutive non-keeps),
  `max_iterations` (default 10), `max_wall`, `max_crashes`, `interrupted` (Ctrl-C,
  including during the baseline, records nothing half-written).
  _Verify:_ `tests/unit/test_engine_loop.py` (AC-ENG-050..059).
- **SC5 — Append-only, replay-validated ledger.** `events.jsonl` is fsync'd per event;
  `status` replays it and exits 3 on any violation (illegal keep, non-monotonic seq,
  unknown outcome, misplaced stop); a resumed run supersedes its stop with a `resume`
  event rather than corrupting the ledger.
  _Verify:_ `tests/unit/test_engine_ledger.py` (AC-ENG-020..025).
- **SC6 — Dry-run and real-run flags.** `run --dry-run` validates config, git state,
  protected hashes and the adapter binary, runs guard + verify at HEAD, prints the exact
  adapter argv (prompt elided) and the planned stops — and commits nothing, writes no
  event, never calls the agent. A real run with a missing adapter binary exits 2 before
  any baseline is written.
  _Verify:_ `tests/integration/test_engine_loop.py` (AC-ENG-201..203),
  `tests/unit/test_engine_loop.py` (AC-ENG-050..059).
- **SC7 — Four harnesses, exact argv.** Adapters build the headless invocation for
  `claude -p`, `opencode run --dir`, `hermes chat -q … -Q --yolo --in`, and
  `dsh --profile headless`; `command` and `replay` adapters exist for scripting and
  offline reproduction (`--record` makes a live run replayable).
  _Verify:_ `tests/unit/test_engine_adapters.py` (AC-ENG-030..033).
- **SC8 — The agent learns from the loop.** The prompt carries the program, goal, metric
  state, scope, protected files, the one-change/no-git/`CHANGE:` rules, the last 8 trials,
  dead ends, and the tail (≤ 40 lines) of the last failure.
  _Verify:_ `tests/unit/test_engine_prompt.py` (AC-ENG-070..076).
- **SC9 — Evidence-linked report.** `report` writes markdown whose EVIDENCE section gives,
  for every keep, the commit, the metric and a reproduce command, plus `results.tsv`.
  _Verify:_ `tests/unit/test_engine_report.py` (AC-ENG-060..064).
- **SC10 — A real-OSS target with an unforgeable guard.** ex5 vendors NLTK 3.9.1
  `nltk/metrics/distance.py` verbatim (Apache-2.0, pinned commit) as the only editable
  scope; `bench.py` (verify) and `guard.py` are protected. The guard has four stages —
  policy, upstream cases, differential oracle against a pristine copy, public surface —
  and the candidate only ever runs in an isolated child process, so it cannot exit the
  guard early or patch the oracle; the bench times cold child processes, so import-time
  precomputation is charged. Behaviour-changing mutants and each known bypass fail.
  _Verify:_ `tests/unit/test_examples_ex5.py` (AC-EXA-040..050).
- **SC11 — Proven on four harnesses.** A live ex5 run with each of `hermes`, `claude`,
  `opencode` and `dsh` completes under the engine with a valid ledger and a final guard
  pass; the measured outcome (keeps, best metric, % change — or the honest absence of a
  gain) is recorded with its commands.
  _Verify:_ `docs/17-autoresearch-engine.md` (*Verification*: per-harness run commands and
  ledgers) — empirical, not a CI test; harness credentials are host state.

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| metric parsing priority, scrubbed env, median of repeats | `tests/unit/test_engine_measure.py` | AC-ENG-001..005 |
| keep only beyond the noise floor; zero and negative incumbents | `tests/unit/test_engine_decide.py` | AC-ENG-010..012 |
| ledger validation, resume segments, tamper → exit 3 | `tests/unit/test_engine_ledger.py` | AC-ENG-020..025 |
| exact argv for claude/opencode/hermes/dsh/command; replay | `tests/unit/test_engine_adapters.py` | AC-ENG-030..033 |
| init preconditions, protected hashes, `--force` validates before archiving | `tests/unit/test_engine_config.py` | AC-ENG-040..045 |
| iteration outcomes, unified revert, stops, dry-run, Ctrl-C, missing binary | `tests/unit/test_engine_loop.py` | AC-ENG-050..059, 077..079 |
| report EVIDENCE + results.tsv; status summary | `tests/unit/test_engine_report.py` | AC-ENG-060..064 |
| prompt contents incl. failure tail | `tests/unit/test_engine_prompt.py` | AC-ENG-070..076 |
| end-to-end init→run→status→report; record→replay; dry-run; missing binary | `tests/integration/test_engine_loop.py` | AC-ENG-201..203 |
| ex5 guard passes pristine, fails mutants and the SystemExit / monkeypatch / surface-deletion attacks; bench charges import; tree stays clean with bytecode on | `tests/unit/test_examples_ex5.py` | AC-EXA-040..050 |
| four-harness live ex5 runs | `docs/17-autoresearch-engine.md` (empirical) | — |

## CI/CD Gate

The engine's unit tests run in the existing `unit` job and its end-to-end test in the
`integration` job (`.github/workflows/ci.yml`); no new job is needed because the engine is
stdlib-only. CI also runs on pull requests into `uat` (the Delivery stage's UAT branch).
Live harness runs (SC11) are **not** a CI gate — they need host credentials; they are a
sub4 UAT smoke step recorded in `docs/17`.

## Assumptions

- [ASSUMPTION] Parallel live runs on one 28-core host perturb a ~0.6 s CPU benchmark by
  less than the 2 % noise floor; docs/17 records the load at run time.
- The DeepSeek Harness reads its credential from `OPENAI_API_KEY`; on this host that value
  is exported only inside the run command, never written to a file.
- ex5's headroom is bounded (hand probes reached ≈1.9×); a plateau after a few keeps is the
  expected shape, not a defect.

## Confidence

**Medium-high.** The mechanics are grounded in 15 studied systems and tested here; the
real-code improvement claim rests on one target and a handful of iterations per harness.
