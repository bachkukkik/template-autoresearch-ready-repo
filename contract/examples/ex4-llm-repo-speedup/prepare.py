"""prepare.py — FROZEN evaluator for the ex4-llm-repo-speedup worked example.

This is the karpathy/autoresearch contract instantiated on a **real software
repo**: a frozen test suite (``target/tests.py``) gates a candidate's
correctness, and the candidate's wall-clock median on a fixed workload is the
metric. The candidate is ONE file, ``target/solution.py``; everything in this
file is owned by the evaluator and is never edited during a run:

  * TIME_BUDGET      — the HARD wall-clock ceiling on one evaluated run
  * generate_data()  — the deterministic workloads (seeded, embedded)
  * reference()      — the frozen oracle for the held-out workload
  * the child runner — screen -> frozen tests -> held-out exact-output gate ->
                       timed reps, all inside ONE subprocess
  * run_evaluator()  — spawns that subprocess under demand, kills it at
                       ``TIME_BUDGET`` and reports ``stop_reason: budget``
  * decide() / status_for() — the evaluator-owned keep/discard vocabulary
  * parse_verdict()  — the run log -> verdict reader

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

Correctness gate (both must hold; a failure is NEVER a keep):
  1. the frozen test suite in ``target/tests.py`` reports zero failures;
  2. ``run(held_out) == reference(held_out)`` — an exact-dict comparison on a
     held-out workload the candidate's code never saw, so a
     special-cased-to-the-tests implementation is rejected.

Budget: the ENTIRE evaluated run (screen + tests + gate + ``BENCH_REPS`` timed
calls on the big workload) is one subprocess with a HARD ``TIME_BUDGET``
wall-clock limit. On expiry the evaluator kills the process, reports
``stop_reason: budget`` with ``median_seconds: inf``, and the driver records a
non-keep row. The baseline in this example is quadratic by construction, so its
row IS a budget stop — the budget binds, it is not decoration.

Only the judged read this: ``median_seconds`` / ``gate`` / ``stop_reason`` in the
key: value lines at the end of the run log. Stdlib only — no pytest, no
third-party packages.
"""
import argparse
import importlib.util
import json
import os
import random
import statistics
import subprocess
import sys
import time
from collections import Counter

# --------------------------------------------------------------- constants --
HERE = os.path.dirname(os.path.abspath(__file__))
TIME_BUDGET = 5            # seconds, HARD wall clock for one evaluated run
BENCH_REPS = 3             # median over 3 timed calls of run(big workload)
SEED_BIG = 20261017        # train workload seed
SEED_HELD = 424242         # held-out workload seed (disjoint)
N_BIG = 60_000             # items in the timed workload
N_HELD = 3_000             # items in the held-out gate workload
VOCAB_SIZE = 4_000         # distinct strings in the generated corpus
DIRECTION = "lower"        # lower median seconds is better
LEDGER_HEADER = "commit\tmedian_seconds\tgate\tstop_reason\tstatus\ttokens\tdescription"
LEDGER_STATUSES = ("keep", "discard", "timeout", "crash")
ARTIFACT = os.path.join("target", "solution.py")


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


