# 11 — Worked Example Pipelines

## What

Four complete instantiations of the autoresearch contract, one per objective
shape, living under `contract/examples/`: `ex1-music-abc` (minimize a language-model
loss), `ex2-iris-knn` (maximize a classifier accuracy), `ex3-hotpath-speedup`
(minimize wall-clock time under an exact-output gate), and `ex4-llm-repo-speedup`
(the same wall-time-under-a-gate objective driven by a **live LLM agent** editing
a small software repo). A single self-contained `dashboard.html` visualizes the
ex1–ex3 progression ledgers.

## Why

- **The contract in `docs/02-autoresearch-contract.md` is stated; a worked run proves
  it runs.** Each example carries the whole contract — human policy, frozen evaluator,
  the one agent-edited file, a keep/discard ledger and the loop driver that produced
  it — so a reader can reproduce a real optimization trajectory, not a description of
  one.
- **One direction is not enough to test a loop.** A keep/discard rule can be right for
  a minimization and silently wrong for a maximization; a gate that measures a scalar
  can pass a candidate that a structural gate must reject. Three objectives on one
  contract expose those asymmetries.
- **The loop's own failure modes only appear when it runs.** A mutation that never
  fires, a crash that is discarded but not reset, a simplification blocked by strict
  improvement — none are visible from the template alone. Running the loop three times
  surfaced each and fixed it.

## How

### The instantiations

| # | Directory | Objective (direction) | Baseline → Best | Candidates (K/D/C) | Proves |
|---|---|---|---|---|---|
| 1 | `contract/examples/ex1-music-abc` | `val_bpb` ↓ (ABC sheet-music LM, procedural stand-in corpus per the transcript-corpus topic) | 3.765056 → **2.178535** (−42.1%) | 6 (4/2/0) | a text domain; the frozen evaluator; keep/discard/reset |
| 2 | `contract/examples/ex2-iris-knn` | `accuracy` **↑** (real seaborn-mirror iris, embedded byte-identical) | 0.933333 → **1.000000** | 7 (3/4/0) | direction inversion; the frozen-evaluator object-identity guard |
| 3 | `contract/examples/ex3-hotpath-speedup` | median seconds ↓ + exact-output gate (non-ML, 2,000,000-token workload) | 2.310 s → **0.275 s** (8.41×) | 11 (9/1/1) | an anti-Goodhart gate rejects a ≈10×-faster wrong answer |
| 4 | `contract/examples/ex4-llm-repo-speedup` | median seconds ↓ + exact-output gate (small repo, one edited file, **live LLM**) | inf (baseline 36.05 s = 7.2× budget) → **0.001811 s** | 5 (1/1/3) | the LIVE loop end to end: a model proposes real code edits; the suite + held-out gate score them; the budget binds |

### Anatomy of a faithful instance

Every example directory carries the same five artifacts, plus a README:

| File | Role | Mutable by the loop |
|---|---|---|
| `program.md` | human policy: run tag, CAN/CANNOT rules, the goal | no — authored once |
| `prepare.py` | **FROZEN** evaluator and workloads | no — importing, never redefining, is the contract |
| `train.py` | the candidate being optimized | **yes — the only edited file** |
| `loop_driver.py` | the mechanical loop: apply patch → commit → run → parse metric → keep or reset | no |
| `results.tsv` | the keep/discard ledger | vendored once as the record |

`loop_driver.py` applies each candidate as an ordered patch list against the current
kept state, commits it, runs the objective, parses the metric from the run log, and
either keeps (a strict improvement) or `git reset --hard HEAD~1`. On a discard the next
patch set chains from the last kept file, which is exactly the karpathy loop.

ex4 keeps this shape with a model in the mutation slot — `agent_driver.py` writing
`target/solution.py` — and is described below.

### Ledger shape

| Example | Ledger columns | Rows | keep / discard / crash |
|---|---|---|---|
| ex1-music-abc | `commit val_bpb seconds status description` (no header line) | 6 | 4 / 2 / 0 |
| ex2-iris-knn | `commit accuracy seconds status description` | 7 | 3 / 4 / 0 |
| ex3-hotpath-speedup | `commit median_seconds gate status description` | 11 | 9 / 1 / 1 |
| ex4-llm-repo-speedup | `commit median_seconds gate stop_reason status tokens description` | 6 | 1 / 1 / 3 (+ 1 baseline `timeout`) |

`results.tsv` is **runtime state, vendored here ONCE as the record of the worked
run.** It is not appended to in place: re-running `loop_driver.py` in a scratch clone
produces a fresh ledger, and its `seconds` column (a T2 statistical field — T2 =
statistical tier: values jitter between runs and never gate; see
`kb/concepts/better-cheaper-faster-metrics.md`) jitters between runs. Each example
README embeds the run's git history verbatim; the live scratch clones are gitignored
stage-1 scratch and are never cited.

### The frozen evaluator, three ways

