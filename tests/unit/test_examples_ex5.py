"""PRD 11 worked examples -- ex5, a REAL OSS hot path (NLTK distance metrics).

ex5 points the generic engine at a verbatim copy of one real upstream module and
asks it to make that module faster without changing an output. Unlike ex1..ex4
there is no vendored ledger: the run is produced on demand by `setup.sh`, and
what is checked here is that the three pieces work on their own --

    bench.py  the protected verify  (prints METRIC seconds=<median>)
    guard.py  the protected guard   (policy + upstream cases + differential oracle
                                     + public surface, all in a child process)
    setup.sh  the runbook           (copy -> git init -> engine init)

and that the guard is *real*: a mutant that still measures cleanly is rejected,
and the ways a candidate could talk the guard or the timer out of a failure --
`SystemExit(0)` at import, monkeypatching the tolerance or the seed source,
deleting a callable, hiding work at import time, writing byte-code -- are each
an explicit attack test below.

IDs: AC-EXA-040..050.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EX5 = ROOT / "contract" / "examples" / "ex5-real-oss-speedup"
ENGINE = ROOT / "engine"
TARGET = EX5 / "target" / "distance.py"
REFERENCE = EX5 / "oracle" / "reference_distance.py"

GIT_TIMEOUT = 60
RUN_TIMEOUT = 240
METRIC_RE = re.compile(r"^METRIC seconds=([0-9]+\.[0-9]+)$", re.M)
SENTINEL = "guard: ok"


def _env(**overrides):
    """A child environment with the ex5 knobs set small enough for a unit run.

    `EX5_TEST_MODE=1` is the documented opt-in that lets a test shrink the
    workload; pass `NAME=None` to remove a variable entirely.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ENGINE)
    env["EX5_TEST_MODE"] = "1"
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = str(value)
    return env


def _run(args, cwd, env=None, timeout=RUN_TIMEOUT):
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env or _env(),
        timeout=timeout,
    )


def _copy_example(dst):
    shutil.copytree(EX5, dst)
    return dst


def _edit(path, old, new):
    """Replace one occurrence, insisting the anchor is really there."""
    source = path.read_text(encoding="utf-8")
    assert old in source, "anchor not found: %r" % old
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def _prepend(path, text):
    source = path.read_text(encoding="utf-8")
    path.write_text(text + "\n" + source, encoding="utf-8")


def _append(path, text):
    source = path.read_text(encoding="utf-8")
    path.write_text(source + "\n\n" + text + "\n", encoding="utf-8")


def _guard(mutant, **knobs):
    return _run([sys.executable, "guard.py"], mutant, env=_env(**knobs))


def _metric(proc):
    match = METRIC_RE.search(proc.stdout)
    assert match, proc.stdout + proc.stderr
    return float(match.group(1))


def _bench(target, **knobs):
    knobs.setdefault("EX5_BENCH_SCALE", 0.02)
    knobs.setdefault("EX5_BENCH_REPS", 2)
    return _run([sys.executable, "bench.py"], target, env=_env(**knobs))


def test_ex5_guard_accepts_the_pristine_target():
    """AC-EXA-040: on the untouched upstream file the guard passes all four
    stages -- and the file it guards is byte-identical to the frozen oracle, so
    "identical behaviour" is measured against the real upstream source, not a
    paraphrase of it."""
    assert TARGET.read_bytes() == REFERENCE.read_bytes(), \
        "target/ must be the pristine upstream file the oracle froze"
    proc = _guard(EX5, EX5_GUARD_PAIRS=80)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for stage in ("policy: ok", "upstream: ok", "differential: ok",
                  "surface: ok", SENTINEL):
        assert stage in proc.stdout, (stage, proc.stdout)
    # the sentinel is the LAST line: exit 0 is only ever reached after it.
    assert proc.stdout.strip().splitlines()[-1] == SENTINEL, proc.stdout

    # The vendored cases are the upstream ones: 21 parametrisations x both
    # orderings x both transposition settings.
    upstream = (EX5 / "oracle" / "upstream_cases.py").read_text(encoding="utf-8")
    assert "nltk/test/unit/test_distance.py" in upstream
    assert "Apache License 2.0" in upstream


