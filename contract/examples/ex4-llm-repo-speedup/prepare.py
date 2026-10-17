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
  * run_evaluator()  — spawns that subprocess, draws ONE fresh ``secrets`` seed
                       per timed rep AFTER the child's import handshake, sends
                       only that seed, times the round trip itself, verifies the
                       output against a reference it computed BEFORE sending the
                       seed, kills the whole process group at ``TIME_BUDGET`` and
                       reports ``stop_reason: budget``
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

TIMING is parent-side too, one rep at a time. The parent chooses a fresh
benchmark seed with ``secrets.randbits`` for EACH rep, computes
``reference(generate_data(N_BIG, seed))`` BEFORE it sends anything so reference
time is excluded from the window, writes ONLY that seed to the child's stdin,
starts its own ``perf_counter``, waits for the child's output record for THAT
seed (a record for another seed, or one already read before this seed was sent,
is never a match), stops its clock, and verifies the output against the
reference it computed. The recorded median is the median of the PARENT's
per-rep seconds; the child's own opinion of how long it took is never read (the
protocol carries no ``seconds`` field at all). Because the seed for rep k does
not exist until the parent sends it, a workload precomputed at import time — or
a clock the candidate patched — cannot make a rep look faster; the window is
the parent's own wall clock around the round trip. The metric is therefore
**parent wall time per rep, including the child's workload generation
(``generate_data``) and the IPC**. That generation cost is identical for every
candidate, so it is a constant overhead that keeps comparisons valid rather than
a bias. The whole bench stays bounded by ``TIME_BUDGET`` (the process-group kill
is unchanged), and the parent never blocks forever: every wait polls against the
overall deadline.

RESIDUAL RISK (honest, by design). Both the correctness signal and the speed
number are parent-measured and cannot be forged. What remains is that the
evaluated artifact is arbitrary Python run **unsandboxed with the caller's
privileges** — it can read files, spawn processes and consume the machine
(there is no container here). Run live loops only in a disposable
sandbox/VM with no host mounts and no credentials; that is this template's
stance on running model-written code. A wall-clock delta within ~10% is not
signal, so the ledger's keep/discard decisions must not be read as precise.

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
a private HOME), and the whole group is killed on EVERY exit path (a clean
``os._exit(0)`` included), so the evaluated code never inherits the caller's API
key and never leaves an orphan behind.

