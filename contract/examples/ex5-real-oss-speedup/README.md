# ex5 — a real open-source hot path as an autoresearch target

`ex5` is the template's **real-code** example: the engine is pointed at a
verbatim copy of one module from a real, widely-installed library, and the loop
has to make it faster without changing a single output.

* **Target:** `target/distance.py` — NLTK's `nltk/metrics/distance.py`.
* **Metric:** median seconds of a fixed seeded workload, lower is better
  (`METRIC seconds=<median>` from `bench.py`).
* **Gate:** `python3 guard.py` must exit 0 — vendored upstream test cases plus a
  differential oracle against a frozen pristine copy over 4 000+ seeded inputs.
* **Editable scope:** `target/` only. `bench.py`, `guard.py` and `oracle/` are
  protected and hashed by `init`.

## Provenance — what this code is and why it is real

| | |
|---|---|
| Upstream | NLTK (Natural Language Toolkit) |
| File | `nltk/metrics/distance.py` |
| Version | **3.9.1** (tag `3.9.1`) |
| Commit | `aca78cb2add4084f76b9eac921d8a73927d7a086` |
| URL | https://github.com/nltk/nltk/blob/3.9.1/nltk/metrics/distance.py |
| License | **Apache License 2.0** (`target/LICENSE-UPSTREAM` = NLTK's `LICENSE.txt`, verbatim) |
| Size | 508 lines, pure Python, stdlib only (`operator`, `warnings`) |
| sha256 | `e35e62a30a00f48a85fb76ee9263d7f87b2ec0cd2aa30469ebaa55312c4316bf` |
| Changes | none — `target/distance.py` and `oracle/reference_distance.py` are byte-identical to upstream |

Why this module:

* **It is real.** `nltk.metrics.distance` is what people actually call for
  record linkage, fuzzy string matching and inter-annotator agreement in NLTK,
  a library with tens of millions of downloads. The code is shipped, not a
  teaching snippet.
* **It is a genuine hot path.** `edit_distance` is the inner loop of any
  deduplication pass; it allocates a full DP matrix and calls a Python helper
  once per cell, which is exactly the shape an agent can improve safely.
* **It is pinned and small.** 508 lines, one file, one commit, no data files,
  no optional C accelerator, no network, no environment — a deterministic
  target whose behaviour can be frozen byte-for-byte.
* **Upstream has its own tests.** `nltk/test/unit/test_distance.py` supplies 21
  parametrised `edit_distance` cases (both orderings, both transposition
  settings, several substitution costs). They are vendored in
  `oracle/upstream_cases.py` as data so the guard needs no test framework.

The one thing this example does **not** claim: that NLTK is slow in production.
It claims that a pure-Python DP loop of this shape has measurable, honest
headroom, which the measurements below show.

## Layout

```
README.md                     this runbook
program.md                    standing instructions copied into every prompt
setup.sh                      make a disposable target repo from this example
bench.py            PROTECTED  verify: fixed seeded workload -> METRIC seconds=<median>
guard.py            PROTECTED  guard: policy + upstream cases + differential oracle
oracle/
  reference_distance.py       the pristine upstream file, frozen (the oracle)
  upstream_cases.py           the upstream test cases, vendored as data
target/
  distance.py                 the ONLY agent-editable file (verbatim upstream)
  LICENSE-UPSTREAM            NLTK's LICENSE.txt, verbatim (Apache-2.0)
  NOTICE                      origin, commit, sha256, "no changes"
```

## The workload

`bench.py` runs a fixed mix, three timed reps by default, each rep seeded from
`SEED + rep` (so caching across reps cannot help):

| Workload | Calls per rep |
|---|---|
| `edit_distance(word, typo)` | 6 600 |
| `edit_distance(..., transpositions=True)` | 6 600 |
| `edit_distance_align(short, short)` | 2 000 |
| `jaro_similarity` + `jaro_winkler_similarity` on name pairs | 20 000 |
| `jaccard_distance` + `masi_distance` on token sets | 8 000 |

Measured on the reference host (CPython 3.12):

| | seconds |
|---|---|
| one `bench.py` invocation (3 internal reps) | **≈ 1.9 s** |
| the engine's baseline metric (`--repeats 3` → median of 9 reps) | **≈ 0.60 s** |
| one `guard.py` run | **≈ 1.7 s** |
| one candidate, end to end (guard + 3 × verify) | **≈ 7 s** |

Timing is machine-dependent; only the *relative* improvement over the incumbent
is judged, with a 2 % noise floor and a median over repeats.

## Run it

```bash
# 1. a disposable repo: copy + git init + one baseline commit + engine init
bash contract/examples/ex5-real-oss-speedup/setup.sh "$TMPDIR/ex5"
cd "$TMPDIR/ex5"

# 2. prove the wiring without spending a token
PYTHONPATH=<repo>/engine python3 -m autoresearch run --repo . --agent claude --dry-run

# 3. a live run
PYTHONPATH=<repo>/engine python3 -m autoresearch run --repo . \
  --agent claude --max-iterations 8 --plateau 3
```

`setup.sh` records exactly this config (read it back from
`.autoresearch/run.json`):

```
verify  python3 bench.py      guard  python3 guard.py
metric  seconds (lower)       scope  target
protect bench.py, guard.py, oracle/reference_distance.py, oracle/upstream_cases.py
repeats 3        noise-floor 0.02        program program.md
```

The guard that the ledger scores against **is** `python3 guard.py` — the same
command string `init` hashed, not a stronger one described in prose and not a
weaker one wired into the loop.

### Per harness

| Harness | Command |
|---|---|
| Claude Code | `run --repo . --agent claude --model claude-sonnet-4-5 --max-iterations 8` |
| opencode | `run --repo . --agent opencode [--model <provider/model>] --max-iterations 8` |
| Hermes | `run --repo . --agent hermes [-m <model>] --max-iterations 8` |
| DeepSeek harness | `run --repo . --agent dsh --max-iterations 8` (`OPENAI_API_KEY` required) |
| Any CLI | `run --repo . --agent command --agent-cmd 'my-agent --prompt-file {prompt_file}' --max-iterations 8` |
| Replay | `run --repo . --agent replay --replay record.jsonl` (needs a run made with `--record record.jsonl`) |

All of them are prefixed with `PYTHONPATH=<repo>/engine python3 -m autoresearch`,
or use `engine/bin/autoresearch` from inside the template repo.

### A no-op sanity run

```bash
PYTHONPATH=<repo>/engine python3 -m autoresearch run --repo . \
  --agent command --agent-cmd 'true' --max-iterations 1
# iter 1: no_change metric=n/a commit=- — iteration 1
# stop: max_iterations after 1 iteration(s) (incumbent 0.611 at 1f2ab90)
```

`no_change` is the right outcome: the adapter changed nothing, so nothing was
committed, guarded or measured. `status` still replays as valid.

## The guard — and why it is the whole point

A faster-but-wrong candidate is worthless, so speed is only measured after the
guard passes. `guard.py` has four stages and exits 0 only if all pass:

1. **policy** — every `.py` under `target/` parses; no `importlib`/`os`/`sys`/
   `subprocess`/`socket`/`pathlib`/`pickle`/oracle import; and the candidate may
   not use `open`/`exec`/`eval`/`compile`/`__import__`/`__globals__`-style
   escapes **more often than the pristine file already does**. (Upstream's
   `custom_distance` calls `open`, so the rule is a count, not a ban: adding a
   second `open` to read `bench.py` or the oracle fails.)
2. **upstream** — the 21 vendored `edit_distance` cases, both string orderings ×
   both transposition settings × their substitution costs (84 evaluations).
3. **differential** — 4 010 comparisons against `oracle/reference_distance.py`
   (the pristine file): `edit_distance` (plain, symmetric, `substitution_cost=3`,
   transpositions, transpositions+`substitution_cost=2`), `edit_distance_align`,
   `jaro_similarity`, `jaro_winkler_similarity` (default and `p=0.2,max_l=3`),
   `jaccard_distance`, `masi_distance`, `binary_distance`, `interval_distance`.
   Inputs are seeded randoms over six alphabets (including non-ASCII and emoji),
   lengths 0–120, plus hand-picked edge cases: empty strings, one-sided empties,
   single characters, repeats, transpositions, whitespace, and 120-character
   strings.
4. **surface** — the candidate still exposes every public callable the pristine
   module exposes (all twelve, `presence`/`fractional_presence`/`custom_distance`
   included) with an unchanged `inspect.signature` string. Deleting a function
   the bench never calls, or widening a signature, fails here.

Integer and container results are compared exactly (`int` must stay `int`);
floats to 1e-12, so an agent may reassociate arithmetic but cannot move a value.
A call that raises is behaviour too: the exception's type is recorded and
compared, so "raise instead of answer" is not a way through.

### Isolation — the candidate never runs in the judging process

The candidate is imported **only in a throwaway child** (`python3 -I`, minimal
environment, a timeout, JSON over stdin/stdout). The parent refuses to import it
at all, which closes three doors at once:

* `raise SystemExit(0)` (or `KeyboardInterrupt`) at import cannot end the guard —
  the child dies without an answer and the stage fails. On top of that, any
  `BaseException` escaping the guard's own body exits 1, and exit 0 is reached
  only after an explicit stage counter equals the number of stages, one line
  after the `guard: ok` sentinel is printed.
* The candidate cannot monkeypatch `math.isclose`, `random.Random` or the
  reference module: the expectations are computed from the pristine oracle in
  the parent, with a parent-owned `Random`, **before** the child is spawned; the
  tolerance is bound at the guard's import. The child only reports what the
  candidate returned.
* The same isolation covers the upstream stage, so a candidate cannot reach into
  the case table either. The policy stage stays a static AST read, as before.

Twelve comparison shapes across ~4 000 inputs is what catches the failures that
a benchmark cannot: an off-by-one in the transposition step, a row-reuse bug
that only bites on long strings, or a `jaro_similarity` that matches the wrong
character. Measured on throwaway probes:

| Probe | Guard | `METRIC seconds` |
|---|---|---|
| pristine upstream | ok | 0.612 |
| + inline non-transposition DP, `set` membership in Jaro | ok | 0.437 (−28 %) † |
| + inline transposition DP and `edit_distance_align` | ok | 0.322 (−47 %) † |
| `binary_distance` returns 0.0 always | **FAIL** (differential) | — |
| transposition cost `-1` dropped | **FAIL** (upstream) | — |
| pristine + `open("bench.py")` at import | **FAIL** (policy) | — |
| pristine + `raise SystemExit(0)` at import | **FAIL** (upstream: no answer) | — |
| pristine + patched `math.isclose`, wrong `binary_distance` | **FAIL** (differential) | — |
| pristine − `presence`/`fractional_presence`/`custom_distance` | **FAIL** (surface) | — |

† The two optimised rows were timed with the earlier in-process timer, which
started after the import; the shipped bench costs each rep a fresh interpreter
(≈0.05 s) and charges the import, so those ratios are an upper bound on the win,
not a promise. The pristine row (0.612) is the shipped bench's baseline.

So the headroom is real (≈1.9× with two safe passes, before the cold-start tax)
and the guard is real (it rejects exactly the shortcuts that would fake it). The
probe files are not shipped: they were throwaway copies, and a candidate that
merely reproduces them is not in this repo.

### Residual risk (stated, not hidden)

* **The timer charges the import, not a candidate's intent.** Each rep is a cold
  `python3 -I` child timed end to end, so precomputation at import (memoising the
  seeded pairs, building tables, warming caches) is paid on every rep instead of
  being free. What this does **not** do is make timing introspection impossible:
  code can still look at the state of the world (process start, CPU time, the
  module's own call pattern) and behave differently when it believes it is being
  benchmarked. No timer can see that, and no amount of rep-counting fixes it.
  The backstop is the guard: it replays behaviour on different seeds, in a
  separate process, against the pristine oracle, so a candidate that is fast
  because it is wrong scores nothing. A candidate that is fast *and* correct on
  every probed input is, by the contract, an optimisation.
* The guard's seeds are constants in a protected file, so a determined agent
  could in principle special-case them. Two things make that pointless: the
  bench uses different seeds *and* a fresh seed per rep, and the differential
  inputs are unrelated to the bench inputs, so a bench-shaped shortcut never
  earns a keep it can also pass.
* The policy compares construct *counts*. Reusing upstream's existing `open`
  instead of adding one would pass the policy — but the value is nil: the
  module cannot act on another file without new code that the differential
  oracle would have to keep honest anyway.
* An inherited `EX5_GUARD_PAIRS` / `EX5_BENCH_SCALE` cannot quietly weaken a run:
  below the documented default both scripts exit 2 unless `EX5_TEST_MODE=1`
  marks the shrink as deliberate, and a scale that leaves the workload empty is
  refused outright.

## Reproduce the numbers

```bash
cd contract/examples/ex5-real-oss-speedup
python3 guard.py                          # policy/upstream/differential/surface -> guard: ok
python3 bench.py                          # ~1.9 s, prints METRIC seconds=~0.61
EX5_TEST_MODE=1 EX5_BENCH_SCALE=0.05 python3 bench.py   # same shape, ~0.1 s (unit tests)
EX5_TEST_MODE=1 EX5_GUARD_PAIRS=40 python3 guard.py     # fewer random pairs, ~0.7 s

# the guard is not decorative: mutate a copy and watch it fail
cp -R . "$TMPDIR/ex5-mutant" && cd "$TMPDIR/ex5-mutant"
python3 - <<'EOF'
import pathlib
p = pathlib.Path("target/distance.py")
p.write_text(p.read_text().replace("return 0.0 if label1 == label2 else 1.0", "return 0.0"))
EOF
python3 guard.py; echo "exit=$?"          # exit=1, FAILED at differential oracle
```

Unit tier: `python3 -m pytest tests/unit/test_examples_ex5.py -q`
(AC-EXA-040..050 — the guard accepts the pristine target and rejects a mutant, a
filesystem escape, `SystemExit(0)` at import, a monkeypatched tolerance and a
deleted callable; the bench charges import time, prints one parseable metric and
refuses a vacuous environment; `setup.sh` produces a runnable, clean-tree
target).

## Licence note

`target/distance.py` is Apache-2.0 code from NLTK. `target/LICENSE-UPSTREAM` and
`target/NOTICE` must travel with it; an optimised copy redistributed outside
this example still carries NLTK's licence and attribution. Everything added by
this example (`bench.py`, `guard.py`, `setup.sh`, `program.md`, this README) is
covered by the repository's own licence.
