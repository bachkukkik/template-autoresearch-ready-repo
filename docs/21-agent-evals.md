# 21 — Agent Evals

> **Numbering note.** Downstream numbering wins: this is the stage-6 record for
> **PRD 20** (*agent evals*), which is downstream's PRD/doc 20–21 pair. It
> records `autoresearch/engine/autoresearch/` only — the *referee* half of the
> downstream eval layer (A/A noise floor, drift canary, cheat probes, audit
> scoring, the `faster` leg) has no evaluator surface in this tree and is not
> ported. **Provenance:** ported from `vanilla-open-design-autoresearch`
> PRs #8, #13, #14 (the eval layer) and #29, #30 (salvage and the wall, owned by
> PRD 17); research capture
> `kb/raw/articles/2026-11-15-downstream-frontier-distillation.md`; intent
> [PRD 20](prd/20-agent-evals.md).

## What

The engine's evaluation layer: a measurement that reports the dispersion it
observed, a keep gated on a margin derived from that dispersion, a third verdict
(`inconclusive`) for a delta the margin cannot separate, and a six-field
provenance block on every adjudicated decision so a result survives a model
swap.

## Why

- **The pre-port rule was a bare fraction over one repeat.** `decide()` gated on
`|incumbent| × noise_floor` with `DEFAULT_REPEATS = 1`, so the recorded
dispersion was never observed and the gate was dormant while prose described
it as live: at `n = 1` the standard error is undefined, so 0.01 against a
proportion metric's SE of 0.038–0.05 banked jitter as progress.
- **A keep had two readings where it needed three.** A delta too small to
separate the runs was recorded `discard`, which claims a judgement nobody made
and spends a plateau slot on a coin flip.
- **Decisions were not reproducible.** No event recorded the model, the route,
the engine version, the scoring command or the profile content, so after a
model or evaluator change a keep could be neither re-run nor credited.
- **`measure()` threw away what it had just measured.** Repeats were reduced to
a bare median; the spread that would have made the median a measurement was
discarded.
- Intent: [PRD 20](prd/20-agent-evals.md) (SC-evl-1..6), on top of
[PRD 17](prd/17-autoresearch-engine.md). Grounding:
[deterministic-keep-gate](../kb/concepts/deterministic-keep-gate.md),
[better-cheaper-faster-metrics](../kb/concepts/better-cheaper-faster-metrics.md),
[loop-stop-conditions](../kb/concepts/loop-stop-conditions.md),
[run-record-contract](../kb/concepts/run-record-contract.md).
- **Scope.** This PRD tightens what a keep is allowed to mean; it changes no
other PRD-17 contract. Salvage (SC12) and the wall reservation (SC13) are
verified here because they share the loop, but they are PRD 17's.

## How

### Measurement — the dispersion is derived, never assigned

`measure()` runs the verify command `cfg.repeats` times and reduces the series
to a median. `Measurement.__post_init__` fills the dispersion from the values it
was given, so no caller can claim one.

| Field | Definition | Single repeat |
|---|---|---|
| `values` | every repeat's metric, in run order | 1 value |
| `repeats` | `len(values)` unless set | `1` |
| `spread` | `statistics.stdev(values)` (sample SD) | `null` — never a fabricated `0.0` |
| `honest` | `repeats >= 2 and value is not None` | `false` |
| `raw` | the evaluator's own line for the **median repeat** | that repeat's line |

`standard_error_of_difference(candidate, incumbent)` is the independent
two-sample SE of the difference of two **medians**:
`1.2533 × sqrt(s1²/n1 + s2²/n2)`, with `MEDIAN_CONSISTENCY = 1.2533`
(`sqrt(π/2)`) because the point estimates are medians, not means. It returns
`None` when either side is not honest — the gate is the repeat count, not the
`spread` field, so a hand-built measurement that reports repeats and no
dispersion is treated as *no observed dispersion* (variance 0) rather than as an
invitation to invent one.

`DEFAULT_REPEATS` is **3**, set where the decision is made, so the statistical
gate is live by default; `--repeats 1` remains available and remains honest.

### The decision — one margin, computed once, recorded with its inputs