def reference(items):
    """Frozen oracle: the obvious dict-based implementation of the contract.

    This defines truth for the held-out gate. The candidate is expected to reach
    (and may beat) this cost; it may not redefine or import it.
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

# A candidate may not reach into the frozen truth: returning the oracle output
# would pass the gate trivially and be "infinitely fast".
FORBIDDEN = ("import prepare", "from prepare", "EXPECTED", "run_reference",
             "reference(")


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


def _print(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _child(candidate_path):
    """One evaluated run: screen -> tests -> held-out gate -> timed reps.

    Runs inside the budget-bounded subprocess. Prints key: value lines and
    flushes every one, so the parent can read the gate verdict even when it
    kills this process at ``TIME_BUDGET``. Exit: 0 ok, 2 gate failed, 1 error.
    """
    problem = screen_source(candidate_path)
    if problem is not None:
        _print("gate: failed")
        _print("gate_detail: " + problem)
        _print("stop_reason: gate_failed")
        return 2

    module = _load_module(candidate_path, "ex4_solution")
    if module is None or not callable(getattr(module, "run", None)):
        _print("gate: failed")
        _print("gate_detail: artifact defines no callable run()")
        _print("stop_reason: gate_failed")
        return 2

    tests = _load_module(TESTS_PATH, "ex4_frozen_tests")
    failures = tests.run_tests(module.run)
    if failures:
        _print("gate: failed")
        for message in failures:
            _print("test: " + message)
        _print("stop_reason: gate_failed")
        return 2
    _print("tests: {} passed".format(len(tests.CASES)))

    got = module.run(list(HELD_OUT))
    diff = _held_out_diff(got, HELD_OUT_WANT)
    if diff is not None:
        _print("gate: failed")
        _print("gate_detail: held-out output != reference: " + diff)
        _print("stop_reason: gate_failed")
        return 2

    _print("gate: ok")
    big = generate_data(N_BIG, SEED_BIG)
    times = []
    for _ in range(BENCH_REPS):
        payload = list(big)          # a fresh list per rep: no identity cache
        start = time.perf_counter()
        module.run(payload)
        times.append(time.perf_counter() - start)
    _print("median_seconds: {:.6f}".format(statistics.median(times)))
    _print("reps: {}".format(BENCH_REPS))
    _print("stop_reason: done")
    return 0


def _decode(raw):
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw


def run_evaluator(candidate_path):
    """Evaluate one candidate under the budget. Returns ``(verdict, log)``.

    The subprocess is killed at ``TIME_BUDGET``; a killed run reports
    ``stop_reason: budget`` and ``median_seconds: inf`` with whatever gate
    verdict the child had already flushed (``ok`` once the gate passed, ``n/a``
    when it never got that far).
    """
    cmd = [sys.executable, "-u", os.path.abspath(__file__), "--child",
           candidate_path]
    start = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE,
                              timeout=TIME_BUDGET)
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = _decode(exc.stdout), _decode(exc.stderr), None
        timed_out = True
    wall = time.perf_counter() - start

    lines = [line for line in stdout.splitlines() if line.strip()]
    if stderr.strip():
        lines.append("# stderr: " + stderr.strip().splitlines()[0])
    if timed_out:
        lines.append("# killed at TIME_BUDGET={}s (hard wall-clock limit)".format(
            TIME_BUDGET))
    lines.append("median_seconds: {}".format(_verdict_median(stdout, timed_out)))
    lines.append("gate: {}".format(_verdict_gate(stdout, timed_out)))
    lines.append("stop_reason: {}".format(
        "budget" if timed_out else _verdict_stop_reason(stdout, code)))
    lines.append("time_budget: {}".format(TIME_BUDGET))
    lines.append("total_seconds: {:.3f}".format(wall))
    log = "# FROZEN evaluator (prepare.py) — candidate: {}\n".format(
        candidate_path) + "\n".join(lines) + "\n"

    verdict = parse_verdict(log)
    verdict["exit_code"] = code
    verdict["wall_seconds"] = wall
    verdict["timed_out"] = timed_out
    return verdict, log


def _line_value(text, key):
    for line in text.splitlines():
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def _verdict_gate(stdout, timed_out):
    gate = _line_value(stdout, "gate")
    if gate in ("ok", "failed"):
        return gate
    return "n/a"                    # killed before the gate printed a verdict


def _verdict_median(stdout, timed_out):
    if timed_out:
        return "inf"
    return _line_value(stdout, "median_seconds") or "inf"


def _verdict_stop_reason(stdout, code):
    if code != 0:
        return "gate_failed" if _verdict_gate(stdout, False) == "failed" else "error"
    return _line_value(stdout, "stop_reason") or "error"


def parse_verdict(log):
    """Read a run log (the evaluator's key: value lines) into a verdict dict.

    ``median_seconds`` is a float, or ``inf``. Never self-reported by the
    candidate — the driver calls this on the FROZEN evaluator's own output.
    """
    median_raw = _line_value(log, "median_seconds") or "inf"
    return {
        "median": float("inf") if median_raw == "inf" else float(median_raw),
        "gate": _line_value(log, "gate") or "n/a",
        "stop_reason": _line_value(log, "stop_reason") or "error",
    }


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
    print("TIME_BUDGET={}s  BENCH_REPS={}  (hard wall-clock ceiling per run)".format(
        TIME_BUDGET, BENCH_REPS))
    train = generate_data(N_BIG, SEED_BIG)
    want = reference(train)
    print("big workload: {} items / vocab {} / distinct {} / pairs {}".format(
        N_BIG, VOCAB_SIZE, len(set(train)), want["pairs"]))
    print("held-out:     {} items / distinct {} / pairs {}".format(
        N_HELD, len(set(HELD_OUT)), HELD_OUT_WANT["pairs"]))
    print("artifact:     {} (the only agent-edited file)".format(ARTIFACT))
    print("gate:         target/tests.py + exact-output on the held-out workload")
    start = time.perf_counter()
    reference(train)
    print("reference() on the big workload: {:.3f}s (one undistributed call)".format(
        time.perf_counter() - start))


def main(argv):
    parser = argparse.ArgumentParser(
        description="FROZEN ex4 evaluator — dataset summary, one run, or the "
                    "internal budget-bounded child.")
    parser.add_argument("--run", metavar="ARTIFACT",
                        help="evaluate one candidate file under TIME_BUDGET")
    parser.add_argument("--child", metavar="ARTIFACT", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child is not None:
        return _child(args.child)
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