- **ex1** imports `evaluate` from `prepare.py`; the baseline starts at a unigram
  add-alpha model and the loop moves to bigram interpolation and a lighter backoff.
- **ex2** imports `evaluate_accuracy` and states the rule in `program.md`:
  `loop_driver.py` asserts `train.evaluate_accuracy is prepare.evaluate_accuracy` and
  aborts with `CONTRACT VIOLATION` otherwise. Redefining the evaluator in `train.py`
  fails that identity check before any candidate runs.
- **ex3** goes further: `prepare.py` owns a frozen `EXPECTED_OUTPUT` reference, and the
  evaluator screens the `train.py` module source for the names `EXPECTED_OUTPUT` and
  `run_reference`, rejecting a candidate that reaches into the ground truth.

### The exact-output gate (ex3)

ex3's objective is wall-clock time, but a candidate's speed counts only after
`run(data)` equals the frozen reference dict-for-dict. The ledger's `gate` column is
`ok` or `invalid`; a gate failure is recorded as `crash` (invalid), never a keep. The
final ledger row is a labeled attack — aggregating only the first 10% of the document
— which is ≈10× faster than the incumbent (0.027475 s vs 0.274679 s) and rejected by
the gate.

### Dashboard

`contract/examples/dashboard.html` is one self-contained file (inline `RUNS` data, no
JavaScript dependencies) rendering the progression of all three ledgers, coloring
keep / discard / crash / best. It **hand-transcribes** the vendored ledger values into
its inline `RUNS` array — it does not read the `results.tsv` files at load time —
so `tests/unit/test_examples_replay.py` (AC-EXA-003) asserts the inline numbers equal
the vendored ledgers and fails on any drift.

### ex4 — the live LLM instantiation

ex4 keeps the three roles but puts a **live model** in the mutation slot. The
frozen side is `prepare.py` (workloads, metric, `TIME_BUDGET`) plus
`target/tests.py` (the stdlib correctness suite); the human policy is
`program.md`; the one agent-edited artifact is `target/solution.py` — a small
software repo's hot path (`run(items) -> dict`, five keys). `agent_driver.py` is
the loop: each round it builds a prompt from `program.md` + the current artifact
+ the ledger tail + the last run-log tail, asks an OpenAI-compatible
chat-completions endpoint for the **complete** new file in one fenced block,
commits it, runs the frozen evaluator under the budget, and keeps or
hard-resets. Three environment variables, **NAMES only** (never a value in a
tracked file): the base URL, the key and the model id.

`transcript.jsonl` records every exchange — the messages' sha256, the artifact
sent, the raw response, `finish_reason`, the token usage and the wall time — and
that record is what makes the run reproducible: `--replay transcript.jsonl`
re-applies the recorded responses in order **with no network at all**.

The gate is the same anti-Goodhart shape as ex3 (`target/tests.py` plus an
exact-output comparison against `prepare.reference(...)` on a held-out workload,
with a source screen that rejects any candidate naming the frozen oracle), and
the budget is a hard 5 s ceiling. The shipped baseline is quadratic, so its row
is a budget stop by construction.

## Verification

Run from the repo root, 2026-09-26.

```bash
ls contract/examples/
# README.md  dashboard.html  ex1-music-abc  ex2-iris-knn  ex3-hotpath-speedup

ls contract/examples/ex1-music-abc/
# README.md  loop_driver.py  prepare.py  program.md  results.tsv  train.py

wc -l contract/examples/ex*/results.tsv
#   6 contract/examples/ex1-music-abc/results.tsv
#   8 contract/examples/ex2-iris-knn/results.tsv
#  12 contract/examples/ex3-hotpath-speedup/results.tsv
#  26 total

(cd contract/examples/ex1-music-abc && python3 train.py 2>/dev/null | grep val_bpb)
# val_bpb:          2.178535

(cd contract/examples/ex2-iris-knn && python3 train.py 2>/dev/null | grep '^accuracy:')
# accuracy:         1.000000

(cd contract/examples/ex3-hotpath-speedup && python3 train.py 2>/dev/null | grep -E 'median_seconds|gate_ok')
# median_seconds: 0.291148   # representative run; timing jitters (~0.29 ±0.01)
# gate_ok: True

(cd contract/examples/ex2-iris-knn && python3 -c "import loop_driver; loop_driver.assert_frozen_evaluator()")
# contract ok: train.evaluate_accuracy is prepare.evaluate_accuracy (train=105 test=45 seed=23)

grep -c "dot" contract/examples/dashboard.html
# 7        (inline data + legend rendering present; 7,697 bytes)
```

The frozen-evaluator guard is falsifiable, verified directly:
redefining `evaluate_accuracy` in `train.py` and calling
`loop_driver.assert_frozen_evaluator()` prints
`CONTRACT VIOLATION: train.evaluate_accuracy is not prepare.evaluate_accuracy`; the
untouched `train.py` prints
`contract ok: train.evaluate_accuracy is prepare.evaluate_accuracy (train=105 test=45 seed=23)`.