| Call | Rule |
|---|---|
| `decide(candidate, incumbent, direction, floor)` | the pre-port rule, unchanged: relative floor `|incumbent| × floor`, absolute at `incumbent == 0` |
| `margin(candidate, incumbent, floor, mode=…)` | `max(floor, 1.96 × SE)` — `Z = 1.96`, the floor read as an absolute amount unless `mode="relative"` |
| `decide_with_margin(...)` | `keep` when `delta > margin`, `discard` when `delta < -margin`, `inconclusive` inside it |

`loop.py` computes the threshold **once** per trial (`mode="relative"`, so a
fractional profile keeps its pre-port meaning), passes it to
`decide_with_margin`, and records *that number* with the dispersion it came
from. `inconclusive` reverts through the same helper as a `discard`, never moves
the incumbent, and counts as a non-keep for the plateau stop. The incumbent's
`values` are re-read from the ledger, so its dispersion survives a resume.

A decided trial event carries:

| Field | Meaning |
|---|---|
| `repeats`, `spread`, `honest` | dispersion of the candidate measurement |
| `se` | the standard error of the difference; `null` when not computable |
| `margin` | the threshold the verdict used |
| `values`, `raw` | the series, and the evaluator's line for its median repeat |
| `agent_tokens`, `agent_api_calls` | JSON `null`, not `0` — no adapter reports them, and `0` would claim the agent was free |
| `provenance` | the six fields below, on `keep` and `discard` only |

### Provenance — six fields, built before the commit

| Field | Value |
|---|---|
| `model` | the operator's `--model`, or the adapter's default label (`command:default`) |
| `model_route` | the adapter's binary/route (`python3`, `claude`, …) |
| `engine_version` | `autoresearch.__version__` (`0.2.0` at this record) |
| `referee_version` | `verify:` + the first 12 hex of sha256 of the verify command — the engine's referee *is* that command |
| `profile_sha256` | sha256 of the `run.json` content, so a run cannot claim a profile it did not use |
| `timestamp` | ISO-8601 UTC, second resolution (`[0-9]{4}-…Z`) |

The block is built **before** the candidate is committed, so a block that cannot
be built aborts on a clean tree (AC-EVL-006). `model`, `model_route` and the
`--model` flag are **refused, never scrubbed**, when they embed URL userinfo —
`scheme://userinfo@host` with or without a colon, per RFC 3986 — because the
ledger is append-only: a secret written there could only be rotated. An empty
identifier or a field over 512 characters is refused for the same reason.

`status --require-provenance` is the read-side gate: exit 3 naming each
offending `seq` when a decision has no block, a block is missing a field, or the
timestamp / profile digest is not canonical. Without the flag the same ledger
still replays, so a run written before provenance existed is not invalidated by
the new claim.

### Replay — the recorded margin is re-checked

`ledger.validate()` replays every keep through `decide()` with the recorded
floor (unchanged, AC-ENG-020..025) and then applies the margin rule to the
events that record one:

- keep with **no** `margin` — every pre-PRD-20 event — replays by the legacy
floor rule alone; `margin >= floor` by construction, so an old keep is never
retro-invalidated;
- keep whose `margin` is non-numeric, NaN, infinite or negative is a violation
(`margin` is an amount of improvement; NaN compares false against everything);
- keep whose `delta` does not exceed its recorded `margin` is a violation — a
fabricated *implausibly large* margin does not validate;
- an `inconclusive` trial replays as a non-keep that never moves the incumbent.

### Stated divergences from the downstream engine

| Area | Downstream | Here | Why |
|---|---|---|---|
| Wall reservation | `agent_timeout + ITERATION_TAIL` with `ITERATION_TAIL = 120` | `agent_timeout + guard_timeout + repeats × verify_timeout` (3300 s at the defaults), checked at the loop top **and** the stop reason | the tail under-reserves a repeats × timeout verify; the arithmetic is exact and downstream parity is not required |
| Salvage marker | `salvaged: true` on a dead keep *and* on a dead rejection | `salvaged: true` on a `keep` only; a dead rejection keeps its own outcome (`agent_error`, `scope_violation`) and its `agent_exit_code` | a reverted tree banked nothing — calling it salvaged would overstate the round |
| `raw` field | — | the evaluator's line of the **median repeat** (`median_index`), never an averaged number | an even-count median is a number no run printed; the pairing is stated, not claimed |

### The verification fixture

The live runs below point the engine at a throwaway checkout of this shape — the
same shape `tests/integration/test_eval_loop_stats.py` and
`tests/integration/test_objective_record_replay.py` build:

