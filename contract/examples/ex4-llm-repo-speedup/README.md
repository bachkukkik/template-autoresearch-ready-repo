# Example 4 — ex4-llm-repo-speedup: a LIVE LLM agent speeds up a small repo

The contract instantiated as the template's main use case: an agent proposes
edits to **real software code**, scored by that code's frozen test suite plus a
speed metric, under a fixed `TIME_BUDGET` that genuinely stops a candidate.

**This is the one example whose candidates were proposed by a live LLM** — the
other three (`ex1-music-abc`, `ex2-iris-knn`, `ex3-hotpath-speedup`) are scripted
reference runs whose candidates come from a fixed list. Here the mutation slot is
a real model: each round `agent_driver.py` asks an OpenAI-compatible
chat-completions endpoint for the complete new `target/solution.py`, applies it,
commits it, runs the FROZEN evaluator and keeps or resets. Everything the model
returned is recorded in `transcript.jsonl`, so the run replays offline.

## The instance

| File | Role | Mutable by the loop |
|---|---|---|
| `program.md` | human policy: run tag, CAN/CANNOT rules, the goal | no — authored once |
| `prepare.py` | **FROZEN** evaluator, workloads and metric; owns `TIME_BUDGET` | no |
| `target/tests.py` | **FROZEN** correctness gate (stdlib, pytest-free) | no |
| `target/solution.py` | the candidate being optimized | **yes — the only edited file** |
| `solution_baseline.py` | the reconstructed baseline the run started from | no |
| `agent_driver.py` | the loop: prompt → apply → commit → evaluate → keep/reset | no |
| `results.tsv` | the keep/discard ledger, vendored once as the record | runtime state |
| `transcript.jsonl` | every recorded model exchange (the replay's input) | runtime state |

`target/solution.py` must implement `run(items: list[str]) -> dict` (five keys;
see `target/README.md`). The gate is `target/tests.py` **plus** an exact-output
comparison against `prepare.reference(...)` on a held-out workload the code never
saw, and `prepare.py` screens the source for references to the frozen oracle.

## The live run (2026-10-17)

Model `opencode-go/kimi-k3`, `--max-tokens 12000`, 5 rounds, `TIME_BUDGET = 5` s.
The run was driven by `agent_driver.py` (exit 0); the vendored `results.tsv` and
`transcript.jsonl` are its record and are never edited afterwards.

| commit | median s | gate | stop_reason | status | tokens | description |
|---|---|---|---|---|---|---|
| 591f5e4 | inf | ok | budget | timeout | 0 | baseline (quadratic scan + per-value rescan; over budget by construction) |
| 7affeed | 0.001811 | ok | done | keep | 4311 | Replace quadratic scans with a single Counter pass, O(n) first-repeat via seen-set, and heapq.nsmallest |
| 9b37924 | inf | n/a | error | crash | 14087 | unusable response (no fenced code block) |
| e97294a | 0.002029 | ok | done | discard | 6904 | Key-free nsmallest over pre-decorated (-count, value) tuples, fused pairs/groups loop with single pass |
| 1233256 | inf | n/a | error | crash | 14152 | unusable response (no fenced code block) |
| e046af9 | inf | n/a | error | crash | 14109 | unusable response (no fenced code block) |

**The budget binds.** The shipped baseline is quadratic; measured uncapped it
runs **36.05 s**, i.e. **7.2×** `TIME_BUDGET`, so its ledger row is a budget stop
(`stop_reason: budget`, `status: timeout`, `median_seconds: inf`) — not
decoration.

**Five rounds, 1 keep / 1 discard / 3 unusable.** Round 1 replaced the quadratic
scan with a single `Counter` pass and was kept (0.001811 s). Round 3 offered a
second linear candidate (0.002029 s) that did not beat the incumbent, so the
evaluator discarded it. Rounds 2, 4 and 5 returned **empty content**
(`finish_reason: length`): the model spent its entire token cap on hidden
reasoning before emitting a fenced block, so the response was unusable and
recorded as a crash. That is a real model failure, kept in the ledger rather than
smoothed away. Total model cost: **53,563 tokens** over **468.8 s** of wall time.

## Reproducing the ledger offline

`agent_driver.py` commits and hard-resets, so copy the example into a scratch git
repo first. `--from-baseline` restores the tracked baseline; `--replay` re-applies
the recorded responses **with no network at all**:

```bash
cp -r contract/examples/ex4-llm-repo-speedup /tmp/ex4 && cd /tmp/ex4
git init -q && git add -A && git commit -qm "contract: baseline"
python3 agent_driver.py --from-baseline --replay transcript.jsonl
```

The replay reproduces the ledger's **deterministic columns** row for row — `gate`,
`stop_reason`, `tokens` and `description`. It does **not** reproduce
`median_seconds` (a T2 statistical field that jitters) or the `status` column that
turns on it, except the budget-bound baseline row (`timeout`), whose kill at the
budget is deterministic. Test: `tests/unit/test_examples_ex4.py` (AC-EXA-018).

## Live mode

```bash
OPENAI_BASE_URL=http://127.0.0.1:4000/v1 OPENAI_API_KEY=... \
OPENAI_MODEL=opencode-go/kimi-k3 \
python3 agent_driver.py --from-baseline --rounds 8
```

Three environment variables, **names only** (never a value in a tracked file):
the base URL, the key and the model id. A reasoning model needs a large
`--max-tokens` — too tight a cap is swallowed by the hidden chain of thought and
truncates to empty content, exactly as in rounds 2, 4 and 5 above; record
`finish_reason` so a truncated round is visible rather than silent.