### Run 2026-10-16

Re-run after the examples gained their tracked `train_baseline.py` and the two replay
tiers (PRD 11). Commands from the repo root:

```bash
python3 -m pytest -q tests/unit/test_examples_replay.py
# 12 passed in 0.78s

python3 -m pytest -q tests/integration/test_examples_replay.py
# 2 passed in 88.44s (0:01:28)

(cd contract/examples/ex1-music-abc && python3 train.py 2>/dev/null | grep val_bpb)
# val_bpb:          2.178535

(cd contract/examples/ex2-iris-knn && python3 train.py 2>/dev/null | grep '^accuracy:')
# accuracy:         1.000000

(cd contract/examples/ex3-hotpath-speedup && python3 train.py 2>/dev/null | grep -E 'median_seconds|gate_ok')
# median_seconds: 0.296541   # representative run; timing jitters (~0.29 ±0.01)
# gate_ok: True
```

The endpoints reproduce (`2.178535` / `1.000000` / `gate_ok True`); ex3's
`median_seconds` is a fresh measurement, not the vendored `0.275`, because timing is T2.

**The ex3 replay is the one run the tiers do not compare row for row.** Its
keep/discard statuses are a T2 statistical field: two candidates sit within a few
percent of their incumbent (row 2, the `word_count` reuse, ≈3%; row 7, the `Counter`
counting step, ≈4%) and flip between keep and discard under load. A flipped keep is not
cosmetic — it diverges the patch cascade. The discarded row's file state survives, so a
later candidate that assumed its structural change raises inside `run()` (e.g. the
`re.findall` tokenize removing `clean` while `len(clean.split())` is still referenced);
the frozen gate records that extra crash as gate `invalid` (or `n/a` when it dies before
printing a verdict), the candidate is reset, and the final `attack:` anchor is left
dangling — `PATCH MISS`, driver exit 1, no attack row. The integration tier therefore
compares only what is deterministic: that the replay starts from the tracked baseline and
completes the baseline row, that the descriptions it produces are a prefix of the vendored
ledger, and that the final kept `train.py` — the vendored artifact when a flip diverged
the cascade, the replay's own HEAD otherwise — still passes the exact-output gate. It
never compares the `median_seconds`, `status` or `gate` columns.

### Run 2026-10-17 — ex4, the live LLM run

The one example whose candidates were proposed by a live model
(`opencode-go/kimi-k3`, `--max-tokens 12000`), 5 rounds at `TIME_BUDGET = 5` s.
`transcript.jsonl` holds every exchange, so the run replays offline. Commands from
the repo root:

```bash
python3 -m pytest -q tests/unit/test_examples_ex4.py
# 23 passed in 9.60s

mkdir -p "$TMPDIR/ex4"
git archive HEAD contract/examples/ex4-llm-repo-speedup | tar -x -C "$TMPDIR/ex4" --strip-components=3
cd "$TMPDIR/ex4" && git init -q && git add -A && git commit -qm "contract: baseline"
python3 agent_driver.py --from-baseline --replay transcript.jsonl
# replay: 5 recorded round(s) from transcript.jsonl (no network)
# --from-baseline: target/solution.py <- solution_baseline.py (HEAD 8c0cb0e)
# commit	median_seconds	gate	stop_reason	status	tokens	description
# 8c0cb0e            inf  gate=ok     budget      timeout tok  baseline (quadratic scan + per-value rescan; over budget by construction)
# WARNING: round 1 prompt sha256 differs from the recorded one (a67b7924e21f != 0227ff922293); prompts embed timing -- the recorded response is re-applied verbatim
# fcdc763       0.001695  gate=ok     done           keep tok  Replace quadratic scans with a single Counter pass, O(n) first-repeat via seen-set, and heapq.nsmall
# WARNING: round 2 prompt sha256 differs from the recorded one (96a37d73be39 != 32097634dc05); prompts embed timing -- the recorded response is re-applied verbatim
# fcdc763 unusable response (round 2)
# WARNING: round 3 prompt sha256 differs from the recorded one (ac0e1dafa99f != f6babd06036e); prompts embed timing -- the recorded response is re-applied verbatim
# fcdc763       0.001865  gate=ok     done        discard tok  Key-free nsmallest over pre-decorated (-count, value) tuples, fused pairs/groups loop with single ha
# WARNING: round 4 prompt sha256 differs from the recorded one (a2064d196960 != 14ac2ce224d1); prompts embed timing -- the recorded response is re-applied verbatim
# fcdc763 unusable response (round 4)
# WARNING: round 5 prompt sha256 differs from the recorded one (5cfd36554b72 != bde3dbaed926); prompts embed timing -- the recorded response is re-applied verbatim
# fcdc763 unusable response (round 5)
#
# rows: 6  keep=1 discard=1 timeout=1 crash=3
# best median: 0.001695s (budget 5s)
# HEAD: fcdc763 | candidate: round 1
```

