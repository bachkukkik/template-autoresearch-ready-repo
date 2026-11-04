"""prepare.py — FROZEN evaluator for the ex3-hotpath-speedup example.

This is the NON-ML instantiation of the karpathy/autoresearch contract:
the thing being optimized is **wall-clock time of a fixed hot-path workload**
under an **exact-output correctness gate** (the anti-Goodhart pattern).

Owned by this file, never edited during a run:
  * DATA / DATA_VAL       — the deterministic workloads (seeded, embedded)
  * RARE_WORD             — the token whose every occurrence must be located
  * run_reference(data)   — trivial reference implementation of the workload
  * EXPECTED_OUTPUT       — computed ONCE at module load from run_reference
  * EXPECTED_OUTPUT_VAL   — same for the held-out workload
  * check(...)            — the exact-output gate (== on the dict)
  * benchmark(reps=5)     — median wall-seconds of train.run(data)
  * evaluate(train_module)-> (median_seconds, gate_ok)
  * TIME_BUDGET = 60      — seconds, wall clock, per candidate run

WORKLOAD CONTRACT (train.py must implement exactly this)

    run(data: str) -> dict

All word operations are performed on ``data.lower()``; a *word* is a maximal
run of ASCII letters (``[a-z]+``).  Positions are character offsets into that
lowercased text (identical to offsets in ``data`` because the alphabet is
ASCII, so lowercasing preserves length).  The returned dict has EXACTLY these
keys:

    total_chars      int    len(data)
    word_count       int    number of word tokens
    top50            list   50 x [word, count], sorted by (-count, word asc)
    by_initial       dict   {first_letter: number_of_tokens_starting_with_it}
    longest_word     str    longest token; ties -> lexicographically smallest
    palindrome_count int    number of token OCCURRENCES that read the same
                            backwards (multiplicity counts, not unique words)
    rare_positions   list   every offset where the rare word occurs, ascending
    rare_count       int    len(rare_positions)

Gate: ``run(data) == EXPECTED_OUTPUT`` (dict equality), and — because
exact_gate implies full rigor — also ``run(DATA_VAL) == EXPECTED_OUTPUT_VAL``
on the held-out workload (integrity guard against data-specific shortcuts).

Exit contract for train.py: 0 = gate passed, 2 = gate failed (invalid, never a
keep), 3 = gate passed but median > TIME_BUDGET.
"""
import inspect
import os
import random
import re
import statistics
import sys
import time
from collections import Counter

# --------------------------------------------------------------- constants --
TIME_BUDGET = 60          # seconds, wall clock, per candidate run
BENCH_REPS = 5            # median over 5 timed calls of train.run(data)
SEED = 1234               # train workload seed
SEED_VAL = 99999          # held-out workload seed (disjoint)
N_TOKENS = 2_000_000      # tokens in the train workload
N_TOKENS_VAL = 500_000    # tokens in the held-out workload
N_RARE = 200              # injected occurrences of the rare word
RARE_WORD = "zorblat"     # never generable from the vocabulary (asserted)

# --------------------------------------------------------------- workload ---
# Deterministic, seeded procedural text. Labeled in README.md as an honest
# stand-in for a real hot-path document workload (self-contained, reproducible).
_A = ["kra", "zor", "mik", "tal", "run", "nel",
      "lov", "vit", "sha", "gru", "pem", "dor"]
_B = ["", "n", "k", "l", "m", "s", "t", "r"]
_C = ["", "ix", "ath", "ek", "ost", "um"]
_PUNCT = [",", ".", ";", "!", "?", ":", '"', "(", ")", "-", "'"]
# A fixed slice of genuinely palindromic tokens, so palindrome_count is a
# non-degenerate aggregate (a wrong palindrome rule must fail the gate).
_PALINDROMES = ["radar", "level", "solos", "kayak", "minim", "deified"]
assert all(w == w[::-1] for w in _PALINDROMES)


def _build_vocab():
    vocab = []
    seen = set()
    for a in _A:
        for b in _B:
            for c in _C:
                w = a + b + c
                if w not in seen:
                    seen.add(w)
                    vocab.append(w)
    return vocab


_BASE_VOCAB = _build_vocab()          # 576-ish distinct words
_VOCAB = _BASE_VOCAB + _PALINDROMES
_BAG = _VOCAB + _PUNCT
# Zipf-ish word weights, a fixed mid weight per palindrome, and a punctuation
# mass tuned to ~3% of the stream.
_WORD_W = ([1.0 / ((i + 1) ** 1.1) for i in range(len(_BASE_VOCAB))]
           + [0.05] * len(_PALINDROMES))
