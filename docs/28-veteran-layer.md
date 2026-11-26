# 28 — Veteran Layer

> **What this records.** PRD 28's three deliverables: the twenty-rule register,
> the three-layer model in `ADOPTING.md`, and the skipped-job guard that closes
> VD-14 in code. Written from a verification run, not from the plan.
> **Provenance:** the mature downstream instance
> `vanilla-open-design-autoresearch` (38 registered seasons, 22 tracked close
> records, 75 rounds, a 25,046-line league); the adopter that forked instead of
> followed (`media-gen-ops-autoresearch` PRDs 28–31); knowledge capture
> `kb/raw/articles/2026-11-26-veteran-decisions.md`; intent
> [PRD 28](prd/28-veteran-layer.md).

## What

A register of twenty decisions in `docs/prd/28-veteran-layer.md`, each carrying
the failure that earned it, an enforcement cell and a source; a structural test
that holds the table to that shape; a layer model in `ADOPTING.md` that says
where a game belongs; and a three-line change to `scripts/local-ci.sh` that
makes a skipped CI job fail.

## Why

The template carried contracts and not judgment, and the cost was measurable: a
sibling repo built on this template re-derived four contracts as its own PRDs
because nothing said which layer belonged to the adopter. The register is the
cheapest possible carrier — it travels as prose an adopter can read in one
sitting, and it becomes machine-checkable where this tree can already check it.

## How

**The register is data, not a list of links.** Each row's `Enforcement` cell is
one of three kinds, and the kind is the claim:

| Kind | Rows | Meaning |
|---|---|---|
| `test:` | 8 (VD-01..05, 13, 14, 19) | a test in this tree fails if the rule stops holding |
| `test-partial:` | 4 (VD-07, 10, 18, 20) | the mechanical half runs; the settlement half is a game's |
| `declared:` | 8 (VD-06, 08, 09, 11, 12, 15..17) | this tree cannot enforce it, and a gap says who would |

`tests/unit/test_veteran_register.py` parses the table and asserts: twenty rows
with contiguous ids; five non-empty cells each; every `test:`/`test-partial:`
target exists in the tree; every `declared:` row appears by id in
`docs/gaps/28-veteran-rules-unenforced.md` and every id there is a row (both
directions); no cell carries an absolute path, a `scratchpads/` path, a `..`
traversal or a sibling checkout's name; and `ADOPTING.md` carries the layer
section with the configure-not-fork sentence.

**The guard is behavioural.** `scripts/local-ci.sh` previously read act's exit
code and the `Job failed` marker. It now also reads two skip markers
(`Skipping unsupported platform`, `Job skipped`) and fails the job with a
printed reason. `tests/unit/test_local_ci_guard.py` does not grep the script: it
writes a stub `act` into `tmp_path/bin`, puts it on `PATH`, and runs the real
script — a skip-only log must exit 1 and print `FAIL`; a clean log must exit 0
and print `RESULT: PASSED`; a log with `Job failed` must still name the job
failure, so the new check did not replace the old one.

One pre-existing hazard was found and fixed in passing: the failure-detail
`grep` pipeline aborted under `set -e` + `pipefail` on a skip-only log, which is
exactly the case that must print a reason, so it now ends in `|| true`.

## Verification

```
$ python3 -m pytest tests/unit/test_veteran_register.py \
      tests/unit/test_local_ci_guard.py -q
32 passed            # across the register and guard suites with W2's file

$ python3 -m pytest tests/unit/test_docs_template.py \
      tests/unit/test_gaps_lifecycle.py -q
20 passed

$ python3 scripts/audit-chars.py
OK: every measured line is within 80 chars (6807 lines); 37 unbreakable

$ python3 scripts/audit-size.py --max-kb 60
OK: 386 tracked files within 61440 bytes

$ python3 scripts/audit_pyramid.py
OK: 3 foundations green (34 files, ratio 5.3%)

$ bash -n scripts/local-ci.sh
OK
```

Register parse, measured: 20 rows — 8 `test:`, 4 `test-partial:`, 8 `declared:`.

## What Works

- **The register fails when it rots.** Rebinding VD-03/VD-04 to a test file that
  did not yet exist produced exactly two failures naming both ids and both
  paths, and went green the moment PRD 29 landed that file. That is the gate
  doing its job on its own author.
- **The three kinds carry different weight and the test enforces the
  difference.** A `declared:` row with no gap listing fails; a gap listing for a
  plain `test:` row fails.
- **The guard is proven by execution, not by reading.** The stub `act` returns 0
  having run nothing; the script still exits 1.
- **The layer model needed no code.** It is a paragraph plus a table, and
  `ADOPTING.md` is where an adopter already looks for what to keep.

## What Fails

- **Eight rules remain unenforced, by design.** They govern a tournament, a
  settlement, a scheduler fleet and a steward that this template does not ship.
  The register says so in the cell and the gap says so again; a reader who does
  not follow the cell will still over-read the rule.
- **VD-19 (salvage) is `test:` here but its payment half is not.** The engine
  salvages a dead agent's tree and marks a keep `salvaged`; nothing pays for it,
  because nothing pays. The register's `test:` claim is true of the mechanical
  half only — the same shape as `test-partial`, and it should probably be
  re-classified rather than left to a note.
- **VD-02's enforcement is narrower than the rule.**
  `_require_wall_funds_an_iteration` refuses a wall below the smallest usable
  one; it does not enforce that each iteration's *remaining* wall funds the
  next, which the veteran's rule states.
- **The `_Verify:` payload rule (VD-09) has no checker**, so the template's own
  PRDs are still trusted on their word — the exact defect the veteran found in
  its own tree when it discovered 205 pointer-only annotations.
- **`scripts/local-ci.sh` still carries four pre-existing over-80-column lines.**
  They are comments and one operator `echo`; this change left them alone rather
  than widening its own diff, and they are the only offenders in the file.

## Resolution

The unenforced half is tracked, not forgotten. One resolution per failure, in
the order above:

- **Eight `declared` rules** — gap [28](gaps/28-veteran-rules-unenforced.md)
  lists every one by id with the layer that would close it. Cheapest next:
  VD-09, a `_Verify:` payload checker, test-only, no runtime change.
- **VD-19's payment half** — a PRD edit, not a code change: the honest cell is
  `test-partial`, and this record is the evidence for it.
- **VD-02's narrower enforcement** — a PRD edit: narrow the rule sentence to
  what `_require_wall_funds_an_iteration` actually refuses.
- **VD-09 has no checker** — the same VD-09 item above, kept separate here
  because it is both an unenforced rule and a defect in this repo's own PRDs.
- **Four over-80 columns in `local-ci.sh`** — left alone deliberately to keep
  this diff surgical; they are comments and one operator `echo`, and the unit
  job's `audit-chars` step does not measure shell comments.

## Verdict

**works** — for what it claims. The register is machine-held and the guard is
proven by execution; the claims it makes about rules it does *not* enforce are
stated as such in two places. The limits are in *What Fails* rather than in a
footnote.
