"""solution_baseline.py -- the reconstructed BASELINE of the one agent-edited
file (ex4-llm-repo-speedup).

The tracked ``target/solution.py`` is the FINAL kept state of the worked run;
this file is the state the run started from. ``agent_driver.py --from-baseline``
copies this file over ``target/solution.py`` before it replays anything, so a
scratch clone starts from the same baseline the live run did.

The baseline is deliberately naive -- correct, but quadratic (or worse) in the
size of the input, so it cannot finish the timed workload inside
``prepare.TIME_BUDGET``:

  * ``pairs`` and ``first_repeat`` scan every ANCHOR PAIRS -- O(n^2);
  * the per-value counts re-scan the whole list once per distinct value -- O(n*d);
  * the ranking is an ordinary sort over that list of pairs.

Contract: ``run(items) -> dict`` as specified in target/README.md.
"""
from collections import Counter


def run(items):
    """Naive-but-correct implementation of the target repo's contract."""
    n = len(items)

    # O(n^2): compare every pair.
    pairs = 0
    for i in range(n):
        left = items[i]
        for j in range(i + 1, n):
            if left == items[j]:
                pairs += 1

    # O(n * distinct): one full rescan of the input per distinct value.
    values = []
    for value in items:
        if value not in values:
            values.append(value)
    counts = []
    for value in values:
        count = 0
        for other in items:
            if other == value:
                count += 1
        counts.append([value, count])

    ranked = sorted(counts, key=lambda pair: (-pair[1], pair[0]))
    top = [list(pair) for pair in ranked[:10]]
    largest = list(ranked[0]) if ranked else []
    groups = sum(1 for _, count in counts if count >= 2)

    first_repeat = -1
    for j in range(n):
        for i in range(j):
            if items[i] == items[j]:
                first_repeat = j
                break
        if first_repeat != -1:
            break

    return {
        "pairs": pairs,
        "groups": groups,
        "largest": largest,
        "top": top,
        "first_repeat": first_repeat,
    }


if __name__ == "__main__":
    print(run(["b", "a", "b", "a", "a"]))
