# target/ -- the tiny software repo the agent edits

A two-file package: `solution.py` (the implementation) and `tests.py` (its
frozen test suite). This repository is the *subject* of the ex4 experiment; the
evaluator (`../prepare.py`) and this file are read-only for the run.

## Module contract

`solution.py` must define exactly one public entry point:

```python
def run(items: list[str]) -> dict
```

It returns a dict with exactly these five keys:

| Key | Type | Meaning |
|---|---|---|
| `pairs` | int | number of index pairs `(i < j)` with `items[i] == items[j]` |
| `groups` | int | number of distinct values occurring at least twice |
| `largest` | list | `[value, count]` of the most frequent value; ties resolve to the lexicographically smallest value; `[]` for an empty input |
| `top` | list | up to 10 x `[value, count]`, sorted by `(-count, value)` ascending |
| `first_repeat` | int | the smallest index `j` whose value already appeared in `items[:j]`; `-1` when no value repeats |

`run` must be pure: same input, same output; no I/O, no globals mutated.

## Tests

`tests.py` is the correctness gate. It is standard-library only and pytest-free:
`python3 -c "import tests, solution; print(tests.run_tests(solution.run))"`
prints `[]` when the implementation is correct. `prepare.py` runs the same suite
inside its budget-bounded child, plus an exact-output comparison on a held-out
workload, and rejects any candidate that references the frozen oracle.

## Workload and budget

`prepare.py` (`../prepare.py`, FROZEN) owns the workloads, the metric and
`TIME_BUDGET`. One evaluated run is a single subprocess with a hard
`TIME_BUDGET`-second wall-clock limit; the baseline implementation is quadratic,
takes many times the budget, and is therefore killed at the budget and recorded
as a non-keep row. The gate (this suite plus the held-out comparison) runs
before the timed calls, so a candidate is only ever timed when it is correct.