```python
# score.py — the verify. Value is read from src/value.txt; a counter OUTSIDE the
# checkout gives three repeats a deterministic ±1 jitter, so spread == 1.0.
import os, pathlib
base = float(pathlib.Path("src/value.txt").read_text().strip())
counter = pathlib.Path(os.environ["NOISE_PATH"])
raw = counter.read_text().strip() if counter.exists() else ""
n = int(raw) if raw else 0
counter.write_text(str(n + 1))
print(f"METRIC value={base + (0.0, -1.0, 1.0)[n % 3]}")
```

```python
# agent.py — the scripted proposer behind `--agent command`. argv: repo plan step exit
import json, pathlib, sys
repo, plan, step_file = pathlib.Path(sys.argv[1]), json.loads(pathlib.Path(sys.argv[2]).read_text()), pathlib.Path(sys.argv[3])
exit_code = int(sys.argv[4]) if len(sys.argv) > 4 else 0
step = int(step_file.read_text()) if step_file.exists() else 0
step_file.write_text(str(step + 1))
target = repo / "src" / "value.txt"
if step < len(plan):
    target.write_text(f"{float(target.read_text().strip()) + plan[step]}\n")
    print(f"CHANGE: move value by {plan[step]}")
sys.exit(exit_code)
```

The guard is `float(value) > 0` (a candidate that breaks the number has no
business scoring). Every run below is therefore model-free, network-free and
stdlib-only, exactly like the tests — which is also this record's largest limit.

### Test map

| File | ACs | Tests |
|---|---|---|
| `tests/unit/test_eval_statistics.py` | AC-EVL-001..004 | 30 |
| `tests/unit/test_eval_provenance.py` | AC-EVL-006, AC-EVL-007 | 36 |
| `tests/unit/test_engine_ledger.py` | AC-EVL-005 (+ AC-ENG-020..025) | 19 |
| `tests/unit/test_engine_loop.py` | AC-ENG-050..059, 082..082e, 083..083d | 42 |
| `tests/integration/test_eval_loop_stats.py` | AC-EVL-202 | 2 |
| `tests/integration/test_objective_record_replay.py` | AC-OBJ-201, AC-REC-201 | 2 |

## Verification

### Run 2026-11-16 (tiers) — this tree @ `bf33243`

```console
$ python3 -m pytest tests/unit -q
584 passed, 1 warning in 69.78s (0:01:09)

$ python3 -m pytest tests/unit/test_eval_statistics.py tests/unit/test_eval_provenance.py \
      tests/unit/test_engine_ledger.py -q
85 passed in 3.43s

$ python3 -m pytest tests/unit/test_engine_loop.py -q
42 passed in 13.02s

$ python3 -m pytest tests/integration/test_eval_loop_stats.py -q
2 passed in 2.39s

$ python3 -m pytest tests/integration/test_objective_record_replay.py -q
2 passed in 2.36s

$ bash tests/run.sh
==> Tier 1/3: unit … 584 passed
==> Tier 2/3: integration … 45 passed in 119.75s (0:01:59)
==> Tier 3/3: e2e
SKIPPED (needs a running service — re-run with --with-e2e)
RESULT: PASSED
```

The single warning is the ambient `starlette`/`anyio` deprecation in the service
tier's client, not this layer. The e2e tier was not run (see *What Fails*).

### Run 2026-11-16 (one live three-repeat run — the core record) — this tree @ `bf33243`

Three repeats, `--noise-floor 0.01`, a plan of two candidates: −2 (an
improvement of 2) and −4. The checkout's floor is `10 × 0.01 = 0.1`; the
measured SE is `1.2533 × sqrt(1/3 + 1/3) = 1.0233`, so the margin is
`1.96 × 1.0233 = 2.0057`.