The replay reproduces the vendored ledger's **deterministic columns** — `gate`,
`stop_reason`, `tokens`, `description` — row for row; commit hashes and
`median_seconds` differ, as with every example. The budget binds: the baseline
runs **36.05 s** uncapped = **7.2×** the 5 s ceiling, so its row is a budget stop
(`stop_reason: budget` / `status: timeout` / `median_seconds: inf`). The recorded
run is **1 keep / 1 discard / 3 unusable**: round 1's single-`Counter` rewrite was
kept (0.001811 s); round 3's second linear candidate (0.002029 s) did not beat the
incumbent and was discarded; **rounds 2, 4 and 5 returned empty content**
(`finish_reason: length`) — the model spent the entire token cap on hidden
reasoning before emitting a fenced block — and are recorded as unusable-response
crashes rather than smoothed away. Total cost: 53,563 tokens over 468.8 s of model
wall time. The replay also prints one `WARNING: round N prompt sha256 differs`
line per round: a prompt embeds the ledger and run-log tails, the log carries
`total_seconds`, so its sha256 can never be stable across runs — the warning is
soft and the recorded response is re-applied verbatim. The round-3 `discard` can
flip to a `keep` when the two linear candidates land inside the timing noise
(≈0.0017 s vs ≈0.0019 s); only the deterministic columns are claimed.

### Run 2026-10-17 — hardening after review

A spec review and a quality/security review of the ex4 harness found defects in
the **evaluator and driver only** — never in the recorded artifact — so they were
fixed without a model call. `results.tsv` and `transcript.jsonl` are untouched:
they remain the record of the 2026-10-17 live run, produced by the evaluator as it
stood then, and `target/solution.py` remains that run's kept artifact.

| Defect (pre-hardening) | Fix |
|---|---|
| **The verdict could be forged.** `run_evaluator` parsed `gate` / `median_seconds` / `stop_reason` from the child's stdout, and `_line_value` took the FIRST match — but the candidate shares that stdout. | the child writes its verdict as JSON to a file in a parent-created temp dir (atomic rename); the parent reads **only** that file, requires exit 0 for `gate: ok`, and treats a missing or contradictory verdict as a crash. stdout is a human log. |
| **A budget kill could be scored from stale lines.** The killed run's verdict was re-assembled by appending lines to the child's stdout and re-parsing it. | on timeout the parent sets the verdict itself: `median_seconds: inf`, `stop_reason: budget`, gate from the verdict file if the child got that far, else `n/a`. |
| **The kill only reached the direct child**, so a candidate's grandchildren survived as orphans. | `Popen(start_new_session=True)` and, on timeout, `os.killpg(SIGKILL)` followed by `communicate()` to reap. |
| **The child inherited the caller's API key.** | a minimal env — `PATH`, `PYTHONPATH`, `PYTHONHASHSEED`, `SYSTEMROOT` and a private `HOME` — plus `PYTHONDONTWRITEBYTECODE`; no `OPENAI_*` and no other secrets. |
| **The metric could be gamed by memoization.** `BENCH_REPS` timed the same `big` list three times. | each rep gets its own seeded workload of the same size (`SEED_BIG + rep`), median over reps. |
| **The driver could run inside the template checkout.** `git rev-parse --show-toplevel` resolved to the template root, so `git reset --hard` would revert the user's work and leave `candidate: round N` commits. | the driver refuses unless `git rev-parse --show-prefix` is empty (the example directory *is* the repo root), before any git write. |
| **The comment about the reset was false.** It claimed a hard reset would delete the untracked `results.tsv` / `transcript.jsonl`; a reset reverts *tracked* files, and both are gitignored runtime state in a scratch repo. | comment corrected; a LIVE run deletes the vendored `results.tsv` first (README + this doc), and the driver refuses a non-empty ledger for a live run. |
| **A bare `git commit` committed the whole index.** | `git commit --no-verify -q --allow-empty -m … -- target/solution.py` — path-limited. |
| **The baseline row's own reset undid `--from-baseline`.** Live round 1 in a fresh clone started from the FINAL artifact and `--replay` printed `note: round 1 artifact_sent != current artifact`. | the baseline is the incumbent by definition: it is never reset, even when it times out. |

The forgery was not hypothetical. Against the pre-hardening `prepare.py`
(`e2fe985`) a candidate whose whole body is `print` lines plus `sys.exit(0)`:

```bash
# prepare.py from e2fe985, candidate: three fake verdict lines, then sys.exit(0)
python3 prepare.py --run exit_zero.py
# gate: ok
# median_seconds: 0.000001
# stop_reason: done
# ... exit=0
```

…was scored `0.000001 s`, gate `ok`, and kept — no test had run. The hardened
evaluator gives that candidate no verdict file, hence gate `n/a`, `stop_reason:
error`, status `crash` (AC-EXA-019, which also covers the print-only forgery).

