"""PROTECTED guard — a candidate that changes behaviour never gets a score.

Exit 0 only if all four stages pass:

1. policy      every ``.py`` under ``target/`` imports stdlib only and does not
               reach for the filesystem, the network, the oracle copy or an
               interpreter escape (no ``open``/``exec``/``eval``/``__import__``).
2. upstream    the vendored upstream test cases for ``edit_distance`` (NLTK's
               ``nltk/test/unit/test_distance.py``, retargeted at the candidate).
3. differential the candidate's output is compared with the frozen pristine copy
               ``oracle/reference_distance.py`` over seeded random inputs and a
               list of hand-picked edge cases, across every public function.
4. surface     the candidate still exposes every public callable the pristine
               module exposes, with an unchanged signature string.

The oracle copy is pristine upstream source, so "identical behaviour" is decided
against the real thing, not against a paraphrase of it. Floats may differ in the
last bits (an agent is allowed to reassociate arithmetic); everything else is
compared exactly, including the integer type a distance must return.

Isolation (why the guard cannot be talked out of a failure)
-----------------------------------------------------------
The candidate is **never imported into this process**. Every call it answers is
made in a separate, isolated child (``python3 -I``, minimal environment, a
timeout, JSON on stdin/stdout). This guard therefore cannot be ended early by
``raise SystemExit(0)`` at the candidate's import, and the candidate cannot
monkeypatch the reference module, ``math.isclose`` or ``random.Random`` — it
never gets to run in the process that computes expectations or compares. The
parent builds its inputs with its own ``Random`` and its own pristine oracle
*before* the child is spawned; the child only reports what the candidate
returned. Exceptions are behaviour: a call that raises is recorded as
``EXC:<TypeName>`` and must match the oracle's outcome.

Success requires an explicit stage counter to reach the number of stages, and
the final ``guard: ok`` line is printed only then — one line before exit 0. Any
``BaseException`` escaping the guard's own body (``SystemExit`` and
``KeyboardInterrupt`` included) exits 1.

Environment (optional):

    EX5_GUARD_PAIRS  random input pairs for the differential stage (default 250)
    EX5_GUARD_SEED   seed for those inputs (default 815)
    EX5_TEST_MODE    "1" lets the unit tests shrink the workload; without it a
                     pairs value below the default is refused (exit 2) rather
                     than silently measuring less
"""

import ast
import importlib.util
import inspect
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET_DIR = ROOT / "target"
TARGET = TARGET_DIR / "distance.py"
REFERENCE = ROOT / "oracle" / "reference_distance.py"

DEFAULT_PAIRS = 250
PAIRS = int(os.environ.get("EX5_GUARD_PAIRS", str(DEFAULT_PAIRS)))
SEED = int(os.environ.get("EX5_GUARD_SEED", "815"))
TEST_MODE = os.environ.get("EX5_TEST_MODE") == "1"
FLOAT_TOLERANCE = 1e-12
MAX_REPORTED = 6
CHILD_TIMEOUT = 240.0

#: Bound at import time, so nothing that runs later can swap the tolerance.
_isclose = math.isclose

#: Every stage that must complete, in order. Exit 0 needs all of them.
STAGES = ("policy", "upstream", "differential", "surface")
SENTINEL = "guard: ok"

FORBIDDEN_MODULES = {
    "bench", "builtins", "ctypes", "gc", "glob", "guard", "importlib", "io",
    "marshal", "oracle", "os", "pathlib", "pickle", "reference_distance",
    "shutil", "socket", "subprocess", "sys", "tempfile", "upstream_cases",
}
FORBIDDEN_CALLS = {
    "__import__", "breakpoint", "compile", "eval", "exec", "input", "open",
}
FORBIDDEN_ATTRIBUTES = {
    "__builtins__", "__code__", "__globals__", "__loader__", "__spec__",
    "__subclasses__",
}
#: Primitives a candidate may not use MORE often than the pristine copy does.
WATCHED = FORBIDDEN_CALLS | FORBIDDEN_ATTRIBUTES