```console
$ python3 -P -m autoresearch init --repo . --verify "python3 score.py" \
    --guard "python3 guard.py" --metric-name value --direction lower --scope src \
    --protect score.py --protect guard.py --repeats 3 --noise-floor 0.01
initialised run in <WORK>/run-a
  verify : python3 score.py
  guard  : python3 guard.py
  metric : value (lower is better)
  scope  : src
  protect: guard.py, score.py
  config : <WORK>/run-a/.autoresearch/run.json

$ python3 -P -m autoresearch run --repo . --agent command \
    --agent-cmd "python3 {repo}/agent.py {repo} <WORK>/plan.json <WORK>/step" \
    --max-iterations 2
baseline: 10.0 (commit 607aae2)
iter 1: inconclusive metric=8 commit=c5a368c — move value by -2
iter 2: keep metric=6 commit=98b1269 — move value by -4
stop: max_iterations after 2 iteration(s) (incumbent 6.0 at 98b1269)

$ python3 -P -m autoresearch status --repo .
run value (lower is better): baseline 10 -> best 6 (+40.00%), 2 iteration(s), stop max_iterations
ledger: valid

$ python3 -P -m autoresearch status --repo . --require-provenance
run value (lower is better): baseline 10 -> best 6 (+40.00%), 2 iteration(s), stop max_iterations
ledger: valid                                                          (exit 0)
```

The two trial events, verbatim except for the paths (the keep is the whole
event):

```json
{"seq": 2, "iteration": 1, "outcome": "inconclusive", "metric": 8.0,
 "repeats": 3, "spread": 1.0, "honest": true,
 "se": 1.0233151648767191, "margin": 2.0056977231583697,
 "values": [8.0, 7.0, 9.0], "raw": "METRIC value=8.0",
 "agent_tokens": null, "agent_api_calls": null, "provenance": null}

{"seq": 3, "iteration": 2, "outcome": "keep", "metric": 6.0, "commit": "98b1269…",
 "guard": "pass", "direction": "lower", "noise_floor": 0.01,
 "repeats": 3, "spread": 1.0, "honest": true,
 "se": 1.0233151648767191, "margin": 2.0056977231583697,
 "values": [6.0, 5.0, 7.0], "raw": "METRIC value=6.0",
 "agent_tokens": null, "agent_api_calls": null,
 "provenance": {"model": "command:default", "model_route": "python3",
                "engine_version": "0.2.0", "referee_version": "verify:dbc4238619ee",
                "profile_sha256": "42e45b88…(64 hex)", "timestamp": "2026-11-16T09:11:51Z"}}
```

A 2.0 improvement cleared the old 0.1 floor and did **not** clear 2.0057: it is
`inconclusive`, its commit is not the incumbent, and the tree is back at 10
before iteration 2 runs. The 4.0 improvement is a keep. `report` renders both
files from the ledger — `results.tsv` and `report.md` are its output, not the
run's — so the third outcome is a first-class row in each, not a discard:

```console
$ python3 -P -m autoresearch report --repo .
<WORK>/run-a/.autoresearch/report.md

$ cat .autoresearch/results.tsv
iter	commit	metric	outcome	description
0	607aae232948…	10	baseline	baseline
1	c5a368c6fd8f…	8	inconclusive	move value by -2
2	98b1269c90d3…	6	keep	move value by -4

$ grep outcomes .autoresearch/report.md
- outcomes: inconclusive=1, keep=1
```

### Run 2026-11-16 (one repeat stays honest) — this tree @ `bf33243`

The same fixture at `--repeats 1` — the claim is that the old rule survives
unchanged *and* says so:

```console
$ python3 -P -m autoresearch init --repo . … --repeats 1 --noise-floor 0.01
$ python3 -P -m autoresearch run --repo . --agent command … --max-iterations 1
iter 1: keep metric=5 commit=7b40f68 — move value by -4
{"outcome": "keep", "metric": 5.0, "repeats": 1, "spread": null, "honest": false,
 "se": null, "margin": 0.1, "values": [5.0]}
```

`margin` is the 0.1 relative floor, `se` is `null` (not `0.0`), `spread` is
`null` (not a fabricated zero), and the keep is exactly what the pre-port rule
would have recorded.

### Run 2026-11-16 (salvage, the wall, the state dir) — this tree @ `bf33243`

**Salvage — a dead agent's tree is still a candidate.** The proposer applies −4
and exits 3:

```console
$ python3 -P -m autoresearch run --repo . --agent command \
    --agent-cmd "python3 {repo}/agent.py {repo} <WORK>/plan.json <WORK>/step 3" --max-iterations 1
iter 1: keep metric=6 commit=8930704 — move value by -4
{"outcome": "keep", "metric": 6.0, "agent_exit_code": 3, "salvaged": true, "values": [6.0, 5.0, 7.0]}
```

**Salvage is not a licence to keep.** The same death with a *worse* tree (+4):

