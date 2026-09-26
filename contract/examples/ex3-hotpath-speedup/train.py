"""train.py — the ONLY agent-edited file (ex3-hotpath-speedup).

Contract: implement ``run(data) -> dict`` exactly as specified in prepare.py.
Gate: the frozen evaluator compares ``run(data)`` against its frozen reference
result — exact dict equality — and runs the same check on a held-out workload.
Speed only counts when the gate passes.

Baseline (as-shipped): deliberately suboptimal but correct — a per-character
cleanup loop, one full token pass per starting letter, a per-offset occurrence
scan, character-by-character palindrome tests, and a duplicated tokenize.
"""
import re
import sys
import time
from collections import Counter
from operator import itemgetter

import prepare

RARE = prepare.RARE_WORD
WORD_RE = re.compile(r"[a-z]+")
RARE_RE = re.compile(RARE)


def normalize(data):
    """Naive: one Python step per character of the document."""
    return "".join(c if c.isalpha() else " " for c in data.lower())


def count_words(words):
    """Naive per-token dict accumulation."""
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return counts


def by_initial(words):
    """One pass: a Counter over first characters."""
    return Counter(map(itemgetter(0), words))


def top_n(counts, n):
    """Top n by (count desc, word asc)."""
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[w, c] for w, c in ranked[:n]]


def longest_word(words):
    """Longest token; ties broken lexicographically."""
    best = ""
    for w in words:
        if len(w) > len(best) or (len(w) == len(best) and w < best):
            best = w
    return best


def palindrome_count(words):
    """Naive: compare each token from both ends, character by character."""
    n = 0
    for w in words:
        ok = True
        for i in range(len(w) // 2):
            if w[i] != w[-1 - i]:
                ok = False
                break
        if ok:
            n += 1
    return n


def rare_positions(low):
    """One C-level substring scan over the already-lowercased document."""
    return [m.start() for m in RARE_RE.finditer(low)]


def run(data):
    """WORKLOAD: the pure function the ledger times (lower is better)."""
    low = data.lower()
    words = WORD_RE.findall(low)
    counts = Counter(words)
    rare = rare_positions(low)
    return {
        "total_chars": len(data),   # naive per-character loop
        "word_count": len(words),      # tokenize a second time
        "top50": top_n(counts, 50),
        "by_initial": by_initial(words),
        "longest_word": min(counts, key=lambda w: (-len(w), w)),
        "palindrome_count": sum(c for w, c in counts.items() if w == w[::-1]),
        "rare_positions": rare,
        "rare_count": len(rare),
    }


def main():
    """Run the frozen evaluator against this module and print the ledger lines.

    Exit contract: 0 = gate passed inside budget, 2 = gate failed (invalid),
    3 = gate passed but the median exceeds TIME_BUDGET.
    """
    t0 = time.perf_counter()
    median, gate_ok = prepare.evaluate(sys.modules[__name__])
    elapsed = time.perf_counter() - t0
    print(f"reps: {prepare.BENCH_REPS}")
    print(f"median_seconds: {median:.6f}")
    print(f"gate_ok: {gate_ok}")
    print(f"time_budget: {prepare.TIME_BUDGET}")
    print(f"total_seconds: {elapsed:.3f}")
    if not gate_ok:
        return 2
    if median > prepare.TIME_BUDGET:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())