# Pairs the random stream alone would rarely produce: empty, one-sided, repeats,
# transpositions, non-ASCII, emoji, whitespace, long, and the textbook pair.
EDGE_CASES = [
    ("", ""), ("", "a"), ("a", ""), ("a", "a"), ("a", "b"), ("ab", "ba"),
    ("abc", "cba"), ("aa", "aa"), ("aaaa", "aaa"), ("aab", "aba"),
    ("abcabc", "acbacb"), ("naïve", "naive"), ("café", "cafe"),
    ("straße", "strasse"), ("漢字", "漢字"), ("漢字", "汉字"), ("🙂a", "a🙂"),
    ("a b", "ab"), ("kitten", "sitting"), ("Saturday", "Sunday"),
    ("", "abcdefghij"), ("abcdefghij", ""),
    ("aaaaaaaaaaaaaaaaaaaa", "aaaaaaaaaaaaaaaaaaaa"),
    ("abcabcabcabcabcabcabc", "cbacbacbacbacbacbacba"),
    ("x" * 120, "x" * 120), ("x" * 120, "x" * 60 + "y" * 60),
]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s as module %r" % (path, name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ─── value codec (one definition, shared with the child by source) ───────────


def encode_value(value):
    """Encode a value as JSON-safe data that can be compared across processes.

    Scalars keep their ``repr`` (floats full precision, ints as text), containers
    keep their type, sets are sorted so two processes agree on the order. A
    result the codec does not know is quoted by type and repr.
    """
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", repr(int(value))]
    if isinstance(value, float):
        return ["float", repr(value)]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [encode_value(item) for item in value]]
    if isinstance(value, (set, frozenset)):
        items = [encode_value(item) for item in value]
        items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return [type(value).__name__, items]
    return ["obj", type(value).__qualname__, repr(value)]


def _decode_literal(spec):
    """Decode an encoded *argument* into the value the candidate will receive."""
    kind = spec[0]
    if kind == "int":
        return int(spec[1])
    if kind == "float":
        return float(spec[1])
    if kind == "bool":
        return bool(spec[1])
    if kind == "str":
        return spec[1]
    if kind == "list":
        return [_decode_literal(item) for item in spec[1]]
    if kind == "tuple":
        return tuple(_decode_literal(item) for item in spec[1])
    if kind == "set":
        return {_decode_literal(item) for item in spec[1]}
    if kind == "frozenset":
        return frozenset(_decode_literal(item) for item in spec[1])
    if kind == "obj":
        raise ValueError("an argument may not be encoded as 'obj'")
    raise ValueError("unknown argument encoding %r" % (kind,))


def same(got, want):
    """Behaviour equality between two encoded results.

    Exact for ints/strings/lists/sets (an ``int`` must stay ``int``, a ``bool``
    is not an ``int``), 1e-12 for floats, and an exception must be the same
    exception type. ``want`` is always the pristine oracle's encoded result.
    """
    if not isinstance(want, list) or not isinstance(got, list):
        return got == want
    kind = want[0]
    if kind == "bool":
        return got[0] == "bool" and bool(got[1]) == bool(want[1])
    if kind == "int":
        try:
            return got[0] == "int" and int(got[1]) == int(want[1])
        except (TypeError, ValueError, IndexError):
            return False
    if kind == "float":
        if got[0] not in ("float", "int"):
            return False
        try:
            return _isclose(float(got[1]), float(want[1]),
                            rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE)
        except (TypeError, ValueError, IndexError, OverflowError):
            return False
    if kind in ("list", "tuple", "set", "frozenset"):
        if got[0] != kind or len(got[1]) != len(want[1]):
            return False
        return all(same(one, other) for one, other in zip(got[1], want[1]))
    return got == want


# ─── the isolated child that runs the candidate ──────────────────────────────

CHILD_SOURCE = r'''
import importlib.util
import json
import os
import sys

payload = json.loads(sys.stdin.read())

# The candidate may print; keep its output off the reply channel.
reply = os.fdopen(os.dup(1), "w", encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %r" % (path,))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode(spec):
    kind = spec[0]
    if kind == "int":
        return int(spec[1])
    if kind == "float":
        return float(spec[1])
    if kind == "bool":
        return bool(spec[1])
    if kind == "str":
        return spec[1]
    if kind == "list":
        return [decode(item) for item in spec[1]]
    if kind == "tuple":
        return tuple(decode(item) for item in spec[1])
    if kind == "set":
        return {decode(item) for item in spec[1]}
    if kind == "frozenset":
        return frozenset(decode(item) for item in spec[1])
    raise ValueError("unknown argument encoding %r" % (kind,))


namespace = {"json": json}
exec(payload["encode_source"], namespace)
encode = namespace[payload["encode_name"]]


def surface(module):
    import inspect

    found = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        try:
            value = getattr(module, name)
        except BaseException:
            continue
        if not callable(value):
            continue
        try:
            found[name] = str(inspect.signature(value))
        except (TypeError, ValueError):
            found[name] = "<no signature>"
    return found


def answer(module, call):
    try:
        function = getattr(module, call["fn"])
        args = [decode(arg) for arg in call.get("args", [])]
        kwargs = {key: decode(value) for key, value in call.get("kwargs", {}).items()}
        return encode(function(*args, **kwargs))
    except BaseException as exc:                      # a raise is behaviour
        return ["exc", type(exc).__name__]


def finish(payload_out, code):
    reply.write(json.dumps(payload_out))
    reply.flush()
    sys.exit(code)


try:
    module = load(payload["module"], payload["module_name"])
except BaseException as exc:
    finish({"import_error": "%s: %s" % (type(exc).__name__, exc)}, 1)

out = {"results": [answer(module, call) for call in payload.get("calls", [])]}
if payload.get("surface"):
    try:
        out["surface"] = surface(module)
    except BaseException as exc:
        finish({"error": "surface: %s: %s" % (type(exc).__name__, exc)}, 1)
finish(out, 0)
'''


