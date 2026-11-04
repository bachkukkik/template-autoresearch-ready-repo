"""PROTECTED verify — the only thing that can win a keep.

Measures a fixed, seeded workload over the vendored upstream module in
``target/distance.py`` (NLTK's ``nltk/metrics/distance.py``, see
``target/NOTICE``) and prints one line the engine parses:

    METRIC seconds=<median of EX5_BENCH_REPS cold reps>

The agent may not edit this file, so the workload, the seed and the rep count
are fixed. Each rep draws its inputs from ``SEED + rep``, so a candidate that
caches results keyed on its inputs gains nothing across reps.

Cold process per rep — import is charged
----------------------------------------
A rep is a **fresh child process**, timed end to end: the clock starts before
``python3 -I -c <import target + run rep>`` is spawned and stops when it exits.
Importing the module is therefore inside the timed region, so a candidate
cannot move work to import time for free (memoising the seeded pairs, building
tables, warming caches — all of it is paid, every rep).

What that does and does not buy, stated plainly: a candidate can still branch on
wall-clock introspection at import (e.g. "if this looks like a benchmark, do the
work differently"), and no timer can see that. The backstop is the guard: it
replays the *behaviour* on different seeds, in its own isolated child, against
the pristine oracle, so a shortcut that is fast because it is wrong still scores
nothing. Timing tricks that keep behaviour identical are a small constant on
this workload; correctness tricks are caught.

Environment (all optional, used by the unit tests and for a quick local probe):

    EX5_BENCH_SCALE  multiplies every workload count   (default 1.0)
    EX5_BENCH_REPS   timed repetitions, median is kept  (default 3)
    EX5_TEST_MODE    "1" allows a scale below the default; without it a shrunken
                     workload is refused (exit 2) instead of measured
"""

import inspect
import json
import os
import statistics
import subprocess
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "target" / "distance.py"

SEED = 20261028
REPS = int(os.environ.get("EX5_BENCH_REPS", "3"))
SCALE = float(os.environ.get("EX5_BENCH_SCALE", "1"))
TEST_MODE = os.environ.get("EX5_TEST_MODE") == "1"
DEFAULT_SCALE = 1.0
CHILD_TIMEOUT = 300.0

# Counts at SCALE=1.0, tuned for a ~0.6 s rep on the reference host, plus ~0.05 s
# of interpreter start-up that a cold rep pays on purpose.
PAIRS = int(6600 * SCALE)         # word -> typo, edit_distance both ways
ALIGNMENTS = int(2000 * SCALE)    # short pairs, edit_distance_align
NAMES = int(10000 * SCALE)        # name pairs, jaro + jaro_winkler
SETS = int(4000 * SCALE)          # token-set pairs, jaccard + masi

CHECKSUM_AS_INT = 1e-9

CONSONANTS = "bcdfghjklmnpqrstvwxz"
VOWELS = "aeiou"


def _word(rng, syllables):
    out = []
    for _ in range(syllables):
        out.append(rng.choice(CONSONANTS))
        out.append(rng.choice(VOWELS))
        if rng.random() < 0.35:
            out.append(rng.choice(CONSONANTS))
    return "".join(out)


def _mutate(rng, word):
    """A typo-shaped variant: substitutions, insertions and deletions."""
    chars = list(word)
    for _ in range(rng.randint(1, 3)):
        op = rng.randrange(3)
        pos = rng.randrange(len(chars))
        if op == 0:
            chars[pos] = rng.choice(CONSONANTS + VOWELS)
        elif op == 1 and len(chars) < 40:
            chars.insert(pos, rng.choice(CONSONANTS + VOWELS))
        elif len(chars) > 3:
            del chars[pos]
    return "".join(chars)


def workload(module, rng):
    """One rep: run the fixed mix and return a checksum (informational)."""
    checksum = 0

    pairs = []
    for _ in range(PAIRS):
        word = _word(rng, rng.randint(3, 6))
        pairs.append((word, _mutate(rng, word)))
    for left, right in pairs:
        checksum += module.edit_distance(left, right)
    for left, right in pairs:
        checksum += module.edit_distance(left, right, transpositions=True)

    for _ in range(ALIGNMENTS):
        left, right = _word(rng, 2), _word(rng, 2)
        checksum += len(module.edit_distance_align(left, right))

    for _ in range(NAMES):
        left = _word(rng, rng.randint(2, 4)).title()
        right = _word(rng, rng.randint(2, 4)).title()
        checksum += round(module.jaro_similarity(left, right), 9)
        checksum += round(module.jaro_winkler_similarity(left, right), 9)

    vocabulary = [_word(rng, 2) for _ in range(120)]
    for _ in range(SETS):
        left = set(rng.sample(vocabulary, rng.randint(2, 8)))
        right = set(rng.sample(vocabulary, rng.randint(2, 8)))
        checksum += round(module.jaccard_distance(left, right), 9)
        checksum += round(module.masi_distance(left, right), 9)

    return checksum