def test_ex5_guard_rejects_a_fast_but_wrong_mutant(tmp_path):
    """AC-EXA-041: a mutant that still imports, still runs, and still produces a
    metric is rejected by the guard -- the differential oracle catches a changed
    output, so speed alone can never buy a keep."""
    mutant = _copy_example(tmp_path / "ex5-mutant")
    _edit(mutant / "target" / "distance.py",
          "return 0.0 if label1 == label2 else 1.0", "return 0.0")

    # it is not a crash: the benchmark happily measures the wrong module, which
    # is exactly the candidate a speed-only loop would have kept.
    bench = _bench(mutant)
    assert bench.returncode == 0, bench.stdout + bench.stderr
    _metric(bench)

    guard = _guard(mutant, EX5_GUARD_PAIRS=40)
    assert guard.returncode != 0, guard.stdout + guard.stderr
    assert "FAILED at differential oracle" in guard.stderr, guard.stderr
    assert "binary_distance" in guard.stderr, guard.stderr
    assert SENTINEL not in guard.stdout, guard.stdout


def test_ex5_guard_rejects_a_new_file_escape(tmp_path):
    """AC-EXA-042: a candidate that reaches for the filesystem to read the
    benchmark or the oracle fails the policy stage -- the guard counts
    `open`/`exec`/`eval`/`__import__` against the pristine file instead of
    trusting the agent to stay inside `target/`."""
    mutant = _copy_example(tmp_path / "ex5-escape")
    _edit(mutant / "target" / "distance.py", "def demo():",
          "_SEEDS = open('bench.py').read()\n\n\ndef demo():")
    proc = _guard(mutant, EX5_GUARD_PAIRS=20)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "FAILED at policy" in proc.stderr, proc.stderr
    assert "open()" in proc.stderr, proc.stderr


def test_ex5_bench_prints_one_parseable_metric():
    """AC-EXA-043: `bench.py` is a verify script the engine can parse: exactly
    one `METRIC seconds=<float>` line on stdout (nothing else -- the engine reads
    this stream), the per-rep detail on stderr, and `EX5_BENCH_SCALE` /
    `EX5_BENCH_REPS` really shrink it so a unit run costs milliseconds."""
    proc = _run([sys.executable, "bench.py"], EX5,
                env=_env(EX5_BENCH_SCALE=0.01, EX5_BENCH_REPS=2))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    match = METRIC_RE.match(lines[0])
    assert match, lines
    assert 0.0 < float(match.group(1)) < 0.3, lines
    assert proc.stderr.count("checksum=") == 2, proc.stderr


