# program.md — ex5, real-OSS hot path (NLTK distance metrics)

You are optimising **`target/distance.py`**, a verbatim copy of NLTK 3.9.1's
`nltk/metrics/distance.py`. The workload is fixed and seeded; the metric is the
**median seconds** of one workload rep, and **lower is better**.

The loop around you is script-owned: it commits your edit, runs
`python3 guard.py`, runs `python3 bench.py`, keeps your commit only if the guard
exits 0 **and** the metric beats the incumbent by more than the noise floor
(2 %), and otherwise hard-resets to the incumbent. You never commit, revert or
measure by hand.

## What wins

1. Every public function keeps its **signature and its output**:
   `edit_distance`, `edit_distance_align`, `jaro_similarity`,
   `jaro_winkler_similarity`, `binary_distance`, `jaccard_distance`,
   `masi_distance`, `interval_distance`, `presence`, `fractional_presence`,
   `custom_distance`.
   Integer results must stay `int`; floats are compared to 1e-12, so you may
   reassociate arithmetic but not change a value.
2. The metric improves by more than 2 % — a change that is only noise is discarded.
3. The file is still importable stdlib-only Python 3.11+.

## Hard rules (the guard enforces the first three)

- **Stay inside `target/`.** `bench.py`, `guard.py` and `oracle/` are frozen and
  out of scope; a diff that touches them is reverted unread.
- **No new file or interpreter escape.** No new `open`/`exec`/`eval`/`compile`/
  `__import__`, no `importlib`/`os`/`sys`/`subprocess`/`socket`/`pathlib`, no
  `__globals__`/`__subclasses__` games. Read nothing at runtime.
- **No caching keyed on the inputs, no work moved to import time.** Every rep is
  a **cold process**: `bench.py` starts a fresh `python3 -I` child, imports the
  module inside the timed region and then runs the workload with that rep's own
  seed. Memoising pairs or precomputing tables at import is therefore paid on
  every rep instead of being free, and a cache keyed on the inputs gains
  nothing across reps. Branching on string length/seed/specific inputs is reward
  hacking, not optimisation: the guard's inputs differ from the bench's, its
  oracle is the pristine upstream module, and the candidate runs in its own
  throwaway process where it cannot reach the comparison.
- **Keep the module's public surface.** All twelve public functions must still
  exist with their signatures unchanged — `presence`, `fractional_presence` and
  `custom_distance` included, even though the bench never calls them. The public
  surface is compared with the pristine module's, name by name and signature by
  signature, and a missing or reshaped callable fails the guard; a changed
  output fails it too.

## Where the time actually goes (honest hints)

- `edit_distance` builds a full `(len1+1) x (len2+1)` matrix and calls
  `_edit_dist_step` once per cell, passing eight arguments plus two keywords.
  Inlining the step and dropping to two rows for the non-transposition case is
  the single biggest win; the transposition variant needs the full matrix.
- `jaro_similarity` tests `j not in flagged_2` against a **list** inside a
  nested loop — quadratic membership on a hot path. A `set`, `bytearray` or
  index array is a large, safe win.
- `edit_distance_align` pays for the same per-cell function call and then
  rebuilds tuples in the backtrace; it does thousands of calls per rep.
- `_edit_dist_init` allocates and then fills; `list(range(n))` plus one slice
  per row does the same work more cheaply.
- Micro-wins worth taking once the structure is right: hoist attribute lookups
  and `min` into locals, avoid recomputing `len()`, avoid `sigma`/`last_left_t`
  where the plain DP does not need them (only the transposition variant does).

## Verify before you finish

```bash
python3 guard.py                        # must print "guard: ok"
EX5_BENCH_SCALE=0.1 python3 bench.py    # a fast smoke measurement
```

Do not trust a fast run that the guard rejects — a candidate that fails the
guard never gets a score.

## Reporting

End your turn with exactly one line:

```
CHANGE: <one line, imperative, what you changed>
```

The loop records that line as the iteration's description in the ledger.
