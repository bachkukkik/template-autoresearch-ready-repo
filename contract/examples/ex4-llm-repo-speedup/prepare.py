"""prepare.py — FROZEN evaluator for the ex4-llm-repo-speedup worked example.

This is the karpathy/autoresearch contract instantiated on a **real software
repo**: a frozen test suite (``target/tests.py``) gates a candidate's
correctness, and the candidate's wall-clock median on a fixed workload is the
metric. The candidate is ONE file, ``target/solution.py``; everything in this
file is owned by the evaluator and is never edited during a run:

  * TIME_BUDGET      — the HARD wall-clock ceiling on one evaluated run
  * generate_data()  — the deterministic workloads (seeded, embedded)
  * reference()      — the frozen oracle
  * the child runner — screen -> import -> frozen tests -> held-out outputs ->
                       freshly seeded timed reps, all inside ONE subprocess
  * run_evaluator()  — spawns that subprocess, chooses the benchmark seeds with
                       ``secrets`` AFTER the child's import handshake, recomputes
                       ``reference(...)`` and compares the child's reported
                       outputs itself, kills the whole process group at
                       ``TIME_BUDGET`` and reports ``stop_reason: budget``
  * decide() / status_for() — the evaluator-owned keep/discard vocabulary

Three roles, never merged (the whole point of the example):

    frozen evaluator   this file + target/tests.py   (never edited in a run)
    human policy       program.md                     (authored once)
    agent artifact     target/solution.py             (the ONE edited file)

WORKLOAD CONTRACT (``target/solution.py`` must implement exactly this)

    run(items: list[str]) -> dict

Keys, always exactly these five:

    pairs         int   number of index pairs (i < j) with items[i] == items[j]
    groups        int   number of distinct values occurring at least twice
    largest       list  [value, count] of the most frequent value; ties resolve
                        to the lexicographically smallest value
                        (``[]`` when ``items`` is empty)
    top           list  up to 10 x [value, count], sorted by (-count, value asc)
    first_repeat  int   the smallest index j whose value already appeared in
                        items[:j]; -1 when no value repeats

Correctness gate — decided by the PARENT, never reported by the child. The child
runs inside the same process that would report a verdict, so within one process
there is no trust boundary: any number it asserts can be forged. Therefore the
child asserts **nothing**. It reports only the raw OUTPUTS of ``run(items)`` -- as
JSON, one record per input it was given -- and the parent recomputes
``reference(...)`` itself and compares:

  1. the FROZEN test suite (``target/tests.py``) is an extra child-side check
     (its failures fail the candidate, but its passing is not trusted);
  2. the BINDING gate is the parent's own exact-output comparison of the child's
     reported ``run(held_out)`` against ``reference(held_out)``, plus the same
     comparison on every benchmark workload whose seed the parent chose.

Missing or malformed outputs, or any mismatch, is a failed gate or a crash —
never a keep. So a candidate that writes a verdict file (no ``run()``), or that
lets an ``atexit`` hook rewrite one, has no verified output and cannot be kept.

Fresh inputs the candidate cannot precompute. The parent chooses ``BENCH_REPS``
benchmark seeds with ``secrets.randbits`` and sends them over the child's stdin
ONLY after the child signals (in the results channel) that it has imported the
candidate. The child builds each timed workload from its seed with this file's
own ``generate_data``. A workload precomputed at import time, or a cache reused
across reps, is therefore empty: the seeds did not exist when the artifact's
module body ran, and every rep uses a different one.

RESIDUAL RISK (honest, by design). The *correctness* signal is parent-verified
and cannot be forged. The *speed* number is still measured inside the candidate's
process and reported by the child, so a hostile candidate that patches the clock
could understate it. The parent applies one sanity bound — a run is rejected
(``gate: ok`` with ``stop_reason: error``, i.e. a crash) when its reported
``median * BENCH_REPS`` exceeds the wall time the parent actually measured for
the bench phase, or when the median is ``<= 0`` — but that bound cannot catch an
understatement. Run live loops only in a disposable sandbox; that is this
template's T2 stance on timing (a wall-clock delta within ~10% is not signal), so
the ledger's keep/discard decisions must not be read as precise.

Budget: the ENTIRE evaluated run (import + tests + held-out + ``BENCH_REPS``
timed calls) is one subprocess with a HARD ``TIME_BUDGET`` wall-clock limit. On
expiry the evaluator kills the child's whole process group, reports
``stop_reason: budget`` with ``median_seconds: inf``, and the driver records a
non-keep row. The baseline in this example is quadratic by construction, and the
child reports the held-out outputs BEFORE the timed reps start, so its row is
``gate: ok`` / ``stop_reason: budget`` / ``status: timeout`` — the budget binds,
it is not decoration.

The child is also started in its own process group with a scrubbed environment
(no ``OPENAI_*`` or other secrets: only PATH / PYTHONPATH / PYTHONHASHSEED and
a private HOME), so the evaluated code never inherits the caller's API key.

Stdlib only — no pytest, no third-party packages.
"""
import argparse
import importlib.util
import json
import math
import os
import random
import secrets
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter

# --------------------------------------------------------------- constants --
HERE = os.path.dirname(os.path.abspath(__file__))
TIME_BUDGET = 5            # seconds, HARD wall clock for one evaluated run
BENCH_REPS = 3             # median over 3 timed calls of run(big workload)
SAMPLE_SEED = 20261017     # the --summary display workload only; reps are fresh
SEED_HELD = 424242         # held-out workload seed (disjoint)
N_BIG = 60_000             # items in each timed workload
N_HELD = 3_000             # items in the held-out gate workload
VOCAB_SIZE = 4_000         # distinct strings in the generated corpus
DIRECTION = "lower"        # lower median seconds is better
LEDGER_HEADER = "commit\tmedian_seconds\tgate\tstop_reason\tstatus\ttokens\tdescription"
LEDGER_STATUSES = ("keep", "discard", "timeout", "crash")
ARTIFACT = os.path.join("target", "solution.py")
GATE_VALUES = ("ok", "failed")

# The child's report channel: one JSON record per line, written to a path the
# parent creates. The parent reads ONLY the stages below -- a line the candidate
# adds is ignored unless it is one of them, and an ``output`` record is judged by
# comparing it against ``reference(...)``, never by believing it.
STAGE_IMPORTED = "imported"     # handshake: the candidate module has been imported
STAGE_GATE = "gate_failed"      # a child-side failure (screen/no run/raise/tests)
STAGE_TESTS = "tests"           # the frozen suite's result (extra child-side check)
STAGE_OUTPUT = "output"         # one raw run(items) output for a parent-known input

# The evaluated child gets ONLY these variables from the caller's environment.
# Secrets (OPENAI_API_KEY and friends) are deliberately absent: the candidate
# is model-written code and must not be able to read the caller's credentials.
CHILD_ENV_PASSTHROUGH = ("PATH", "PYTHONPATH", "PYTHONHASHSEED", "SYSTEMROOT")


# --------------------------------------------------------------- workloads --
def generate_data(n, seed, vocab=VOCAB_SIZE):
    """Seeded list of ``n`` strings drawn from a Zipf-ish ``vocab``-word corpus.

    Deterministic: the same (n, seed) yields the same list on every platform, so
    the metric is comparable and a replay reproduces the gate.
    """
    rng = random.Random(seed)
    words = ["w{:05d}".format(i) for i in range(vocab)]
    weights = [1.0 / ((i + 1) ** 0.9) for i in range(vocab)]
    return rng.choices(words, weights=weights, k=n)


def bench_seeds():
    """Fresh benchmark seeds, chosen at run time by the parent.

    ``secrets`` (not the module's fixed ``random`` stream), and handed to the
    child only after it reports it has imported the candidate -- so the seeds do
    not exist while the artifact's module body runs. That defeats a workload
    precomputed at import time and a cache reused across reps.
    """
    return [secrets.randbits(64) for _ in range(BENCH_REPS)]


