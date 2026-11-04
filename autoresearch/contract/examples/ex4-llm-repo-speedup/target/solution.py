"""solution.py -- optimized implementation of the target repo's contract.

Strategy (all single-pass / near-linear in the input size):

  * one ``Counter`` pass over ``items`` gives every per-value count;
  * ``pairs`` is the closed form sum over values of C(count, 2);
  * ``groups`` counts values with count >= 2 in the same loop;
  * ``top`` / ``largest`` come from ``heapq.nsmallest(10, ...)`` ordered by
    the contract's (-count, value) key -- no full sort of the distinct set;
  * ``first_repeat`` is a single scan with a ``seen`` set: the first index
    whose value already appeared.

Contract: ``run(items) -> dict`` as specified in target/README.md.
"""
from collections import Counter
from heapq import nsmallest


def run(items):
    """Linear-time implementation of the target repo's contract."""
    counts = Counter(items)

    pairs = 0
    groups = 0
    for count in counts.values():
        if count >= 2:
            groups += 1
            pairs += count * (count - 1) // 2

    if counts:
        best = nsmallest(10, counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top = [[value, count] for value, count in best]
        largest = [best[0][0], best[0][1]]
    else:
        top = []
        largest = []

    seen = set()
    first_repeat = -1
    for j, value in enumerate(items):
        if value in seen:
            first_repeat = j
            break
        seen.add(value)

    return {
        "pairs": pairs,
        "groups": groups,
        "largest": largest,
        "top": top,
        "first_repeat": first_repeat,
    }


if __name__ == "__main__":
    print(run(["b", "a", "b", "a", "a"]))