Under the hardened evaluator the same transcript still reproduces the ledger's
deterministic columns in a fresh scratch copy (the run quoted in § *Run
2026-10-17* above): `gate`, `stop_reason`, `tokens` and `description` equal the
vendored ledger row for row, the baseline still dies at the 5 s budget
(`timeout`), and the kept round-1 artifact still passes the gate inside the
budget (the check at the end of AC-EXA-018 runs `prepare.py --run
target/solution.py` on the replay's own HEAD).

New tests, all offline: `tests/unit/test_examples_ex4.py` — AC-EXA-019 (forged
verdict is not kept), AC-EXA-020 (a gate-passing run killed at the budget is a
`timeout`, never a keep), AC-EXA-021 (the process-group kill leaves no orphan
grandchild), AC-EXA-022 (no `OPENAI_API_KEY` in the child's environment),
AC-EXA-023 (the driver refuses a parent repo and leaves its HEAD and uncommitted
file untouched), AC-EXA-024 (a live run refuses a non-empty ledger), AC-EXA-025
(the benchmark seeds are fresh and parent-chosen), AC-EXA-026 (the README's ledger
table is byte-copied from `results.tsv`).

### Run 2026-10-17 — hardening after review, second pass

The first hardening above was itself incomplete, and the parent reproduced the
hole on the hardened evaluator: it **moved the verdict into a file instead of
removing the trust boundary**. The candidate is imported *inside* the child that
writes `verdict.json` and can read the path straight off `sys.argv`, so any
number it wrote there was still believed. Two candidates both scored `keep` with
median `1e-06`:

- **A2** — no `run()` at all: the file's whole body wrote
  `{"gate": "ok", "median": 1e-06, "stop_reason": "done"}` to the verdict path
  and called `os._exit(0)`;
- **A3** — the correct solution plus an `atexit` hook that overwrote the verdict
  file with median `1e-06`.

The fix removes the assumption rather than guarding the file: **within one
process there is no trust boundary, so the child is no longer asked to tell the
truth about itself.** It reports only the raw OUTPUTS of `run()` — one JSON
record per input — and the PARENT recomputes `reference(...)` and compares.

| Defect (first hardening) | Fix (second hardening) |
|---|---|
| **The verdict file was forgeable.** The candidate shares the child process and can rewrite the file the parent trusts (A2 wrote it with no `run()`; A3 overwrote it from `atexit`). | the child asserts no gate, no keep and no median: it reports the raw `run()` outputs; the parent recomputes `reference(...)` and compares. A missing/malformed output or any mismatch is a failed gate or a crash. |
| **`gate: ok` was a child-reported field.** It required exit 0, but a candidate controls its own exit code. | the parent-owned comparison *is* the gate. `target/tests.py` stays as a cheaper child-side first check (its failures still fail the candidate, but its passing is not trusted). |
| **The timed workloads had known seeds** (`SEED_BIG + rep`), so their answers could be precomputed at import. | the parent draws `BENCH_REPS` seeds with `secrets.randbits` and sends them over the child's stdin **after** the child reports it has imported the candidate; the child builds each workload with `prepare.generate_data`, and the parent verifies each bench output against `reference` on the seed it issued. |
| **A budget kill could lose the gate.** | the held-out outputs are reported BEFORE the timed reps, so the baseline's row still reads `gate: ok` / `stop_reason: budget` / `status: timeout`. |
| **The speed number is reported by the child and could be understated** by patching the clock. | accepted and documented: correctness is parent-verified, timing is not. The parent rejects only what its own measured bench-phase wall clock cannot have produced (`median * BENCH_REPS` above it, or `median <= 0`). |

Reproduced against `run_evaluator` + `status_for(verdict, 0.001811)` (the
vendored kept run's median), the honest artifact, and the baseline — all with
`tests/unit/test_examples_ex4.py`'s A2/A3/A append candidates:

```bash
python3 - <<'PY'
import importlib.util, sys
EX4 = "contract/examples/ex4-llm-repo-speedup"
spec = importlib.util.spec_from_file_location("p", EX4 + "/prepare.py")
prep = importlib.util.module_from_spec(spec); sys.dont_write_bytecode = True
spec.loader.exec_module(prep)
A2 = ('import sys, json, os\n'
      "p = sys.argv[sys.argv.index('--results')+1]\n"
      "json.dump({'gate':'ok','median':1e-06,'stop_reason':'done'}, open(p,'w'))\n"
      "os._exit(0)\n")
CORRECT = open(EX4 + "/target/solution.py").read()
A3 = CORRECT + ("\nimport atexit, json, sys\n"
                "def f():\n"
                " json.dump({'gate':'ok','median':1e-06,'stop_reason':'done'},"
                " open(sys.argv[sys.argv.index('--results')+1],'w'))\n"
                "atexit.register(f)\n")
for name, src in (("A2", A2), ("A3", A3)):
    open("/tmp/%s.py" % name, "w").write(src)
    v, _ = prep.run_evaluator("/tmp/%s.py" % name)
    print(name, "gate=%s stop=%s median=%s status=%s 1e-06? %s" % (
        v["gate"], v["stop_reason"], prep.format_median(v["median"]),
        prep.status_for(v, 0.001811), v["median"] == 1e-06))
PY
# A2 gate=n/a stop=error median=inf status=crash 1e-06? False
# A3 gate=n/a stop=error median=inf status=crash 1e-06? False

(cd contract/examples/ex4-llm-repo-speedup && python3 prepare.py --run \
  target/solution.py | tail -5)
# median_seconds: 0.010834
# gate: ok
# stop_reason: done
# time_budget: 5
# total_seconds: 0.181
```

The honest `target/solution.py` still evaluates to `gate: ok` / `done` (a keep
against the `inf` incumbent); the baseline is still `gate: ok` /
`stop_reason: budget` / `status: timeout`; and the offline replay in a fresh
scratch copy still reproduces the vendored ledger's deterministic columns
(`gate`, `stop_reason`, `tokens`, `description`) row for row, with no
`round 1 artifact_sent != current artifact` note.

New tests, all offline: AC-EXA-027 (a results-file forgery with no `run()` is not
kept), AC-EXA-028 (an `atexit` verdict overwrite is never the recorded median),
AC-EXA-029 (wrong outputs fail the gate however the child writes), AC-EXA-030
(fresh parent-chosen seeds defeat load-time precompute). AC-EXA-025 was rewritten
for the fresh-seed design.

### Run 2026-10-17 — third pass: parent-side timing

A re-review of the second pass found it still trusted the child for the **timing**.
Two attacks scored absurdly well against it:

- an **active load-time precompute** — forge the `imported`/`ready` handshakes,
  read the seed stream off the child's stdin and compute every rep's answer before
  the bench even starts — was scored `keep` at **0.000006 s**;
- a candidate that appended `bench` records claiming `seconds: 1e-9` (with the
  correct output) was recorded at a median of **0.0**.

Both are the same defect: the recorded number was one the candidate could choose.
The fix moves the clock to the parent. For each timed rep the parent draws one
fresh `secrets.randbits` seed, computes `reference(generate_data(seed))` for it
**before** it sends anything, writes only that seed to the child's stdin after the
child reports it is ready, and times the round trip with its own `perf_counter`
until the child's output record for that seed arrives. The protocol carries no
`seconds` field any more, so a forged one is ignored, and the recorded median is
the median of the **parent's** per-rep seconds.

**The metric changed, so the vendored medians are not comparable.** A parent-rep
now includes the child's `generate_data` workload build and the IPC — a constant
overhead — so an honest run measures **0.0107–0.0117 s** (the parent measured
0.010678 / 0.011116 / 0.011657 s on `target/solution.py`), not the **0.0018 s** the
vendored ledger records. The vendored `0.001811 s` keep and `0.002029 s` discard
were produced by the **pre-hardening** evaluator, which timed `run()` inside the
child; they are that run's record and stay as they are. Keep/discard is decided
against the incumbent **measured by the same evaluator in the same run**, so the
shift cancels — only the within-run comparison is read as signal.

Attack table, all re-run against `66b6f7c` (parent-side gate and timing):

| Attack | Result |
|---|---|
| print a fake verdict, `sys.exit(0)` | crash |
| forge the results channel with no `run()` | crash |
| return wrong-but-fast outputs | gate failed |
| active precompute that steals the stdin seeds (AC-EXA-030) | gate failed |
| `atexit`-append fake `bench` records, `seconds: 1e-9` (AC-EXA-031) | ignored; real median ≈0.0107 s |
| patch the clock inside the candidate | no effect; median ≈0.0109 s, gate ok |
| spawn a grandchild, then a clean `os._exit(0)` (AC-EXA-032) | killed — no orphan |
| flood the results channel with 50 MB (AC-EXA-033) | crash; parent max RSS 33 MB |
| `--run rel_sol.py` from another directory | works |
| `importlib.import_module('pre'+'pare')` oracle copy | passes with a real median |

The last row is the honest limit: the FORBIDDEN screen is a **best-effort
tripwire, not a security boundary** — a two-token bypass defeats it, and a copied
*correct* implementation is not a gate forgery (a genuinely correct output passing
the gate is the right answer). The real defence is the parent-side comparison: a
wrong output fails the gate whatever the source named. Under the new evaluator the
replay still reproduces the vendored ledger's deterministic columns row for row
(`gate`, `stop_reason`, `tokens`, `description`, plus `status` for the
baseline/crash rows and the first keep); its own medians are 0.010638 s (keep) and
0.010853 s (discard).

The parent also caps the results channel (8 MiB / 1000 records) and reads it with a
tracked offset rather than re-reading the whole file every poll; past the cap the
run is a crash, never a slow win. `--run` accepts a relative path from any
directory.

New tests, all offline: AC-EXA-030 (the ACTIVE precompute attack is not a fast
keep), AC-EXA-031 (an `atexit`-forged `seconds: 1e-9` is never the recorded
median), AC-EXA-032 (no orphan after a clean exit), AC-EXA-033 (a channel flood is
a crash).

## What Works

- **One contract, three objective shapes.** ex1 (lower-is-better `val_bpb`), ex2
  (higher-is-better `accuracy`) and ex3 (wall-time under a gate) each run the same
  `program.md` / `prepare.py` / `train.py` / `loop_driver.py` / `results.tsv` contract
  with only the direction and the gate changed.
- **The frozen evaluator is enforceable, not advisory.** ex2's object-identity
  assertion aborts the driver on a redefinition, and ex3's source screen rejects a
  candidate that names the ground-truth symbols — both fail before a metric is
  reported.
- **The exact-output gate defeats Goodharting.** ex3's attack candidate is ≈10× faster
  and is recorded as an invalid crash, so the incumbent (0.274679 s, the fastest
  *valid* row) keeps its place.
- **Direction inversion is real, not cosmetic.** ex2 maximizes accuracy while ex1/ex3
  minimize, and the loop's comparison, ledger and keep/reset rule hold against `>`
  exactly as against `<`.
- **A seed chosen to widen the headline delta is disclosed evaluator-input tuning, not a
  hidden win.** ex2's `prepare.py` records a seeds-0–39 scan and freezes seed 23. On the
  first candidate, seed 42, the 1-NN raw baseline already scores 0.977778 (= 44/45) and
  the K × metric × normalize × weighted grid still reaches 1.000000, so that split has
  headroom too — a one-test-row delta against seed 23's three. The seed was picked to
  enlarge the headline delta and the note names that as a Goodhart risk; see
  `ex2-iris-knn/prepare.py:204-217`.
- **The dashboard is portable.** `dashboard.html` carries its data inline and loads no
  external script, so it renders offline from the vendored ledgers.
- **Every documented run is reproducible from the tracked copy.** `python3 train.py` on
  each example prints the ledger's best metric — 2.178535 / 1.000000 / gate_ok True —
  from the shipped `train.py`.
- **A live model is a real mutation operator and the run still replays.** ex4's
  candidates came from a live model (`opencode-go/kimi-k3`), yet
  `--replay transcript.jsonl` reproduced the ledger's deterministic columns offline
  from the tracked baseline, so the three roles hold with a model in the loop.
- **The budget binds.** ex4's quadratic baseline is killed at `TIME_BUDGET` (its
  uncapped 36.05 s is 7.2× the 5 s ceiling), so the first ledger row is a real budget
  stop — a ceiling on a runaway candidate, not decoration.
- **A result the candidate cannot report is a result.** ex4's evaluator trusts
  nothing the child says about itself: the child reports only the raw `run()`
  outputs, and the parent recomputes `reference(...)` and compares — on a held-out
  workload plus benchmark workloads whose seeds the parent draws with `secrets`
  after the child's import handshake. A candidate that writes a verdict file (with
  no `run()` at all, or from an `atexit` hook) has no verified output and is a
  crash, and a workload precomputed at import is empty. The child also runs in its
  own process group with a scrubbed environment, so a budget kill takes its
  grandchildren down and no API key is reachable.

## What Fails

- **A mutation that never fires is indistinguishable from a failed candidate.** An
  anchor bug that patches the wrong site (ex1) leaves the metric identical to the
  incumbent, which a strict-improvement rule mechanically discards.
- **A crash that only discards leaves HEAD on the broken commit.** ex3's first driver
  reset on a discard but not on a crash, so the tree could end on the broken candidate.
- **Strict improvement rejects a simplification that costs nothing.** ex3's dead-code
  deletion (candidate 10) lost by 0.8% (0.276896 s vs 0.274679 s) and was discarded even
  though the code shrank.
- **A spot-check gate is not shape-proof.** ex3's attack candidate passed the first
  spot-check field and still failed the full-output comparison — a field-sample gate
  would have kept a badly wrong answer.
- **A widened headline delta is a metric choice, not a modelling gain.** ex2's seed 23
  was picked after a 0–39 scan because it makes the `0.933333 → 1.000000` delta three
  test rows wide, against one row on seed 42 — the delta is widened by the split, so the
  seed choice is recorded as evaluator-input tuning rather than read as a modelling win.
- **Timing columns are T2 and jitter between runs.** A wall-clock delta within ~10% is
  not signal, so a re-run of `results.tsv` never reproduces its `seconds` column exactly
  (ex3's fresh run measured 0.291 s against the vendored 0.275 s).
- **A reasoning model's hidden chain of thought can swallow the token cap.** ex4's
  rounds 2, 4 and 5 returned empty content (`finish_reason: length`) because the whole
  `--max-tokens` budget went into reasoning before any fenced block; an earlier attempt
  on a different reasoning model failed outright (a 2048-token cap fully consumed by
  reasoning, plus a provider stall) and was discarded as a driver-config problem, not
  read as a run result.
- **A verdict parsed from the child's stdout is forgeable.** ex4's first evaluator
  read `gate` / `median_seconds` / `stop_reason` from the stdout it shared with the
  candidate and took the first match, so an artifact that printed a fake verdict and
  called `sys.exit(0)` was scored 0.000001 s and **kept with no test run**; a budget
  kill also re-parsed that same stream to assemble its verdict, and the kill reached
  only the direct child.
- **A file the candidate can write is no safer than a line it can print.** ex4's
  second evaluator moved the verdict into a parent-created JSON file — but the
  candidate is imported inside the same process that writes it and can read the
  path straight off `sys.argv`, so a file with no `run()` at all (A2) and the
  correct file plus an `atexit` overwrite (A3) were both scored `keep` with median
  `1e-06`. A gate a process reports about itself is only as strong as the process
  boundary around it, and inside one process there is none.
- **The screen is a tripwire, not a boundary, and the artifact runs unsandboxed.**
  ex4's correctness and timing are parent-side, but the candidate is imported and
  run as arbitrary Python with the caller's privileges, so it can read files, spawn
  processes and consume the machine; and the source screen that rejects a candidate
  naming `prepare` is defeated by a two-token bypass
  (`importlib.import_module('pre'+'pare')`) — a copied *correct* implementation
  passes with a real median, because correct output is the right answer, not a
  forgery.

## Resolution

- Verify the patch site before trusting a result: the drivers abort on a
  `PATCH MISS`/`src.count(old) != 1` and an exact tie with the incumbent is read as a
  fired-patch bug, not a candidate outcome.
- Reset on any non-keep, crash included — the fix landed in ex3's driver, which runs
  `git reset --hard HEAD~1` when `status != "keep"`, so a broken candidate stays neither
  in the tree nor in history (the row survives in the ledger). ex1 and ex2 as shipped
  reset only on `discard` (`if status == "discard"`) and keep HEAD on a crashed
  candidate; their crashes never fire in the recorded runs (ex1 and ex2 ledgers have 0
  crash rows), so the difference is latent rather than observed.
- Apply a noise floor: keep if `metric <= incumbent*(1+eps)` **and** the code shrinks,
  so a simplification that is within the timing noise but deletes code is a win.
- Compare the whole output, not a field: the exact-output gate matches the reference
  dict-for-dict, which is what made ex3's fast-but-wrong candidate fail.
- Pre-register the split in the frozen evaluator and document the choice: scan seeds and
  freeze one (ex2 seed 23), recording the scan and the seed-42 split in `prepare.py` as
  evaluator-input tuning (a Goodhart risk) rather than as a headroom constraint.
- Never treat a sub-10% wall-clock delta as signal, and vendor `results.tsv` once: new
  measurements go to a scratch clone, and only the endpoints (not the timing column) are
  compared across runs.
- Give a reasoning model a large `--max-tokens` and record `finish_reason`: a truncated
  round then lands as an honest unusable-response crash (ex4 rounds 2/4/5) instead of a
  silent empty candidate, and a too-tight cap is diagnosed as configuration before it is
  read as a model outcome.
- Judge out of band: never parse the shared stdout, have a timeout SET the verdict
  (median `inf`, `stop_reason: budget`) instead of re-assembling one from what the
  candidate printed, and kill the child's whole process group with a scrubbed
  environment — a verdict is only as trustworthy as the process boundary around it.
- Don't let the child grade itself: a gate a process reports about itself is only as
  strong as the process boundary around it, and inside one process there is none — so
  the child asserts no verdict (it reports only the raw `run()` outputs), the parent
  recomputes `reference(...)` and compares them, and the benchmark seeds are drawn by
  the parent with `secrets` after the child's import handshake and sent over its stdin.
- Run a live loop only in a disposable sandbox/VM with no host mounts and no
  credentials beyond the endpoint key (the evaluated child does not inherit it
  either), and treat the source screen as an accidental-oracle tripwire rather than
  a security boundary: the defence is the parent-side output comparison, which fails
  a wrong output whatever the source said.

## Verdict

**works** — four faithful contract instantiations run end to end on four objective
shapes, three scripted and one driven by a live LLM agent (ex4, whose `--replay`
reproduces the deterministic ledger columns offline), each reproducible from its
tracked baseline, with the frozen-evaluator guard and the exact-output gate proven
falsifiable against a live redefinition and a labeled ~10×-faster attack. The ex4
harness was hardened three times afterwards — a verdict file with an exit-code
cross-check; then, after the parent reproduced a verdict-file forgery the first pass
still allowed, a parent-side comparison of the child's raw `run()` outputs on
parent-chosen fresh seeds; then, after a re-review showed the child still owned the
clock, parent-side per-rep timing on a fresh parent-chosen seed per rep — alongside
the process-group budget kill, the environment scrub and the in-repo guard, all
without touching the recorded run. The loop-mechanics
failures this doc records are the naive loop's — plus ex4's three
token-cap-truncated rounds, kept in the ledger as crashes — and each carries the
calibration rule that fixes it; no example's own run is left red.