#: The rep that actually runs: import the candidate first, then the workload.
#: Its source is sent with the counts and the workload functions, so the only
#: work above the clock is JSON parsing — the import is timed.
CHILD_SOURCE = r'''
import importlib.util
import json
import os
import random
import sys

payload = json.loads(sys.stdin.read())

# Keep any output from the candidate off the reply channel.
reply = os.fdopen(os.dup(1), "w", encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr

namespace = {
    "json": json,
    "random": random,
    "CONSONANTS": payload["consonants"],
    "VOWELS": payload["vowels"],
    "PAIRS": payload["counts"]["pairs"],
    "ALIGNMENTS": payload["counts"]["alignments"],
    "NAMES": payload["counts"]["names"],
    "SETS": payload["counts"]["sets"],
}
for source in payload["workload_source"]:
    exec(source, namespace)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %r" % (path,))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    module = load(payload["module"], "ex5_target_distance")
    checksum = namespace["workload"](module, random.Random(payload["seed"]))
except BaseException as exc:
    reply.write(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}))
    reply.flush()
    sys.exit(1)

reply.write(json.dumps({"checksum": repr(checksum)}))
reply.flush()
sys.exit(0)
'''


def _child_env():
    """A minimal environment: neither the caller's flags nor its credentials."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }
    for name in ("SYSTEMROOT", "TMPDIR", "TEMP", "TMP"):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _source(function):
    return textwrap.dedent(inspect.getsource(function))


def measure_rep(rep):
    """Run rep ``rep`` in a cold child and return ``(seconds, checksum)``."""
    payload = {
        "module": str(TARGET),
        "seed": SEED + rep,
        "counts": {"pairs": PAIRS, "alignments": ALIGNMENTS,
                   "names": NAMES, "sets": SETS},
        "consonants": CONSONANTS,
        "vowels": VOWELS,
        "workload_source": [_source(_word), _source(_mutate), _source(workload)],
    }
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-I", "-c", CHILD_SOURCE],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_child_env(),
        cwd=str(ROOT),
        timeout=CHILD_TIMEOUT,
    )
    elapsed = time.perf_counter() - started

    if proc.returncode != 0 or not proc.stdout.strip():
        detail = " ".join(proc.stderr.strip().splitlines()[-5:])
        raise RuntimeError("rep %d failed (exit %d)%s"
                           % (rep, proc.returncode, (": " + detail) if detail else ""))
    answer = json.loads(proc.stdout)
    if "error" in answer:
        raise RuntimeError("rep %d: %s" % (rep, answer["error"]))
    return elapsed, float(answer["checksum"])


def main():
    if not SCALE > 0 or REPS < 1:
        print("EX5_BENCH_SCALE must be > 0 and EX5_BENCH_REPS >= 1", file=sys.stderr)
        return 2
    if not TEST_MODE and SCALE < DEFAULT_SCALE:
        print("bench: EX5_BENCH_SCALE=%g is below the default %g; the workload would "
              "be smaller than documented. Set EX5_TEST_MODE=1 to shrink it "
              "deliberately." % (SCALE, DEFAULT_SCALE), file=sys.stderr)
        return 2
    counts = {"pairs": PAIRS, "alignments": ALIGNMENTS,
              "names": NAMES, "sets": SETS}
    empty = sorted(name for name, count in counts.items() if count < 1)
    if empty:
        print("bench: EX5_BENCH_SCALE=%g leaves no work (%s would be empty); "
              "refusing to report a metric for an empty workload"
              % (SCALE, ", ".join(empty)), file=sys.stderr)
        return 2

    times = []
    for rep in range(REPS):
        try:
            elapsed, checksum = measure_rep(rep)
        except (RuntimeError, ValueError, OSError) as exc:
            print("bench: %s" % exc, file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired:
            print("bench: rep %d timed out after %gs" % (rep, CHILD_TIMEOUT),
                  file=sys.stderr)
            return 1
        times.append(elapsed)
        # stderr only: the engine reads the METRIC line, nothing else.
        print("rep %d: %.3fs checksum=%.6f" % (rep, elapsed, checksum), file=sys.stderr)

    print("METRIC seconds=%.6f" % statistics.median(times))
    return 0


if __name__ == "__main__":
    sys.exit(main())