```console
iter 1: agent_error metric=14 commit=4875cf3 — move value by 4
{"outcome": "agent_error", "metric": 14.0, "agent_exit_code": 3, "values": [14.0, 13.0, 15.0]}
$ cat src/value.txt
10                       # reverted; HEAD unchanged at 53e6610; no "salvaged" key in the event
```

A dead candidate is measured and judged on the same margin, but only one verdict
survives the death: a `keep` banks its tree (`salvaged: true`), and **every**
rejection is `agent_error` with the measured `metric` and `values` intact —
including one whose improvement sits *inside* the margin. `inconclusive` never
appears for a dead candidate: the third verdict is a judgement about a live
candidate, and an event that claimed it would bury the death under a verdict
nobody delivered.

**The wall funds a whole iteration or starts none.**

```console
$ python3 -P -m autoresearch run --repo . --agent command … --max-wall 2000 --max-iterations 1
autoresearch: error: --max-wall 2000s cannot fund even 1 iteration: one reserves 3300s
(agent timeout 900s + guard 600s + 3 repeats × verify 600s) — the smallest usable
wall is 3301s; pass --max-wall 0 for unlimited                               (exit 2)
$ ls .autoresearch/events.jsonl
ls: cannot access '.autoresearch/events.jsonl': No such file or directory

$ python3 -P -m autoresearch run --repo . --agent command … --max-wall 3600 --max-iterations 1
baseline: 10.0 (commit 24f85d7)
iter 1: keep metric=6 commit=2322c3d — move value by -4
stop: max_iterations after 1 iteration(s) (incumbent 6.0 at 2322c3d)         (exit 0)
```

The refusal is preflight: no baseline, no event, no held lock. The lock file
itself is left behind, unheld and 0 bytes — released, never unlinked — so the
next command can take it. The shipped `/ar-run` default of 3600 s funds one
iteration at the default timeouts.

**The state dir keeps every byte out of the measured checkout.**

```console
$ python3 -P -m autoresearch init --repo . --state-dir <WORK>/harness-d/state …
  config : <WORK>/harness-d/state/run.json
$ ls -a <WORK>/run-d | grep -c '.autoresearch'
0
$ git status --porcelain          # (empty)
$ ls -a <WORK>/harness-d/state
.gitignore  run.json

$ python3 -P -m autoresearch status --repo .
autoresearch: error: no run configured under .autoresearch/run.json — run `autoresearch init` first   (exit 2)

$ python3 -P -m autoresearch status --repo . --state-dir <WORK>/harness-d/state
run value (lower is better): baseline - -> best - (n/a), 0 iteration(s), stop incomplete
ledger: valid                                                                 (exit 0)
```

A later command is **told** where the state is; it never guesses from the
checkout. (AC-TPR-203 covers the same property from the profile plan.)

### Run 2026-11-16 (legacy equivalence, brute force) — this tree @ `bf33243`

Two bounded sweeps, both run by the tracked `scripts/legacy_grid.py`: it imports
the shipped `decide()` and `decide_with_margin()` rather than a copy, fixes its
domain in the module docstring, and exits 1 when an invariant breaks — so the
figures below are one command's output, not a remembered count. The first sweep
is the one-repeat grid, the configuration where the margin collapses to the
floor and the two rules must agree exactly:

```console
$ python3 scripts/legacy_grid.py
domain                 : 16 values x 16 values x 2 directions, floor mode=relative
one-repeat grid        : 3584 points (256 pairs x 2 directions x 7 floors)
  legacy keeps         : 1671
  margin-gated keeps   : 1671
  keeps the margin added: 0
  keeps the margin lost : 0
honest pair sweep      : 13824 points (256 pairs x 3 x 3 spreads x 2 directions x 3 floors)
  legacy keeps         : 6480
  margin-gated keeps   : 5610
  keeps the margin added: 0
  keeps the margin lost : 870
inside the floor       : 242 (121 per direction: 224 exact ties + 18 non-zero delta) — all inconclusive
invariants             : grid added=0 PASS, grid lost=0 PASS, honest added=0 PASS       (exit 0)
```

The 242 inside-floor points are the band where the *only* behavioural difference
lives: 224 are exact ties and 18 carry a non-zero delta still inside the
relative floor. The legacy rule called all of them `discard`; the margin calls
them `inconclusive`; nothing is banked either way.