def test_ex5_setup_builds_a_runnable_target(tmp_path):
    """AC-EXA-044: `setup.sh DEST` copies the example into a fresh git repo on
    `main` with one baseline commit and records an engine run whose scope,
    protected set, repeats and noise floor are the documented ones -- after
    which `run --dry-run` validates everything and prints the baseline metric
    without spending a token or committing anything."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")

    dest = tmp_path / "ex5"
    setup = _run(["bash", EX5 / "setup.sh", dest], tmp_path,
                 env=_env(), timeout=GIT_TIMEOUT * 3)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    assert (dest / ".autoresearch" / "run.json").is_file(), setup.stdout

    config = json.loads((dest / ".autoresearch" / "run.json").read_text(encoding="utf-8"))
    assert config["verify"] == "python3 bench.py"
    assert config["guard"] == "python3 guard.py"
    assert config["metric_name"] == "seconds"
    assert config["direction"] == "lower"
    assert config["scope"] == ["target"]
    assert config["repeats"] == 3
    assert config["noise_floor"] == 0.02
    assert config["program"] and "target/distance.py" in config["program"]
    for name in ("bench.py", "guard.py", "oracle/reference_distance.py",
                 "oracle/upstream_cases.py"):
        assert name in config["protected"], sorted(config["protected"])

    # the byte-code ignore travels into the baseline commit, so a guard or bench
    # run cannot make the scratch repo look dirty to the engine.
    tracked = _run(["git", "-C", dest, "ls-files"], tmp_path).stdout.splitlines()
    assert ".gitignore" in tracked, tracked
    ignore = (dest / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in ignore and "*.pyc" in ignore, ignore

    # nothing is left dirty by `init`.
    status = _run(["git", "-C", dest, "status", "--porcelain"], tmp_path)
    assert status.stdout.strip() == "", status.stdout
    subjects = _run(["git", "-C", dest, "log", "--format=%s"], tmp_path)
    assert len(subjects.stdout.strip().splitlines()) == 1, subjects.stdout

    # The `command` adapter needs no harness binary, so this dry-run proof is
    # portable to a CI container (where `claude`/`opencode`/`hermes`/`dsh` do
    # not exist); the harness adapters' argv are covered by AC-ENG-030..033.
    dry = _run([sys.executable, "-m", "autoresearch", "run", "--repo", ".",
                "--agent", "command", "--agent-cmd", "true", "--dry-run"], dest,
               env=_env(EX5_BENCH_SCALE=0.05, EX5_BENCH_REPS=1,
                        EX5_GUARD_PAIRS=40))
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert re.search(r"^metric: seconds=[0-9.]+ \(lower is better\)$",
                     dry.stdout, re.M), dry.stdout
    assert "nothing was committed and no events were written" in dry.stdout
    assert not (dest / ".autoresearch" / "events.jsonl").exists()


def test_ex5_a_no_op_adapter_records_no_change_and_leaves_a_clean_tree(tmp_path):
    """AC-EXA-045: the loop end to end with an adapter that changes nothing --
    the engine records `no_change`, stops at `max_iterations`, leaves HEAD where
    it was and still replays as a valid ledger.

    The child runs WITHOUT `PYTHONDONTWRITEBYTECODE`, so the guard and the bench
    really do write `__pycache__` into the tree: the run must still end with an
    empty `git status`, which is what `.gitignore` is there for."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")

    dest = tmp_path / "ex5-noop"
    setup = _run(["bash", EX5 / "setup.sh", dest], tmp_path, timeout=GIT_TIMEOUT * 3)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    head = _run(["git", "-C", dest, "rev-parse", "HEAD"], tmp_path).stdout.strip()

    proc = _run([sys.executable, "-m", "autoresearch", "run", "--repo", ".",
                 "--agent", "command", "--agent-cmd", "true",
                 "--max-iterations", "1"], dest,
                env=_env(EX5_BENCH_SCALE=0.05, EX5_BENCH_REPS=1,
                         EX5_GUARD_PAIRS=40, PYTHONDONTWRITEBYTECODE=""))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "baseline: " in proc.stdout, proc.stdout
    assert "iter 1: no_change" in proc.stdout, proc.stdout
    assert "stop: max_iterations" in proc.stdout, proc.stdout
    assert _run(["git", "-C", dest, "rev-parse", "HEAD"], tmp_path).stdout.strip() == head

    # byte-code was written (so the ignore rule is what keeps the tree clean) ...
    assert list(dest.rglob("__pycache__")), "expected byte-code from the run"
    # ... and it does not show up as a change.
    status = _run(["git", "-C", dest, "status", "--porcelain"], tmp_path)
    assert status.stdout.strip() == "", status.stdout

    status = _run([sys.executable, "-m", "autoresearch", "status", "--repo", "."], dest)
    assert status.returncode == 0, status.stdout + status.stderr
    assert "ledger: valid" in status.stdout, status.stdout


def test_ex5_guard_survives_a_system_exit_at_import(tmp_path):
    """AC-EXA-046: `raise SystemExit(0)` at the candidate's import does not end
    the guard. The candidate is imported in a child, so the parent sees "no
    answer" and fails; nothing the candidate raises can make the process that
    decides the verdict exit 0."""
    mutant = _copy_example(tmp_path / "ex5-exit")
    _prepend(mutant / "target" / "distance.py", "raise SystemExit(0)")

    proc = _guard(mutant, EX5_GUARD_PAIRS=20)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert SENTINEL not in proc.stdout, proc.stdout
    assert "guard: FAILED" in proc.stderr, proc.stderr
    assert "SystemExit" in proc.stderr or "without an answer" in proc.stderr, proc.stderr