_PUNCT_W = 0.03 * sum(_WORD_W) / (len(_PUNCT) * 0.97)
_WEIGHTS = _WORD_W + [_PUNCT_W] * len(_PUNCT)

# The rare word must be un-generable: not in the vocabulary, and not a
# substring of any vocabulary word (so every substring hit is a real token).
assert RARE_WORD not in _VOCAB
assert not any(RARE_WORD in w for w in _VOCAB)
_RARE_TOKEN = RARE_WORD.capitalize()   # injected with a capital Z


def generate_data(n_tokens, seed):
    """Seeded token stream joined by single spaces (deterministic)."""
    rng = random.Random(seed)
    tokens = rng.choices(_BAG, weights=_WEIGHTS, k=n_tokens)
    for j in sorted(rng.sample(range(n_tokens), N_RARE)):
        tokens[j] = _RARE_TOKEN
    return " ".join(tokens) + "\n"


DATA = generate_data(N_TOKENS, SEED)
DATA_VAL = generate_data(N_TOKENS_VAL, SEED_VAL)

# ------------------------------------------------------- reference impl -----
WORD_RE = re.compile(r"[a-z]+")
RARE_RE = re.compile(RARE_WORD)


def _token_positions(text):
    """Offsets of rare-word TOKENS (word-boundary truth, for the self-check)."""
    low = text.lower()
    return [m.start() for m in WORD_RE.finditer(low) if m.group() == RARE_WORD]


def run_reference(data):
    """Trivial reference implementation of the workload. FROZEN.

    Deliberately straightforward (findall + Counter); it defines truth, it is
    not the thing being optimized.
    """
    low = data.lower()
    words = WORD_RE.findall(low)
    counter = Counter(words)
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    positions = [m.start() for m in RARE_RE.finditer(low)]
    return {
        "total_chars": len(data),
        "word_count": len(words),
        "top50": [[w, c] for w, c in ranked[:50]],
        "by_initial": dict(Counter(w[0] for w in words)),
        "longest_word": min(words, key=lambda w: (-len(w), w)),
        "palindrome_count": sum(1 for w in words if w == w[::-1]),
        "rare_positions": positions,
        "rare_count": len(positions),
    }


EXPECTED_OUTPUT = run_reference(DATA)
EXPECTED_OUTPUT_VAL = run_reference(DATA_VAL)

# Gate self-check: the substring shortcut used by fast candidates must agree
# with word-boundary truth on this workload (construction guarantee).
assert EXPECTED_OUTPUT["rare_positions"] == _token_positions(DATA)
assert EXPECTED_OUTPUT_VAL["rare_positions"] == _token_positions(DATA_VAL)
assert EXPECTED_OUTPUT["rare_count"] == N_RARE
assert len(EXPECTED_OUTPUT["top50"]) == 50

_KEYS = tuple(EXPECTED_OUTPUT)

# ------------------------------------------------------------------ gate ----
# A candidate may not reach into the frozen truth: returning EXPECTED_OUTPUT
# (or a mutated copy of it) would pass the gate trivially and be "infinitely
# fast". The evaluator rejects any train module that names it.
_FORBIDDEN = ("EXPECTED_OUTPUT", "expected_output", "run_reference")


def _forbidden_reference(train_module):
    try:
        src = inspect.getsource(train_module)
    except Exception:
        return None
    for name in _FORBIDDEN:
        if name in src:
            return name
    return None


def _preview(value):
    if isinstance(value, (list, tuple)):
        return f"{type(value).__name__}[{len(value)}] head={list(value[:3])!r}"
    if isinstance(value, dict):
        items = list(value.items())[:3]
        return f"dict[{len(value)}] {{ {items!r} ... }}"
    return repr(value)


def _describe_mismatch(out, expected):
    if not isinstance(out, dict):
        print(f"gate: output is {type(out).__name__}, expected dict")
        return
    missing = sorted(set(expected) - set(out))
    extra = sorted(set(out) - set(expected))
    if missing:
        print(f"gate: missing keys {missing}")
    if extra:
        print(f"gate: unexpected keys {extra}")
    for k in sorted(set(expected) & set(out)):
        if out[k] != expected[k]:
            print(f"gate: key {k!r} differs "
                  f"(got {_preview(out[k])} vs want {_preview(expected[k])})")


def _one_run(train_module, data, expected, label):
    try:
        out = train_module.run(data)
    except Exception as exc:                      # noqa: BLE001 (report, don't raise)
        print(f"gate[{label}]: run() raised {type(exc).__name__}: {exc}")
        return False
    if out == expected:
        return True
    print(f"gate[{label}]: output != expected")
    _describe_mismatch(out, expected)
    return False


