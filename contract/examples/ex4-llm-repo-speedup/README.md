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
see `target/README.md`). The gate is decided by the **parent**: the child reports
the raw `run()` outputs on a held-out workload the code never saw and on the
timed workloads, and the parent recomputes `prepare.reference(...)` and compares.
`target/tests.py` still runs in the child as a cheaper first check, and
`prepare.py` screens the source for imports of the frozen evaluator.

## The live run (2026-10-17)

Model `opencode-go/kimi-k3`, `--max-tokens 12000`, 5 rounds, `TIME_BUDGET = 5` s.
The run was driven by `agent_driver.py` (exit 0); the vendored `results.tsv` and
`transcript.jsonl` are its record and are never edited afterwards.

| commit | median s | gate | stop_reason | status | tokens | description |
|---|---|---|---|---|---|---|
| 591f5e4 | inf | ok | budget | timeout | 0 | baseline (quadratic scan + per-value rescan; over budget by construction) |
| 7affeed | 0.001811 | ok | done | keep | 4311 | Replace quadratic scans with a single Counter pass, O(n) first-repeat via seen-set, and heapq.nsmall |
| 9b37924 | inf | n/a | error | crash | 14087 | unusable response (no fenced code block) |
| e97294a | 0.002029 | ok | done | discard | 6904 | Key-free nsmallest over pre-decorated (-count, value) tuples, fused pairs/groups loop with single ha |
| 1233256 | inf | n/a | error | crash | 14152 | unusable response (no fenced code block) |
| e046af9 | inf | n/a | error | crash | 14109 | unusable response (no fenced code block) |

Every `description` cell is a **byte-copy of the ledger**, and the driver truncates
a description at 100 characters — so row 2 ends mid-word (`heapq.nsmall`) and row
4 ends mid-word (`single ha`). A crash row's `commit` is the candidate commit that
was discarded by the reset; it is in no branch's history, only in that row.

The `median s` values are that earlier evaluator's **child-side** timing of
`run()`; the current evaluator times each rep in the parent, so a fresh run
measures `0.0107–0.0117 s` and these numbers are **not comparable** with it —
keep/discard is decided against the incumbent measured by the same evaluator in the
same run.

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

`agent_driver.py` commits and hard-resets, so it **refuses to run unless the
example directory is the git root** — inside the template checkout it would reset
the template. Work in a disposable copy (from the repo root):

```bash
mkdir -p "$TMPDIR/ex4"
git archive HEAD contract/examples/ex4-llm-repo-speedup | tar -x -C "$TMPDIR/ex4" --strip-components=3
cd "$TMPDIR/ex4" && git init -q && git add -A && git commit -qm "contract: baseline"
python3 agent_driver.py --from-baseline --replay transcript.jsonl
```

`--from-baseline` restores the tracked `solution_baseline.py`; `--replay`
re-applies the recorded responses **with no network at all**. The replay
reproduces the ledger's **deterministic columns** row for row — `gate`,
`stop_reason`, `tokens` and `description`. It does **not** reproduce
`median_seconds` (a T2 statistical field that jitters) or the `status` column that
turns on it, except the budget-bound baseline row (`timeout`), whose kill at the
budget is deterministic. The round-3 discard can flip to a `keep` when the two
candidates land inside the timing noise (≈0.0017 s vs ≈0.0019 s); the deterministic
columns do not move, which is why `status` is not compared. Test:
`tests/unit/test_examples_ex4.py` (AC-EXA-018).

## Live mode

```bash
OPENAI_BASE_URL=http://127.0.0.1:4000/v1  # your OpenAI-compatible endpoint
OPENAI_API_KEY=... OPENAI_MODEL=opencode-go/kimi-k3 \
  python3 agent_driver.py --from-baseline --rounds 8
```

Three environment variables, **names only** (never a value in a tracked file):
the base URL, the key and the model id. A live run starts from an **empty**
ledger: delete the vendored `results.tsv` in the scratch copy first, or the
driver refuses (it will not append to the record).

**Safety.** Live mode executes **model-written Python unsandboxed, with your
privileges**. Run it in a disposable container/VM with no credentials beyond the
endpoint key and no host mounts. The evaluated child does not inherit that key
either: `prepare.py` passes it a minimal environment (PATH / PYTHONPATH /
PYTHONHASHSEED plus a private HOME), so a candidate that prints
`os.environ["OPENAI_API_KEY"]` sees nothing.

