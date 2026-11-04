"""tests.py -- the FROZEN test suite of the target repo (ex4).

This file is part of the target software repo and is READ-ONLY for the run: the
agent edits ``target/solution.py`` only. The suite is the correctness gate --
``prepare.py`` runs it in the budget-bounded child process and a single failing
case makes the candidate invalid (never a keep).

Standard library only, no pytest: ``run_tests(run)`` returns a list of
human-readable failure strings (empty list == all cases pass). Expected values
are written out literally here, so the suite is independent of the evaluator's
oracle and of any implementation of the contract.
"""

# The contract (see target/README.md):
#   run(items: list[str]) -> dict with exactly the keys
#   pairs, groups, largest, top, first_repeat.


def _case(name, items, expected):
    return (name, items, expected)


CASES = [
    _case("empty", [], {"pairs": 0, "groups": 0, "largest": [], "top": [],
                        "first_repeat": -1}),
    _case("single", ["a"], {"pairs": 0, "groups": 0, "largest": ["a", 1],
                            "top": [["a", 1]], "first_repeat": -1}),
    _case("one_pair", ["a", "a"], {"pairs": 1, "groups": 1,
                                   "largest": ["a", 2], "top": [["a", 2]],
                                   "first_repeat": 1}),
    _case("mixed", ["b", "a", "b", "a", "a"],
          {"pairs": 4, "groups": 2, "largest": ["a", 3],
           "top": [["a", 3], ["b", 2]], "first_repeat": 2}),
    _case("tie_breaks_lexicographically", ["z", "y", "z", "y"],
          {"pairs": 2, "groups": 2, "largest": ["y", 2],
           "top": [["y", 2], ["z", 2]], "first_repeat": 2}),
    _case("all_distinct", ["a", "b", "c"],
          {"pairs": 0, "groups": 0, "largest": ["a", 1],
           "top": [["a", 1], ["b", 1], ["c", 1]], "first_repeat": -1}),
    _case("top_is_capped_at_ten",
          ["v%02d" % i for i in range(12)] + ["v05"],
          {"pairs": 1, "groups": 1, "largest": ["v05", 2],
           "top": [["v05", 2]] + [["v%02d" % i, 1]
                                  for i in (0, 1, 2, 3, 4, 6, 7, 8, 9)],
           "first_repeat": 12}),
]


def run_tests(run):
    """Run every frozen case against ``run``; return failure strings."""
    failures = []
    for name, items, expected in CASES:
        try:
            got = run(list(items))
        except Exception as exc:                      # noqa: BLE001
            failures.append("{}: run() raised {}: {}".format(
                name, type(exc).__name__, exc))
            continue
        if not isinstance(got, dict):
            failures.append("{}: run() returned {}, expected dict".format(
                name, type(got).__name__))
            continue
        if set(got) != set(expected):
            failures.append("{}: keys {} != {}".format(
                name, sorted(got), sorted(expected)))
            continue
        for key in sorted(expected):
            if got[key] != expected[key]:
                failures.append("{}: {}: got {!r} want {!r}".format(
                    name, key, got[key], expected[key]))
    return failures