def reference(items):
    """Frozen oracle: the obvious dict-based implementation of the contract.

    This defines truth for the gate. The candidate is expected to reach (and may
    beat) this cost; it may not redefine or import it.
    """
    counts = Counter(items)
    pairs = sum(c * (c - 1) // 2 for c in counts.values())
    groups = sum(1 for c in counts.values() if c >= 2)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [[w, c] for w, c in ranked[:10]]
    largest = [ranked[0][0], ranked[0][1]] if ranked else []
    seen = set()
    first_repeat = -1
    for j, w in enumerate(items):
        if w in seen:
            first_repeat = j
            break
        seen.add(w)
    return {
        "pairs": pairs,
        "groups": groups,
        "largest": largest,
        "top": top,
        "first_repeat": first_repeat,
    }


HELD_OUT = generate_data(N_HELD, SEED_HELD)
HELD_OUT_WANT = reference(HELD_OUT)

# The frozen test suite lives with the target repo it tests (still frozen).
TESTS_PATH = os.path.join(HERE, "target", "tests.py")

# A candidate may not reach into the frozen truth: returning the oracle's
# output would pass the gate trivially and be "infinitely fast". The screen
# blocks importing the evaluator (the only route to HELD_OUT_WANT); parent-side
# verification is what makes forging the reported result pointless.
FORBIDDEN = ("import prepare", "from prepare", "prepare.reference")


# ------------------------------------------------------------- the harness --
def screen_source(path):
    """Return a rejection message when the artifact reaches for frozen truth."""
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        return "cannot read {}: {}".format(path, exc)
    for token in FORBIDDEN:
        if token in src:
            return "artifact references frozen truth ({!r})".format(token)
    return None


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _preview(value):
    if isinstance(value, (list, tuple)):
        return "{}({}) head={!r}".format(type(value).__name__, len(value),
                                         list(value[:3]))
    if isinstance(value, dict):
        return "dict({}) {!r}".format(len(value), list(value.items())[:3])
    return repr(value)


def _held_out_diff(got, want):
    """First key that differs (or a shape complaint), for the run log."""
    if not isinstance(got, dict):
        return "run() returned {}, expected dict".format(type(got).__name__)
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    if missing or extra:
        return "keys differ (missing={}, extra={})".format(missing, extra)
    for key in sorted(want):
        if got[key] != want[key]:
            return "key {!r}: got {} want {}".format(
                key, _preview(got[key]), _preview(want[key]))
    return None


def _canonical(value):
    """``value`` as the parent will see it: a JSON round-trip.

    JSON normalises shapes (a tuple becomes a list), so the parent's comparison
    is over the value the child actually reported. An unserialisable output
    becomes a sentinel that can never equal ``reference`` -> a failed output.
    """
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return {"__unserialisable__": repr(value)[:200]}


def _print(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def child_env(home):
    """The minimal environment for the evaluated child.

    Only PATH / PYTHONPATH / PYTHONHASHSEED (and SYSTEMROOT on Windows) are
    inherited, plus a private HOME. No ``OPENAI_*``, no cloud credentials, no
    caller secrets: the candidate is model-written code.
    """
    env = {key: os.environ[key] for key in CHILD_ENV_PASSTHROUGH
           if key in os.environ}
    env["HOME"] = home
    env["PYTHONDONTWRITEBYTECODE"] = "1"    # never write into the repo tree
    return env


def _kill_group(proc):
    """SIGKILL the child's whole process group (it has its own session).

    A plain ``proc.kill()`` leaves grandchildren (anything the candidate
    spawned) running as orphans, still burning the machine after the budget.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError):
        proc.kill()


def _read_seeds():
    """The fresh benchmark seeds the parent sends over stdin post-handshake."""
    line = sys.stdin.readline()
    if not line:
        return []
    try:
        data = json.loads(line)
    except ValueError:
        return []
    seeds = data.get("seeds") if isinstance(data, dict) else None
    if not isinstance(seeds, list):
        return []
    return [seed for seed in seeds
            if isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0]


def _child(candidate_path, results_path):
    """One evaluated run: screen -> import -> tests -> held-out -> timed reps.

    The child writes JSON records to ``results_path`` for the PARENT to judge:
    a handshake once the candidate is imported, the frozen suite's result, the
    raw ``run()`` output on the held-out workload, and the raw ``run()`` output
    plus its own measured seconds for each freshly seeded benchmark workload. It
    reports no gate and no keep — the parent recomputes ``reference(...)`` and
    compares. stdout is a human-readable log and nothing else.

    Exit: 0 ok, 2 a child-side failure (screen / no run() / raise / tests).
    """
    def emit(record):
        with open(results_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def fail(detail):
        _print("gate_detail: " + detail)
        emit({"stage": STAGE_GATE, "detail": detail})
        _print("stop_reason: gate_failed (child-side)")
        return 2

    problem = screen_source(candidate_path)
    if problem is not None:
        return fail(problem)

    module = _load_module(candidate_path, "ex4_solution")
    if module is None or not callable(getattr(module, "run", None)):
        return fail("artifact defines no callable run()")

    # Handshake. The parent chooses and sends the fresh benchmark seeds ONLY
    # after this — the artifact's module body has already run, so a workload it
    # precomputed at import cannot use a seed it has not been given yet.
    emit({"stage": STAGE_IMPORTED})
    _print("imported: {}".format(candidate_path))

    tests = _load_module(TESTS_PATH, "ex4_frozen_tests")
    try:
        failures = tests.run_tests(module.run)
    except Exception as exc:                        # noqa: BLE001
        failures = ["frozen suite raised {}: {}".format(type(exc).__name__, exc)]
    emit({"stage": STAGE_TESTS, "cases": len(tests.CASES), "failures": failures})
    if failures:
        return fail(failures[0])
    _print("tests: {} passed (child-side; the parent's own comparison binds)"
           .format(len(tests.CASES)))

    # The held-out output goes to the parent BEFORE the timed reps, so a run the
    # budget kills mid-benchmark still carries a verifiable held-out result —
    # which is why the baseline's row is gate ok / budget / timeout.
    try:
        got = module.run(list(HELD_OUT))
    except Exception as exc:                        # noqa: BLE001
        return fail("run(held_out) raised {}: {}".format(type(exc).__name__, exc))
    emit({"stage": STAGE_OUTPUT, "name": "held_out", "output": _canonical(got)})
    _print("held_out: output reported ({} items)".format(N_HELD))

    seeds = _read_seeds()          # the parent's fresh seeds, sent post-handshake
    if not seeds:
        return fail("no benchmark seeds on stdin")
    for seed in seeds:
        payload = generate_data(N_BIG, seed)
        start = time.perf_counter()
        try:
            got = module.run(payload)
        except Exception as exc:                    # noqa: BLE001
            return fail("run(bench seed {}) raised {}: {}".format(
                seed, type(exc).__name__, exc))
        seconds = time.perf_counter() - start
        emit({"stage": STAGE_OUTPUT, "name": "bench", "seed": seed,
              "seconds": seconds, "output": _canonical(got)})
        _print("bench seed {}: {:.6f}s".format(seed, seconds))
    _print("done: {} benchmark(s) reported".format(len(seeds)))
    return 0


def _has_stage(path, stage):
    """True when the results channel already holds a record with this stage."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("stage") == stage:
            return True
    return False


def _await_imported(proc, results_path, deadline):
    """Wait for the child's import handshake, its exit, or the deadline.

    The seeds are chosen and sent only after this signal returns True.
    """
    while time.perf_counter() < deadline:
        if _has_stage(results_path, STAGE_IMPORTED):
            return True
        if proc.poll() is not None:      # the child is gone; stop waiting
            break
        time.sleep(0.005)
    return _has_stage(results_path, STAGE_IMPORTED)


def _send_seeds(proc, seeds):
    """Hand the child its fresh benchmark seeds over stdin, then close it.

    A dead child raises BrokenPipe — nothing to send, and the judge will see no
    outputs — so the error is swallowed rather than aborting the run.
    """
    try:
        proc.stdin.write(json.dumps({"seeds": list(seeds)}) + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass
        # communicate() would flush a still-attached stdin and raise on a closed
        # one, so detach it now that the seeds are written.
        proc.stdin = None


def _parse_records(path, seeds):
    """The child's records, keeping only the recognised stages.

    A line that is not one of the known stages (a candidate's forged verdict,
    for instance) is ignored: it can never assert a verdict. A forged ``output``
    record IS kept — and then judged like any other, by comparing it against
    ``reference``, where a wrong one only adds a mismatch.
    """
    records = {"imported": False, "gate_failed": None, "tests": None,
               "outputs": [], "seeds": set(seeds)}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return records
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        stage = record.get("stage")
        if stage == STAGE_IMPORTED:
            records["imported"] = True
        elif stage == STAGE_GATE:
            records["gate_failed"] = str(
                record.get("detail") or "child-side gate failure")
        elif stage == STAGE_TESTS:
            records["tests"] = record
        elif stage == STAGE_OUTPUT:
            records["outputs"].append(record)
    return records


def _judge(records, code, timed_out, bench_wall):
    """The PARENT's verdict, from its own comparison of the child's outputs.

    The parent recomputes ``reference(...)`` for the held-out workload and for
    every benchmark workload whose seed the parent itself chose, and compares. A
    mismatch, a child-reported gate failure, or a missing output is a failure or
    a crash — never a keep. A timeout always wins: median ``inf``, ``budget``,
    with ``gate: ok`` when the held-out outputs delivered first all matched.
    """
    inf = float("inf")
    seeds = records["seeds"]
    failed = records["gate_failed"]
    if failed is None and (records["tests"] or {}).get("failures"):
        failed = "frozen tests: " + str(records["tests"]["failures"][0])

    held_out_seen = False
    held_out_ok = False
    bench = {}                      # seed -> measured seconds (matched only)
    for record in records["outputs"]:
        name = record.get("name")
        got = record.get("output")
        if name == "held_out":
            held_out_seen = True
            if got == HELD_OUT_WANT:
                held_out_ok = True
            else:
                failed = failed or ("held-out output != reference: "
                                    + _held_out_diff(got, HELD_OUT_WANT))
        elif name == "bench":
            seed = record.get("seed")
            if seed not in seeds:
                continue            # a rep the parent never seeded: ignore it
            if got != reference(generate_data(N_BIG, seed)):
                failed = failed or "bench output != reference (seed {})".format(seed)
            else:
                seconds = record.get("seconds")
                numeric = (isinstance(seconds, (int, float))
                           and not isinstance(seconds, bool)
                           and math.isfinite(seconds) and seconds > 0)
                bench[seed] = float(seconds) if numeric else None

    any_output = held_out_seen or bool(bench)
    if timed_out:
        gate = "failed" if failed else ("ok" if held_out_ok else "n/a")
        return {"median": inf, "gate": gate, "stop_reason": "budget"}
    if failed is not None:
        return {"median": inf, "gate": "failed", "stop_reason": "gate_failed"}
    if not any_output or not held_out_seen:
        return {"median": inf, "gate": "n/a", "stop_reason": "error"}
    if code != 0 or len(bench) != len(seeds) or any(v is None for v in bench.values()):
        return {"median": inf, "gate": "ok", "stop_reason": "error"}
    median = statistics.median(bench.values())
    # Sanity bound only: the speed number is measured inside the candidate's own
    # process, so an understated median passes. A median the phase wall clock
    # could not have produced (or a non-positive one) is rejected outright.
    if median <= 0 or median * BENCH_REPS > bench_wall:
        return {"median": inf, "gate": "ok", "stop_reason": "error"}
    return {"median": median, "gate": "ok", "stop_reason": "done"}


def run_evaluator(candidate_path):
    """Evaluate one candidate under the budget. Returns ``(verdict, log)``.

    The child runs with its own process group and a scrubbed environment, and
    reports to a results file the parent reads: the raw ``run()`` outputs for the
    held-out workload and for each benchmark workload whose seed the parent chose
    with ``secrets`` after the child's import handshake. The parent recomputes
    ``reference(...)`` and compares — it never reads a gate or a median the child
    asserts. At ``TIME_BUDGET`` the whole process group is killed and the verdict
    is ``median_seconds: inf`` / ``stop_reason: budget``.
    """
    start = time.perf_counter()
    timed_out = False
    code = None
    with tempfile.TemporaryDirectory(prefix="ex4-run-") as tmp:
        results_path = os.path.join(tmp, "results.jsonl")
        log_path = os.path.join(tmp, "child.log")
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        cmd = [sys.executable, "-u", os.path.abspath(__file__), "--child",
               candidate_path, "--results", results_path]
        with open(log_path, "w", encoding="utf-8") as logf:
            proc = subprocess.Popen(cmd, cwd=HERE, env=child_env(home),
                                    stdin=subprocess.PIPE, stdout=logf,
                                    stderr=subprocess.STDOUT, text=True,
                                    start_new_session=True)
            deadline = start + TIME_BUDGET
            # Handshake first: the fresh seeds exist only after the child has
            # imported the candidate, so nothing can precompute their workloads.
            imported = _await_imported(proc, results_path, deadline)
            seeds = bench_seeds() if imported else []
            sent_at = time.perf_counter()
            _send_seeds(proc, seeds)
            try:
                proc.communicate(timeout=max(0.0, deadline - time.perf_counter()))
                code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
                proc.communicate()
            bench_wall = time.perf_counter() - sent_at
            verdict = _judge(_parse_records(results_path, seeds), code,
                             timed_out, bench_wall)
        with open(log_path, encoding="utf-8") as fh:
            child_out = fh.read()
    wall = time.perf_counter() - start

    lines = [line for line in child_out.splitlines() if line.strip()]
    if timed_out:
        lines.append("# killed at TIME_BUDGET={}s (whole process group)".format(
            TIME_BUDGET))
    lines.append("# verdict: the parent's own comparison of the child's reported "
                 "run() outputs; child exit={}".format(
                     "timeout" if timed_out else code))
    lines.append("median_seconds: {}".format(format_median(verdict["median"])))
    lines.append("gate: {}".format(verdict["gate"]))
    lines.append("stop_reason: {}".format(verdict["stop_reason"]))
    lines.append("time_budget: {}".format(TIME_BUDGET))
    lines.append("total_seconds: {:.3f}".format(wall))
    log = "# FROZEN evaluator (prepare.py) — candidate: {}\n".format(
        candidate_path) + "\n".join(lines) + "\n"
    verdict["wall_seconds"] = wall
    return verdict, log


# --------------------------------------------------- evaluator-owned policy --
def decide(metric, incumbent, gate_ok, direction=DIRECTION):
    """The evaluator-owned keep/discard rule (the agent never self-awards).

    A candidate is a ``keep`` only when the gate passed AND its median is
    strictly below the incumbent. ``incumbent`` starts at ``inf`` because the
    baseline is over budget by construction, so the first valid candidate that
    fits is the first keep.
    """
    if direction != "lower":
        raise ValueError("prepare.decide: only direction='lower' is defined")
    if not gate_ok:
        return "discard"            # an invalid candidate is never a keep
    return "keep" if metric < incumbent else "discard"


def status_for(verdict, incumbent):
    """Map an evaluator verdict onto the ledger's status vocabulary.

    ``budget`` -> ``timeout`` (the gate had passed) or ``crash`` (it had not);
    a failed gate or an error -> ``crash``; otherwise the keep/discard rule.
    """
    if verdict["stop_reason"] == "budget":
        return "timeout" if verdict["gate"] == "ok" else "crash"
    if verdict["gate"] != "ok":
        return "crash"
    if verdict["stop_reason"] != "done":
        return "crash"
    return decide(verdict["median"], incumbent, gate_ok=True)


def format_median(metric):
    return "inf" if metric == float("inf") else "{:.6f}".format(metric)


# ------------------------------------------------------------------- main ----
def _summary():
    print("TIME_BUDGET={}s  BENCH_REPS={}  (hard wall-clock ceiling per run)"
          .format(TIME_BUDGET, BENCH_REPS))
    train = generate_data(N_BIG, SAMPLE_SEED)
    want = reference(train)
    print("sample big workload: {} items / vocab {} / distinct {} / pairs {} "
          "(each rep gets a FRESH parent-chosen seed)".format(
              N_BIG, VOCAB_SIZE, len(set(train)), want["pairs"]))
    print("held-out:     {} items / distinct {} / pairs {}".format(
        N_HELD, len(set(HELD_OUT)), HELD_OUT_WANT["pairs"]))
    print("artifact:     {} (the only agent-edited file)".format(ARTIFACT))
    print("gate:         the PARENT's own run(held_out) == reference comparison "
          "(target/tests.py is an extra child-side check)")
    print("seeds:        chosen with secrets.randbits AFTER the child's import "
          "handshake, sent over its stdin")
    start = time.perf_counter()
    reference(train)
    print("reference() on the sample workload: {:.3f}s "
          "(one undistributed call)".format(time.perf_counter() - start))


def main(argv):
    parser = argparse.ArgumentParser(
        description="FROZEN ex4 evaluator — dataset summary, one run, or the "
                    "internal budget-bounded child.")
    parser.add_argument("--run", metavar="ARTIFACT",
                        help="evaluate one candidate file under TIME_BUDGET")
    parser.add_argument("--child", metavar="ARTIFACT", help=argparse.SUPPRESS)
    parser.add_argument("--results", metavar="PATH", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child is not None:
        if not args.results:
            raise SystemExit("--child needs --results PATH (parent-provided)")
        return _child(args.child, args.results)
    if args.run is not None:
        verdict, log = run_evaluator(args.run)
        sys.stdout.write(log)
        if verdict["stop_reason"] == "budget":
            return 3
        if verdict["gate"] != "ok":
            return 2
        return 0
    _summary()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