The second sweep gives both sides a real dispersion (two repeats, spreads
`{0, 1, 3}`), which is where the rules are allowed to differ: the SE the margin
adds can only widen it from the floor, so 870 keeps the legacy rule would have
banked are refused. That direction is the safety property, not a defect — a
narrower legacy keep is the failure the layer exists to prevent.

No point in either sweep produced a keep under the margin that the legacy rule
would have refused. The margin is never more permissive; at multiple repeats it
is strictly stricter, which is the whole claim of SC-evl-2.

### Run 2026-11-16 (pre-port ledger replay and the provenance gate) — this tree @ `bf33243`

A hand-written ledger in the pre-PRD-20 shape — no `margin`, no `provenance`,
one repeat implied — replayed through the real `status`:

```console
$ python3 -P -m autoresearch status --repo .
run value (lower is better): baseline 10 -> best 8 (+20.00%), 2 iteration(s), stop max_iterations
ledger: valid                                                                 (exit 0)

$ python3 -P -m autoresearch status --repo . --require-provenance
ledger: INVALID (2 violation(s))
  - seq 2: keep decision has no provenance block
  - seq 3: discard decision has no provenance block                          (exit 3)
```

The same ledger with a **fabricated margin larger than the delta** is rejected:

```console
$ # the keep's delta is 2.0 and the event records "margin": 2.5
ledger: INVALID (1 violation(s))
  - seq 2: keep's improvement 2 does not exceed its recorded margin 2.5       (exit 3)
```

And the hole that remains — a **fabricated margin smaller than the true one**
(`"margin": 1.0` where three repeats would derive 2.0057):

```console
ledger: valid                                                                 (exit 0)
```

Replay checks that the delta exceeds the *recorded* number; it does not
recompute that number from the recorded `values`/`se`/`floor`. See *What Fails*.

### Run 2026-11-16 (credentials never reach the ledger) — this tree @ `bf33243`

```console
$ python3 -P -m autoresearch run --repo . --agent command … \
    --model 'https://user:<redacted>@gateway.example/v1'
autoresearch: error: --model embeds credentials — pass the model name, not a URL with userinfo
                                                                             (exit 2)
$ ls .autoresearch/events.jsonl
ls: cannot access '.autoresearch/events.jsonl': No such file or directory
$ grep -rl '<the token>' .autoresearch . --exclude-dir=.git
(no matches)
```

The refusal happens in preflight, before the lock, the baseline or the loop, so
nothing is written to a file that could only be rotated.

### Run 2026-11-16 (the objective record, and the close record on a real replay) — this tree @ `bf33243`

```console
$ python3 -P -m autoresearch objective validate --file <WORK>/bad-objective.json
objective record <WORK>/bad-objective.json is invalid (8 problem(s)):
  - leg 'value' of objective 'g0' has no direction/guard
  - weight 'ghost' of objective 'g0' names no declared leg
  - objective id 'g0' is declared 2 times
  - fork of 'absent-parent' into 'g0' has no reason
  - retired objective 'g0' has no reason
  - active objective 'g1' has no legs
  - 2 objectives are active ('g0', 'g1'); a run plays exactly one
  - objective 'g0' names parent 'absent-parent', which is no objective   (exit 1)

$ python3 -P -m autoresearch objective validate
objective record autoresearch/objective/registry.json: valid                    (exit 0)
$ python3 -P -m autoresearch objective resolve
--verify 'python3 train.py' --metric-name val_bpb --direction lower --repeats 3 \
--noise-floor 0.01 --guard 'python3 prepare.py'                                 (exit 0)
```

`validate` lists **every** problem in one pass (the all-problems contract), and
the shipped registry resolves to the `val_bpb` leg at `--repeats 3` — the same
default the engine sets, now stated in the intent layer too.

A `replay`-driven run of the same fixture, then the close record:

```console
$ python3 -P -m autoresearch run --repo . --agent replay --replay <WORK>/records.jsonl --max-iterations 1
baseline: 10.0 (commit b9b1f34)
iter 1: keep metric=6 commit=dad10db — lower value to 6

$ python3 -P -m autoresearch report --repo . --record
<WORK>/run-f/.autoresearch/record.json
$ python3 -P -m autoresearch report --repo . --check
record: byte-identical under <WORK>/run-f/.autoresearch                        (exit 0)

$ printf '\n' >> .autoresearch/record.md
$ python3 -P -m autoresearch report --repo . --check
autoresearch: error: record: <WORK>/run-f/.autoresearch/record.md differs from a
fresh render — the record drifted from the ledger                             (exit 2)
```