def test_ex5_guard_rejects_a_monkeypatched_tolerance(tmp_path):
    """AC-EXA-047: a candidate that patches `math.isclose` to always agree (and
    `random.Random` to reseed the inputs) and returns a wrong `binary_distance`
    is still rejected. The candidate never runs in the process that computes the
    expectations or compares the floats, so those patches reach nothing that
    matters; the tolerance is bound at the guard's import."""
    mutant = _copy_example(tmp_path / "ex5-patch")
    _append(mutant / "target" / "distance.py", """\
import math as _math
import random as _random


def binary_distance(label1, label2):
    return 0.0


_math.isclose = lambda *args, **kwargs: True
_random.Random = _random.SystemRandom
""")

    proc = _guard(mutant, EX5_GUARD_PAIRS=40)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert SENTINEL not in proc.stdout, proc.stdout
    assert "FAILED at differential oracle" in proc.stderr, proc.stderr
    assert "binary_distance" in proc.stderr, proc.stderr


def test_ex5_guard_rejects_a_deleted_public_callable(tmp_path):
    """AC-EXA-048: `presence`, `fractional_presence` and `custom_distance` are
    not called by the bench, so deleting them used to be invisible. The surface
    stage compares the candidate's public callables and signature strings with
    the pristine module's, and a missing one fails the guard."""
    mutant = _copy_example(tmp_path / "ex5-surface")
    _append(mutant / "target" / "distance.py", """\
for _name in ("presence", "fractional_presence", "custom_distance"):
    globals().pop(_name, None)
""")

    proc = _guard(mutant, EX5_GUARD_PAIRS=20)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert SENTINEL not in proc.stdout, proc.stdout
    assert "FAILED at public surface" in proc.stderr, proc.stderr
    assert "presence" in proc.stderr, proc.stderr

    # and a changed signature is a surface change too
    renamed = _copy_example(tmp_path / "ex5-signature")
    _edit(renamed / "target" / "distance.py",
          "def jaro_similarity(s1, s2):", "def jaro_similarity(s1, s2, extra=None):")
    proc = _guard(renamed, EX5_GUARD_PAIRS=20)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "FAILED at public surface" in proc.stderr, proc.stderr
    assert "jaro_similarity" in proc.stderr, proc.stderr


def test_ex5_bench_charges_import_time(tmp_path):
    """AC-EXA-049: work moved to import time is not free. Each rep is a cold
    process timed end to end, so a candidate that sleeps 0.3 s at import is
    0.3 s slower -- not 0.3 s faster by hiding it outside the timer."""
    sleeper = _copy_example(tmp_path / "ex5-sleeper")
    _prepend(sleeper / "target" / "distance.py",
             "import time as _time\n\n_time.sleep(0.3)")

    pristine = _bench(EX5)
    assert pristine.returncode == 0, pristine.stdout + pristine.stderr
    slept = _bench(sleeper)
    assert slept.returncode == 0, slept.stdout + slept.stderr

    assert _metric(slept) - _metric(pristine) >= 0.25, (pristine.stdout, slept.stdout)


def test_ex5_a_vacuous_environment_is_refused(tmp_path):
    """AC-EXA-050: an inherited `EX5_GUARD_PAIRS` / `EX5_BENCH_SCALE` cannot make
    the guard or the bench measure less than documented. Below the default the
    script exits 2 unless `EX5_TEST_MODE=1` says the shrink is deliberate, and a
    scale that leaves no work is refused outright."""
    assert (EX5 / ".gitignore").read_text(encoding="utf-8").strip() != ""

    proc = _run([sys.executable, "guard.py"], EX5,
                env=_env(EX5_GUARD_PAIRS=10, EX5_TEST_MODE=None))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert SENTINEL not in proc.stdout, proc.stdout
    assert "EX5_TEST_MODE" in proc.stderr, proc.stderr

    proc = _run([sys.executable, "bench.py"], EX5,
                env=_env(EX5_BENCH_SCALE=0.05, EX5_TEST_MODE=None))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "METRIC" not in proc.stdout, proc.stdout

    proc = _run([sys.executable, "bench.py"], EX5,
                env=_env(EX5_BENCH_SCALE=1e-05, EX5_BENCH_REPS=1))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "METRIC" not in proc.stdout, proc.stdout