A reasoning model needs a large `--max-tokens` — too tight a cap is swallowed by
the hidden chain of thought and truncates to empty content, exactly as in rounds
2, 4 and 5 above; record `finish_reason` so a truncated round is visible rather
than silent.

## The harness cannot be talked into a keep (hardening, 2026-10-17)

The vendored ledger above was produced by the **pre-hardening** evaluator (it
read `gate` / `median_seconds` / `stop_reason` from the child's stdout, which the
candidate shares). It was hardened afterwards without re-running the live model;
`docs/11-worked-example-pipelines.md` records the audit and the replay evidence.

**The first hardening moved the verdict into a file — and the file was still
forgeable.** The candidate is imported *inside* the child that writes
`verdict.json`, and it can read the path straight off `sys.argv`, so within one
process there is no trust boundary. Two candidates both scored `keep` with median
`1e-06`: (A2) a file with no `run()` at all that wrote
`{"gate": "ok", "median": 1e-06, "stop_reason": "done"}` and called `os._exit(0)`;
(A3) the correct solution plus an `atexit` hook that overwrote the verdict file.
Any number a process reports about itself can be forged.

**So the parent decides the gate now.** The child asserts nothing. It reports, as
one JSON record per line in a path the parent creates, the raw outputs of
`run()` for the held-out workload and for each benchmark workload, and the parent
recomputes `reference(...)` itself and compares. Consequences:

- **The verdict is parent-owned.** No `gate`, `keep` or `median` travels from the
  child as a trusted field: the parent verifies every reported `run()` output
  against its own `reference(...)`, and a record the candidate writes (a fake
  `gate: ok`, a `1e-06`) is either ignored (an unrecognised stage) or, if it is an
  `output`, is compared like any other — where a wrong one only adds a mismatch.
  A2 and A3 therefore have no verified output and are a crash, never a keep.
- **The timing is parent-owned too, one rep at a time.** For each rep the parent
  draws a fresh `secrets.randbits` seed, computes `reference(generate_data(...))`
  for it **before** it sends anything, writes only that seed to the child's stdin,
  times the round trip with its own `perf_counter` until the child's output record
  for that seed arrives, and verifies the output against the reference it
  computed. The recorded median is the median of the **parent's** per-rep seconds;
  the metric is parent wall time per rep, including the child's workload
  generation and the IPC (a constant overhead, identical for every candidate).
  Because the seed for rep *k* does not exist until the parent sends it, a
  workload precomputed at import is impossible, and a patched clock inside the
  candidate changes nothing — the child's own `seconds` is not in the protocol at
  all.
- **The held-out outputs are reported before the timed reps**, so a run the
  budget kills mid-benchmark still carries a verifiable result: the baseline's
  row stays `gate: ok` / `stop_reason: budget` / `status: timeout`.
- **The child runs in its own process group with a scrubbed environment**, and a
  budget kill takes the whole group (no orphan grandchildren).
- The driver refuses a non-root repo (it would `git reset --hard` the template),
  refuses a non-empty ledger for a live run, and commits only the artifact; the
  baseline row is the incumbent, so it is never reset — round 1 starts from
  `solution_baseline.py`, which is what the transcript recorded.

**Residual risk, stated plainly.** Correctness and timing are both parent-side
and cannot be forged. What remains is the artifact itself: it is arbitrary Python
run **unsandboxed, with your privileges**, so it can read files, spawn processes
and consume the machine — run a live loop only in a disposable sandbox/VM with no
host mounts and no credentials beyond the endpoint key (which the evaluated child
does not inherit either). Timing is still a T2 field — a wall-clock delta within
~10% is not signal — so the ledger's keep/discard decisions must not be read as
precise.

**A best-effort screen, not a security boundary.** The source screen rejects a
candidate that names `prepare`, but a two-token bypass defeats it
(`importlib.import_module('pre'+'pare')`), and copying a correct implementation is
not a gate forgery anyway — the output is genuinely correct. The screen is an
accidental-oracle tripwire; the real defence is the parent-side comparison (a
wrong output is a failed gate whatever the source said), and the reason a live
loop belongs in a sandbox is that the artifact runs unsandboxed, not that the
screen can be trusted.