The record is derived from the ledger, not from prose, and it keeps the series
it reduced (`"values": [6.0, 5.0, 7.0]`) plus the evaluator's own line as `raw`.
Its *note* still quotes the configured floor rather than the applied margin —
see *What Fails*.

## What Works

- **Dispersion is reported, never fabricated.** `--repeats 3` records
`spread 1.0`, `honest true`, `se 1.0233`; `--repeats 1` records `spread null`,
`se null`, `honest false` rather than a made-up zero.
- **A delta inside the margin gets its own verdict.** The live run's 2.0
improvement clears the 0.1 floor and stays inside the 2.0057 margin: it is
recorded `inconclusive`, reverted, and counted as a non-keep — the incumbent
is still at iteration 2's starting value when iteration 2 begins.
- **A keep clears the margin and says what it cleared.** The keep event records
the median, the series, the SE, and the exact margin the verdict used; the
margin is computed once and never re-derived at write time.
- **Pre-port ledgers still replay to the same verdict.** A ledger with no
`margin` and no `provenance` validates (`ledger: valid`, exit 0) and only
fails when a caller *asks* for provenance (exit 3, naming each `seq`).
- **A fabricated large margin is caught.** `"margin": 2.5` on a delta of 2.0 is
a replay violation.
- **The margin is never more permissive than the floor it replaced.** The
tracked `scripts/legacy_grid.py` walks 3,584 one-repeat points and 13,824
honest pairs and finds **0** keeps the legacy rule would have refused (870 the
other way); the only one-repeat divergence is the inconclusive band.
- **Provenance is a gate a caller opts into.** `status --require-provenance`
passes on what a real run wrote (`exit 0`) and fails on an old ledger
(`exit 3`), so the new claim does not invalidate old runs.
- **Credentials are refused, not recorded.** A `--model` URL carrying userinfo
exits 2 in preflight; no event file is created and no token appears in the
checkout.
- **A dead agent's tree is still judged.** An agent that exits 3 after making a
real improvement banks a `keep` with `salvaged: true` and
`agent_exit_code: 3`; a dead agent with a worse tree is `agent_error` carrying
its metric and exit code and is reverted.
- **The wall refuses what it cannot fund, with the arithmetic.**
`--max-wall 2000` exits 2 before the baseline, names 3300 s per iteration and
3301 s as the smallest usable wall; 3600 s runs one iteration.
- **A run's state can live entirely outside the measured checkout.** With
`--state-dir`, the checkout stays clean (no `.autoresearch`, empty
`git status`), and a command that is not told the state refuses (exit 2)
instead of guessing.
- **The close record is reproducible and drift-detecting.** `report --record`
writes it, `report --check` re-renders byte-identically (exit 0), and a
one-byte edit to the markdown is caught (exit 2, naming the file).
- **The objective record fails with every problem at once.** 8 problems, 8
lines, one pass, exit 1; the shipped registry validates and resolves to
`--repeats 3`.

## What Fails