Stdlib only — no pytest, no third-party packages.
"""
import argparse
import importlib.util
import json
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
BENCH_REPS = 3             # median over 3 parent-timed reps (one fresh seed each)
SAMPLE_SEED = 20261017     # the --summary display workload only; reps are fresh
SEED_HELD = 424242         # held-out workload seed (disjoint)
N_BIG = 60_000             # items in each timed workload
N_HELD = 3_000             # items in the held-out gate workload
VOCAB_SIZE = 4_000         # distinct strings in the generated corpus
DIRECTION = "lower"        # lower median seconds is better
ARTIFACT = os.path.join("target", "solution.py")
POLL_INTERVAL = 0.001      # how often the parent re-reads the results channel

# The results channel is a one-way stream the CANDIDATE can also append to, so
# it is a resource a hostile artifact can flood. The parent reads it
# incrementally (an offset, never a whole-file re-read) and caps both the bytes
# and the records it will keep: past either cap the run is a crash, not a slow
# win (`_judge`: `overflow` -> `stop_reason: error`).
CHANNEL_MAX_BYTES = 8 * 1024 * 1024     # 8 MiB
CHANNEL_MAX_RECORDS = 1000

# The child's report channel: one JSON record per line, written to a path the
# parent creates. The parent reads ONLY the stages below -- a line the candidate
# adds is ignored unless it is one of them, and an ``output`` record is judged by
# comparing it against ``reference(...)``, never by believing it.
STAGE_IMPORTED = "imported"     # handshake: the candidate module has been imported
STAGE_GATE = "gate_failed"      # a child-side failure (screen/no run/raise/tests)
STAGE_TESTS = "tests"           # the frozen suite's result (extra child-side check)
STAGE_OUTPUT = "output"         # one raw run(items) output for a parent-known input
STAGE_READY = "ready"           # the child is blocked on stdin, waiting for a seed

# The evaluated child gets ONLY these variables from the caller's environment.
# Secrets (OPENAI_API_KEY and friends) are deliberately absent: the candidate
# is model-written code and must not be able to read the caller's credentials.
CHILD_ENV_PASSTHROUGH = ("PATH", "PYTHONPATH", "PYTHONHASHSEED", "SYSTEMROOT")

# The sentinel a channel returns when no matching record exists yet.
_MISSING = object()


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


def fresh_seed():
    """One fresh benchmark seed, drawn by the parent just before it is sent.

    ``secrets`` (not the module's fixed ``random`` stream), and handed to the
    child one rep at a time: the seed for rep k does not exist until the parent
    writes it to the child's stdin, so the workload for that rep cannot be
    precomputed at import time or reused from an earlier rep.
    """
    return secrets.randbits(64)


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
# output would pass the gate trivially and be "infinitely fast". This screen is
# a BEST-EFFORT substring tripwire against ACCIDENTAL oracle use -- a two-token
# bypass (`importlib.import_module('pre'+'pare')`) defeats it, and copying a
# correct implementation is not a gate forgery anyway (the output is genuinely
# correct). It is NOT a security boundary: the real defence is the parent-side
# comparison (a wrong output is a failed gate whatever the source said), and the
# reason a live loop belongs in a disposable sandbox is that the artifact runs
# unsandboxed, not that this screen can be trusted.
FORBIDDEN = ("import prepare", "from prepare", "prepare.reference")


# ------------------------------------------------------------- the harness --
def screen_source(path):
    """Return a rejection message when the artifact reaches for frozen truth.

    Best-effort only (see ``FORBIDDEN``): it catches the accidental, first-order
    use of the oracle's name, nothing more.
    """
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


def _kill_group(proc, pgid=None):
    """SIGKILL the child's whole process group (it has its own session).

    A plain ``proc.kill()`` leaves grandchildren (anything the candidate
    spawned) running as orphans, still burning the machine after the budget.
    ``pgid`` is the group captured BEFORE the child was reaped: once it exits,
    ``os.getpgid(proc.pid)`` raises, so a kill on the clean-exit path needs the
    captured id to still reach a candidate's orphaned grandchildren. Guarded so
    an already-dead group is fine.
    """
    if pgid is None:
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, OSError):
            pgid = None
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except (ProcessLookupError, OSError):
        pass


# --------------------------------------------------- the results channel -----
class _Channel:
    """Incremental reader of the child's JSON results channel.

    Reads only the bytes appended since the last poll (an offset, never a
    whole-file re-read), and caps the bytes and the records it will keep. Past
    either cap ``overflow`` is set and the run is treated as a crash.
    """

    def __init__(self, path, max_bytes=CHANNEL_MAX_BYTES,
                 max_records=CHANNEL_MAX_RECORDS):
        self.path = path
        self.max_bytes = max_bytes
        self.max_records = max_records
        self.offset = 0
        self.bytes = 0
        self._buffer = b""
        self.records = []
        self.overflow = False

    def poll(self):
        """Read and parse whatever was appended since the last poll."""
        remaining = self.max_bytes - self.bytes
        if remaining <= 0:              # already at the cap: never read again
            self.overflow = True
            return
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read(remaining + 1)   # one byte past the cap is enough
        except OSError:
            chunk = b""
        if not chunk:
            return
        self.offset += len(chunk)
        self.bytes += len(chunk)
        if self.bytes > self.max_bytes:
            self.overflow = True
            return
        self._buffer += chunk
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            record = self._parse(line)
            if record is not None:
                self.records.append(record)
        if len(self.records) >= self.max_records:
            self.overflow = True

    @staticmethod
    def _parse(line):
        text = line.strip()
        if not text:
            return None
        try:
            record = json.loads(text.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return record if isinstance(record, dict) else None

    def stage(self, stage):
        """True when a record with this stage has been read."""
        return any(record.get("stage") == stage for record in self.records)

    def bench(self, seed):
        """The first bench record the child wrote for ``seed`` (else _MISSING).

        A record for another seed, or one already read before this seed was
        sent, is never a match.
        """
        for record in self.records:
            if (record.get("stage") == STAGE_OUTPUT
                    and record.get("name") == "bench"
                    and record.get("seed") == seed):
                return record.get("output")
        return _MISSING


def _await(channel, proc, deadline, predicate):
    """Poll ``channel`` until ``predicate`` is true, the child is gone, or the
    overall deadline. Never blocks forever."""
    while time.perf_counter() < deadline:
        channel.poll()
        if predicate():
            return True
        if proc.poll() is not None:      # the child is gone; stop waiting
            break
        time.sleep(POLL_INTERVAL)
    channel.poll()
    return predicate()


def _await_imported(channel, proc, deadline):
    """Wait for the child's import handshake (the fresh seeds come after it)."""
    return _await(channel, proc, deadline,
                  lambda: channel.stage(STAGE_IMPORTED))


def _await_ready(channel, proc, deadline):
    """Wait for the child's ready signal: it is blocked on stdin for a seed.

    Waiting for this BEFORE the first seed keeps the child's own tests/held-out
    phase out of the timed window. An overflowing channel returns False.
    """
    if channel.overflow:
        return False
    return _await(channel, proc, deadline,
                  lambda: channel.stage(STAGE_READY) or channel.overflow) \
        and not channel.overflow


def _await_bench(channel, proc, deadline, seed):
    """Wait for the child's output record for ``seed`` (else _MISSING).

    Polls against the overall deadline, so a hung child cannot wedge the
    parent; an overflowing channel ends the wait immediately.
    """
    while time.perf_counter() < deadline:
        channel.poll()
        if channel.overflow:
            return _MISSING
        output = channel.bench(seed)
        if output is not _MISSING:
            return output
        if proc.poll() is not None:
            break
        time.sleep(POLL_INTERVAL)
    channel.poll()
    return channel.bench(seed)


def _send_seed(proc, seed):
    """Write ONE fresh seed to the child's stdin. False when the child is gone.

    A dead child raises BrokenPipe — nothing to send, and the judge will see no
    output for that seed — so the error is swallowed rather than aborting.
    """
    try:
        proc.stdin.write(json.dumps({"seed": seed}) + "\n")
        proc.stdin.flush()
        return True
    except (BrokenPipeError, OSError, ValueError, AttributeError):
        return False


def _close_stdin(proc):
    """Close the child's stdin (end of the seed stream), guarding a closed one.

    ``communicate()``/``wait()`` would flush a still-attached stdin and raise on
    a closed one, so detach it now that the seeds are written.
    """
    if proc.stdin is None:
        return
    try:
        proc.stdin.close()
    except (BrokenPipeError, OSError, ValueError):
        pass
    proc.stdin = None


def _read_seed():
    """The next seed the parent sends, one JSON line per rep (None on EOF).

    Parsed strictly: a malformed or non-integer line ends the seed stream
    rather than being coerced.
    """
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = data.get("seed")
    if isinstance(data, int) and not isinstance(data, bool) and data >= 0:
        return data
    return None


def _child(candidate_path, results_path):
    """One evaluated run: screen -> import -> tests -> held-out -> timed reps.

    The child writes JSON records to ``results_path`` for the PARENT to judge:
    a handshake once the candidate is imported, the frozen suite's result, the
    raw ``run()`` output on the held-out workload, a ready signal, and the raw
    ``run()`` output for each seed the parent sends — ONE seed per line, read
    in turn. It reports no gate, no keep and no timing: the parent measures the
    per-rep wall clock itself. stdout is a human-readable log and nothing else.

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

    # Handshake. The parent draws and sends the fresh benchmark seeds ONLY
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

    # Ready: from here the parent sends ONE fresh seed per rep and measures the
    # round trip (workload generation + run + IPC) with its OWN clock.
    emit({"stage": STAGE_READY})
    _print("ready: waiting for benchmark seeds")
    reported = 0
    while True:
        seed = _read_seed()
        if seed is None:
            break                # stdin closed by the parent: the stream is done
        payload = generate_data(N_BIG, seed)
        try:
            got = module.run(payload)
        except Exception as exc:                    # noqa: BLE001
            return fail("run(bench seed {}) raised {}: {}".format(
                seed, type(exc).__name__, exc))
        emit({"stage": STAGE_OUTPUT, "name": "bench", "seed": seed,
              "output": _canonical(got)})
        _print("bench seed {}: output reported".format(seed))
        reported += 1
    _print("done: {} benchmark(s) reported".format(reported))
    return 0


def _judge(records, bench_times, wants, code, timed_out, overflow):
    """The PARENT's verdict, from its own comparison of the child's outputs.

    ``bench_times[seed]`` is the PARENT's own wall time for that rep (the
    child's opinion of its speed is never read); ``wants[seed]`` is the
    reference output the parent computed BEFORE it sent the seed. A mismatch, a
    child-reported gate failure, a missing output, an overflowing channel or a
    non-zero exit is a failure or a crash — never a keep. A timeout always wins:
    median ``inf``, ``budget``, with ``gate: ok`` when the held-out outputs
    delivered first all matched.
    """
    inf = float("inf")
    failed = None
    held_out_seen = False
    held_out_ok = False
    bench_ok = set()
    for record in records:
        stage = record.get("stage")
        if stage == STAGE_GATE:
            failed = failed or str(
                record.get("detail") or "child-side gate failure")
        elif stage == STAGE_TESTS:
            failures = record.get("failures")
            if failures:
                failed = failed or "frozen tests: " + str(failures[0])
        elif stage == STAGE_OUTPUT and record.get("name") == "held_out":
            held_out_seen = True
            if record.get("output") == HELD_OUT_WANT:
                held_out_ok = True
            else:
                diff = _held_out_diff(record.get("output"), HELD_OUT_WANT) or ""
                failed = failed or "held-out output != reference: " + diff
        elif stage == STAGE_OUTPUT and record.get("name") == "bench":
            seed = record.get("seed")
            if seed not in wants:
                continue            # a rep the parent never seeded: ignore it
            if record.get("output") == wants[seed]:
                bench_ok.add(seed)
            else:
                failed = failed or "bench output != reference (seed {})".format(seed)

    any_output = held_out_seen or bool(bench_times)
    if timed_out:
        gate = "failed" if failed else ("ok" if held_out_ok else "n/a")
        return {"median": inf, "gate": gate, "stop_reason": "budget"}
    if overflow:
        return {"median": inf, "gate": "n/a", "stop_reason": "error"}
    if failed is not None:
        return {"median": inf, "gate": "failed", "stop_reason": "gate_failed"}
    if not any_output or not held_out_seen:
        return {"median": inf, "gate": "n/a", "stop_reason": "error"}
    if code != 0 or len(bench_times) != len(wants) or bench_ok != set(wants):
        return {"median": inf, "gate": "ok", "stop_reason": "error"}
    return {"median": statistics.median(bench_times.values()),
            "gate": "ok", "stop_reason": "done"}


def run_evaluator(candidate_path):
    """Evaluate one candidate under the budget. Returns ``(verdict, log)``.

    The child runs with its own process group and a scrubbed environment. The
    parent draws ONE fresh ``secrets`` seed per rep, computes ``reference`` on
    that seed's workload BEFORE sending it (so reference time is outside the
    window), writes only that seed to the child's stdin, starts its own
    ``perf_counter``, waits for the child's output record for THAT seed, stops
    its clock and verifies the output against the reference it computed. The
    recorded median is the median of the PARENT's per-rep seconds — the child's
    own timing is never read. At ``TIME_BUDGET`` the whole process group is
    killed (on every exit path) and the verdict is ``median_seconds: inf`` /
    ``stop_reason: budget``.
    """
    candidate_path = os.path.abspath(candidate_path)
    start = time.perf_counter()
    deadline = start + TIME_BUDGET
    timed_out = False
    code = None
    bench_times = {}                # seed -> the PARENT's own seconds for that rep
    wants = {}                      # seed -> reference output, computed pre-send
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
            try:
                pgid = os.getpgid(proc.pid)     # capture before it is reaped
            except (ProcessLookupError, OSError):
                pgid = None
            channel = _Channel(results_path)
            try:
                # Handshake, then ready: the fresh seeds exist only after the
                # child has imported the candidate AND finished its own
                # tests/held-out phase, so nothing precomputes a workload and no
                # other child work lands inside a timed rep.
                if _await_imported(channel, proc, deadline) \
                        and _await_ready(channel, proc, deadline):
                    for _ in range(BENCH_REPS):
                        if time.perf_counter() >= deadline:
                            timed_out = True
                            break
                        seed = fresh_seed()
                        # Computed BEFORE the seed is sent: its cost is outside
                        # the parent's window and the parent owns the truth.
                        wants[seed] = reference(generate_data(N_BIG, seed))
                        if time.perf_counter() >= deadline:
                            timed_out = True
                            break
                        if not _send_seed(proc, seed):
                            break
                        sent = time.perf_counter()
                        output = _await_bench(channel, proc, deadline, seed)
                        received = time.perf_counter()
                        if output is _MISSING:
                            if received >= deadline:
                                timed_out = True
                            break
                        bench_times[seed] = received - sent
                _close_stdin(proc)
                try:
                    proc.wait(timeout=max(0.0, deadline - time.perf_counter()))
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _kill_group(proc, pgid)
                    proc.wait()
            finally:
                # Reach any grandchild the candidate left behind on EVERY exit
                # path — a clean os._exit(0) after spawning one must not leak a
                # running process.
                _kill_group(proc, pgid)
            channel.poll()
            verdict = _judge(channel.records, bench_times, wants, code,
                             timed_out, channel.overflow)
        with open(log_path, encoding="utf-8") as fh:
            child_out = fh.read()
    wall = time.perf_counter() - start

    lines = [line for line in child_out.splitlines() if line.strip()]
    if timed_out:
        lines.append("# killed at TIME_BUDGET={}s (whole process group)".format(
            TIME_BUDGET))
    lines.append("# verdict: the parent's own comparison of the child's reported "
                 "run() outputs and its own per-rep wall clock; child exit={}"
                 .format("timeout" if timed_out else code))
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
    print("held-out:     {} items / distinct {} / pairs {:.0f}".format(
        N_HELD, len(set(HELD_OUT)), HELD_OUT_WANT["pairs"]))
    print("artifact:     {} (the only agent-edited file)".format(ARTIFACT))
    print("gate:         the PARENT's own run(held_out) == reference comparison "
          "(target/tests.py is an extra child-side check)")
    print("timing:       the PARENT's own wall clock per rep (one fresh "
          "secrets seed per rep, sent over the child's stdin)")
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