def _child_env():
    """A minimal environment: nothing from the caller's session leaks in."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }
    for name in ("SYSTEMROOT", "TMPDIR", "TEMP", "TMP"):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def run_child(module_path, calls, *, surface=False, timeout=CHILD_TIMEOUT):
    """Run ``calls`` against the candidate in an isolated child.

    Returns ``(payload, error)``; ``payload`` is the child's decoded reply and
    ``error`` is a human-readable reason when the child did not answer properly.
    """
    payload = {
        "module": str(module_path),
        "module_name": "ex5_candidate_distance",
        "encode_source": inspect.getsource(encode_value),
        "encode_name": encode_value.__name__,
        "calls": calls,
        "surface": bool(surface),
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", CHILD_SOURCE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=_child_env(),
            cwd=str(ROOT),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "the candidate did not finish within %gs" % timeout
    except OSError as exc:
        return None, "could not start the candidate child: %s" % exc

    if not proc.stdout.strip():
        detail = " ".join(proc.stderr.strip().splitlines()[-3:])
        return None, ("the candidate child exited %d without an answer%s"
                      % (proc.returncode, (": " + detail) if detail else ""))
    try:
        answer = json.loads(proc.stdout)
    except ValueError:
        detail = " ".join(proc.stdout.strip().splitlines()[:3])
        return None, "the candidate child did not answer in JSON: %r" % detail
    if "import_error" in answer:
        return None, "the candidate does not import: %s" % answer["import_error"]
    if "error" in answer:
        return None, "the candidate child failed: %s" % answer["error"]
    if "results" not in answer:
        return None, "the candidate child answered without results"
    if len(answer["results"]) != len(calls):
        return None, ("the candidate child answered %d of %d calls"
                      % (len(answer["results"]), len(calls)))
    return answer, None


# ─── stage 1: policy ─────────────────────────────────────────────────────────


def _module_violations(path):
    """Imports that are never allowed, in any file of the candidate."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return ["%s: does not parse: %s" % (path.name, exc)], None

    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    bad.append("%s:%d imports %r" % (path.name, node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            base = (node.module or "").split(".")[0]
            if node.level or base in FORBIDDEN_MODULES:
                bad.append("%s:%d imports from %r" % (path.name, node.lineno, node.module))
    return bad, tree


def _watchlist(tree):
    """Count the escape primitives in one module (``open``, ``exec``, ...)."""
    found = {}
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            name = node.attr
        if name in WATCHED:
            found[name] = found.get(name, 0) + 1
    return found


def check_policy(reference_source):
    """Policy: no dangerous import, and no NEW file or interpreter escape.

    Upstream's own ``custom_distance`` calls ``open``, so the rule is not "no
    ``open`` anywhere" — it is "no more of these primitives than the pristine
    copy has". A candidate that keeps the upstream code and adds a second
    ``open`` (to read ``bench.py``, the oracle, or a precomputed table) fails.
    """
    files = sorted(TARGET_DIR.rglob("*.py"))
    if TARGET not in files:
        return ["%s is missing" % TARGET.relative_to(ROOT)]

    violations = []
    upstream = _watchlist(ast.parse(reference_source, filename=str(REFERENCE)))
    used = {}
    for path in files:
        bad, tree = _module_violations(path)
        violations += bad
        if tree is None:
            continue
        for name, count in _watchlist(tree).items():
            used[name] = used.get(name, 0) + count

    for name in sorted(used):
        allowed = upstream.get(name, 0)
        if used[name] > allowed:
            violations.append(
                "target adds %d use(s) of %s() (the pristine copy has %d)"
                % (used[name] - allowed, name, allowed)
            )
    return violations


# ─── stage 2: the vendored upstream cases ────────────────────────────────────


def upstream_calls():
    """The vendored cases as (child call, expected encoded result) pairs."""
    cases = load_module(ROOT / "oracle" / "upstream_cases.py", "ex5_upstream_cases")
    calls, expected, labels = [], [], []
    for left, right, substitution_cost, expecteds in cases.CASES:
        for s1, s2 in ((left, right), (right, left)):
            for want, transpositions in zip(expecteds, (True, False)):
                calls.append({
                    "fn": "edit_distance",
                    "args": [["str", s1], ["str", s2]],
                    "kwargs": {
                        "substitution_cost": ["int", repr(substitution_cost)],
                        "transpositions": ["bool", transpositions],
                    },
                })
                expected.append(encode_value(want))
                labels.append(
                    "edit_distance(%r, %r, substitution_cost=%r, transpositions=%r)"
                    % (s1, s2, substitution_cost, transpositions)
                )
    return calls, expected, labels


# ─── stage 3: differential oracle ────────────────────────────────────────────

ALPHABETS = ("ab", "abc ", "abcdefghij", "aeioubcdfg", "aé漢 ", "ab🙂")


def _text(rng, alphabet, length):
    return "".join(rng.choice(alphabet) for _ in range(length))


def _pair(rng):
    alphabet = rng.choice(ALPHABETS)
    length = rng.choice((0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 90))
    left = _text(rng, alphabet, length)
    style = rng.randrange(3)
    if style == 0:
        right = _text(rng, alphabet, length)
    elif style == 1:
        chars = list(left)
        for _ in range(rng.randint(1, 4)):
            if chars and rng.random() < 0.5:
                chars[rng.randrange(len(chars))] = rng.choice(alphabet)
            elif chars:
                del chars[rng.randrange(len(chars))]
            else:
                chars.append(rng.choice(alphabet))
        right = "".join(chars)
    else:
        right = left[::-1] if rng.random() < 0.5 else left * rng.randint(1, 2)
    return left, right


def differential_calls(reference):
    """Build the calls and the oracle's answers, in this process, from pristine code.

    The inputs come from this process's own ``random.Random``; the expectations
    come from the pristine oracle imported here and never from the candidate.
    """
    calls, expected, labels, failures = [], [], [], []

    def add(fn, *args, **kwargs):
        call = {
            "fn": fn,
            "args": [encode_value(arg) for arg in args],
            "kwargs": {key: encode_value(value) for key, value in kwargs.items()},
        }
        label = "%s%r%s" % (fn, args, ("".join(
            ", %s=%r" % item for item in kwargs.items())) if kwargs else "")
        try:
            want = getattr(reference, fn)(*args, **kwargs)
        except Exception as exc:                      # noqa: BLE001 - the oracle is pristine
            failures.append("%s: the ORACLE raised %s: %s"
                            % (label, type(exc).__name__, exc))
            return
        calls.append(call)
        expected.append(encode_value(want))
        labels.append(label)

    pairs = EDGE_CASES + [_pair(random.Random(SEED + index)) for index in range(PAIRS)]
    for left, right in pairs:
        add("edit_distance", left, right)
        add("edit_distance", right, left)
        add("edit_distance", left, right, substitution_cost=3)
        add("edit_distance", left, right, transpositions=True)
        add("edit_distance", right, left, transpositions=True)
        add("edit_distance", left, right, substitution_cost=2, transpositions=True)
        add("edit_distance_align", left, right)
        add("jaro_similarity", left, right)
        add("jaro_winkler_similarity", left, right)
        add("jaro_winkler_similarity", left, right, 0.2, 3)

    rng = random.Random(SEED + 1)
    vocabulary = [_text(rng, "abcdefgh", 4) for _ in range(40)]
    for _ in range(PAIRS):
        left = set(rng.sample(vocabulary, rng.randint(1, 8)))
        right = set(rng.sample(vocabulary, rng.randint(1, 8)))
        add("jaccard_distance", left, right)
        add("masi_distance", left, right)
        add("binary_distance", left, right)

    for _ in range(PAIRS):
        left, right = rng.randint(-50, 50), rng.randint(-50, 50)
        add("interval_distance", left, right)
        add("binary_distance", left, right)

    return calls, expected, labels, failures


# ─── stage 4: the public surface ─────────────────────────────────────────────


def public_surface(module):
    """``{name: signature-string}`` for every public callable of a module."""
    found = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        try:
            value = getattr(module, name)
        except Exception:                             # noqa: BLE001 - a hostile getattr
            continue
        if not callable(value):
            continue
        try:
            found[name] = str(inspect.signature(value))
        except (TypeError, ValueError):
            found[name] = "<no signature>"
    return found


def compare_surface(wanted, got):
    """Missing or changed public callables. Extra ones are not a behaviour change."""
    failures = []
    for name in sorted(wanted):
        if name not in got:
            failures.append("public %s() is missing (the pristine module has it)" % name)
        elif got[name] != wanted[name]:
            failures.append("public %s was%s, the pristine module has %s"
                            % (name, got[name], wanted[name]))
    return failures


# ─── entry point ─────────────────────────────────────────────────────────────


def run():
    """The stages, with an explicit counter; ``None`` means "all stages passed"."""
    completed = []

    def fail(stage, message, details):
        print("guard: FAILED at %s" % stage, file=sys.stderr)
        print("  - " + message, file=sys.stderr)
        for detail in details[:MAX_REPORTED]:
            print("  - " + detail, file=sys.stderr)
        return 1

    violations = check_policy(REFERENCE.read_text(encoding="utf-8"))
    if violations:
        return fail("policy", "%d violation(s)" % len(violations), violations)
    completed.append("policy")
    print("policy: ok")

    calls, expected, labels = upstream_calls()
    answer, error = run_child(TARGET, calls)
    if error is not None:
        return fail("upstream cases", error, [])
    failures = [
        "%s: got %r, upstream expects %r" % (labels[index], answer["results"][index], expected[index])
        for index in range(len(calls))
        if not same(answer["results"][index], expected[index])
    ]
    if failures:
        return fail("upstream cases", "%d of %d mismatched" % (len(failures), len(calls)),
                    failures)
    completed.append("upstream")
    print("upstream: ok (%d evaluations)" % len(calls))

    # Pristine code only, in this process, before the candidate runs anywhere.
    reference = load_module(REFERENCE, "ex5_reference_distance")
    wanted_surface = public_surface(reference)

    calls, expected, labels, oracle_failures = differential_calls(reference)
    if oracle_failures:
        return fail("differential oracle", "the oracle could not produce expectations",
                    oracle_failures)

    answer, error = run_child(TARGET, calls, surface=True)
    if error is not None:
        return fail("differential oracle", error, [])
    failures = [
        "%s: got %r, upstream %r" % (labels[index], answer["results"][index], expected[index])
        for index in range(len(calls))
        if not same(answer["results"][index], expected[index])
    ]
    if failures:
        return fail("differential oracle",
                    "%d of %d comparisons mismatched" % (len(failures), len(calls)),
                    failures)
    completed.append("differential")
    print("differential: ok (%d comparisons against the pristine oracle)" % len(calls))

    surface_failures = compare_surface(wanted_surface, answer.get("surface") or {})
    if surface_failures:
        return fail("public surface", "%d callable(s) changed" % len(surface_failures),
                    surface_failures)
    completed.append("surface")
    print("surface: ok (%d callables, signatures unchanged)" % len(wanted_surface))

    if completed != list(STAGES):
        print("guard: FAILED — %d of %d stages completed (%s)"
              % (len(completed), len(STAGES), ", ".join(completed) or "none"),
              file=sys.stderr)
        return 1

    print(SENTINEL)
    return 0


def main():
    """Exit 1 on ANY escape from the stages — ``SystemExit(0)`` included."""
    try:
        return run()
    except BaseException as exc:                      # noqa: BLE001 - exit 1, always
        print("guard: FAILED with an uncaught %s: %s" % (type(exc).__name__, exc),
              file=sys.stderr)
        return 1


def _entry():
    if not TEST_MODE and PAIRS < DEFAULT_PAIRS:
        print("guard: EX5_GUARD_PAIRS=%d is below the default %d; the differential "
              "stage would be weaker than documented. Set EX5_TEST_MODE=1 to shrink "
              "it deliberately." % (PAIRS, DEFAULT_PAIRS), file=sys.stderr)
        return 2
    if PAIRS < 1:
        print("guard: EX5_GUARD_PAIRS must be >= 1", file=sys.stderr)
        return 2
    return main()


if __name__ == "__main__":
    sys.exit(_entry())