- **No live model drove this layer.** Every run in this record — and AC-EVL-202
— uses the `command` or `replay` adapter with a scripted proposer. The
provenance block therefore records the operator's `--model` string (or
`command:default`), never a model observed from a harness. Nothing here has
replayed a keep made by a real Claude Code / opencode / Hermes round under the
margin.
- **Cost fields are always `null`.** No adapter parses token or call counts, so
`agent_tokens` and `agent_api_calls` are `null` in every event; SC-evl-6 is
met only as the explicit null. The "cheaper" leg of better/cheaper/faster is
unmeasured in this tree.
- **Replay trusts the recorded margin's value.** `validate()` checks that the
delta exceeds the recorded number, that it is finite and non-negative — it
never recomputes `max(floor, 1.96 × SE)` from the recorded
`values`/`se`/`floor`. A fabricated margin of 2.5 on a delta of 2.0 is caught;
a fabricated 1.0 where three repeats derive 2.0057 validates (`ledger: valid`,
exit 0).
- **The margin is optimistic at the smallest honest sample.** `Z = 1.96` is the
asymptotic 95% quantile; at `n = 2` the exact `t(0.975, df = 1)` is 12.7, so
the margin is roughly an order of magnitude too narrow at two repeats. It is
still strictly wider than the floor it replaced, which is what the grids
prove.
- **The close record's note quotes the floor, not the margin.** `record.md` says
"kept at iteration 2: 10 -> 6 beyond the 0.01 floor" while the decision used
2.0057. A reader of the close record alone cannot see the margin; only the
ledger trial event carries it.
- **The container/e2e tier was not exercised.** `bash tests/run.sh` covers
unit + integration (584 + 45); `--with-e2e` needs a running service and was
not run, so this layer's behaviour through REST/MCP is unverified here.
- **The referee half is absent by design.** No measured A/A noise floor, no
evaluator drift canary, no cheat probes, no seeded-defect audit rate, no
`faster` leg: `better` (one metric, one direction) is the only measured leg,
and none of the anti-gaming checks that make "the evaluator did not move"
provable exist in this tree.
- **A dead *engine* cannot be salvaged.** Salvage covers an agent that dies
mid-iteration; the engine handles `SIGINT` only, so an outer
`SIGTERM`/`SIGKILL` loses the in-flight tree. The wall reservation is the
defence, not a promise that a kill is safe.
- **Three repeats triple the verify cost, and an inconclusive burns a plateau
slot.** A target whose verify takes minutes pays 3× per candidate, and a
jittering target reaches `--plateau` sooner than a discard-only loop would
(this run: 1 inconclusive out of 2 iterations).

## Resolution

- Run one live harness round on a real target (ex5, or the next live target) at
`--repeats 3` and append its provenance block and ledger excerpt here; until
then the block is an operator claim, and this document says so rather than
implying a model was observed.
- Teach an adapter to parse token and call counts from its harness output and
write them into the trial event; until then `null` is the honest value, and
the layer must not report a cost it did not measure.
- Recompute the margin inside `validate()` from the recorded `values`, `se`,
`repeats`, `noise_floor` and `direction`, and compare the recorded `margin`
against it — the fixture already carries every input, so the check is
derivable without re-running the verify. This is the next PRD-20 revision, and
per `AGENTS.md` funnel stage 7 it belongs in the issue tracker until that PRD
lands (downstream records the same hole against its own layer).
- Switch to `t`-based margins, or require `repeats >= 5` for stochastic metrics,
in a later PRD; the assumption is stated in PRD 20 and the current rule is
still never narrower than the legacy floor.
- Thread the keep event's recorded `margin` into `record._reading`'s note (the
function already receives the keep events), so the close record and the ledger
agree; meanwhile the ledger is the authority and `raw` + `values` are in the
record.
- Run `bash tests/run.sh --with-e2e` off the deployment — never on a host that
serves this compose project, per `AGENTS.md` §6 — and record the REST/MCP path
here when a surface exposes this layer.
- Leave the referee half downstream: PRD 20's *Out of Scope* records why, and
the rules are held in `kb/concepts/deterministic-keep-gate.md` and
`kb/concepts/better-cheaper-faster-metrics.md` so a future PRD implements them
with tests instead of porting dead code.
- Treat the wall reservation as the answer to an outer kill: price the wall at
`agent_timeout + guard_timeout + repeats × verify_timeout` (the preflight now
refuses anything smaller), and send `SIGINT` when an operator wants a
salvageable stop.
- Size `--repeats` per target noise and set `--plateau` above the inconclusive
rate a pilot run shows; the wall arithmetic already forces the budget to fund
`repeats × verify_timeout`, so a slow verify widens the wall instead of
silently truncating a run.

Carried forward, not failures of this layer: the W4 command-registry deferral —
`surfaces()` generates `('cli',)` until a REST or MCP route exists for these
commands (`docs/prd/23-command-registry.md`) — and dependabot PR #48
(`The-PR-Agent/pr-agent` 0.49.0 → 0.50.0), which is a workflow-pin bump owned by
PRD 18 and not by the engine.

## Verdict

**works** for the engine eval layer as PRD 20 scopes it: all six SCs are
verified by test and re-verified live here — dispersion reported or explicitly
`null`, a margin-gated keep with `inconclusive` as a real third verdict,
six-field provenance with an opt-in read-side gate, replay that re-checks a
recorded margin and leaves pre-port ledgers valid, and a close record that
re-renders byte-identically. The limits above are scope, not failed paths: no
live model has run it, cost fields are honest nulls, and replay trusts the
recorded margin's value — the one that matters, recorded first.