def check(train_module, exact_gate=True, held_out=True, verbose=True):
    """Exact-output gate. Returns True iff the candidate is VALID.

    exact_gate=True  -> full rigor: exact dict equality (the contract).
    exact_gate=False -> structural only (same keys, same value types); a
                        diagnostic mode, never used to grant a keep.
    held_out=True    -> additionally require the held-out workload to match
                        (integrity guard: blocks data-specific shortcuts).

    Fresh copies of the workload strings are used, so an identity-keyed cache
    cannot be smuggled in; the module is also screened for references to the
    frozen truth.
    """
    bad = _forbidden_reference(train_module)
    if bad is not None:
        print(f"gate: REJECT — train.py references frozen truth ({bad!r})")
        return False
    data = bytes(DATA, "ascii").decode("ascii")        # guaranteed fresh object
    if not exact_gate:
        try:
            out = train_module.run(data)
        except Exception as exc:                       # noqa: BLE001
            print(f"gate: run() raised {type(exc).__name__}: {exc}")
            return False
        ok = (isinstance(out, dict) and set(out) == set(_KEYS)
              and all(type(out[k]) is type(EXPECTED_OUTPUT[k]) for k in _KEYS))
        if verbose:
            print(f"gate: structural check -> {'ok' if ok else 'FAIL'}")
        return ok
    if not _one_run(train_module, data, EXPECTED_OUTPUT, "train"):
        return False
    if held_out:
        val = bytes(DATA_VAL, "ascii").decode("ascii")
        if not _one_run(train_module, val, EXPECTED_OUTPUT_VAL, "held-out"):
            return False
    if verbose:
        print("gate: exact match on {} run(s)".format("2" if held_out else "1"))
    return True


# ------------------------------------------------------------- benchmark ----
def _import_train_run():
    """benchmark() with no run_fn: use the sibling train.py in this repo."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import train                                   # noqa: PLC0415
    return train.run


def benchmark(reps=BENCH_REPS, run_fn=None, data=None):
    """Median wall-seconds of `reps` calls to train.run(data).

    Each timed rep gets a FRESH, value-equal copy of the workload so an
    identity-keyed memo cache cannot turn the loop into a no-op.
    """
    if run_fn is None:
        run_fn = _import_train_run()
    payload = bytes(DATA, "ascii").decode("ascii") if data is None else data
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        run_fn(payload)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def evaluate(train_module, reps=BENCH_REPS):
    """(median_seconds, gate_ok) for a candidate train module.

    gate_ok is the exact-output gate and NOTHING else. When the gate fails the
    candidate is invalid (train.py exits 2): the returned median is a single
    diagnostic rep so the ledger can show how fast the wrong answer was, and
    it is never eligible for a keep.
    """
    if not check(train_module, exact_gate=True, held_out=True):
        try:
            fast = benchmark(reps=1, run_fn=train_module.run)
        except Exception:                          # noqa: BLE001
            fast = float("inf")
        return (fast, False)
    return (benchmark(reps=reps, run_fn=train_module.run), True)


# ------------------------------------------------------------------ main ----
if __name__ == "__main__":
    print(f"TIME_BUDGET={TIME_BUDGET}s  BENCH_REPS={BENCH_REPS}")
    print(f"train: {len(DATA)} chars / {EXPECTED_OUTPUT['word_count']} tokens "
          f"/ {len(EXPECTED_OUTPUT['top50'])} top rows "
          f"/ rare={EXPECTED_OUTPUT['rare_count']}")
    print(f"held-out: {len(DATA_VAL)} chars / "
          f"{EXPECTED_OUTPUT_VAL['word_count']} tokens")
    print(f"initials: {len(EXPECTED_OUTPUT['by_initial'])}  "
          f"longest={EXPECTED_OUTPUT['longest_word']!r}  "
          f"palindromes={EXPECTED_OUTPUT['palindrome_count']}  "
          f"total_chars={EXPECTED_OUTPUT['total_chars']}")

    ref_module = type("RefModule", (), {"run": staticmethod(run_reference)})()
    t0 = time.perf_counter()
    ref_median = benchmark(reps=3, run_fn=run_reference)
    print(f"reference median ({3} reps): {ref_median:.3f}s "
          f"(setup {time.perf_counter() - t0:.2f}s)")
    print(f"gate self-test (reference impl): "
          f"{check(ref_module, exact_gate=True, held_out=True)}")
