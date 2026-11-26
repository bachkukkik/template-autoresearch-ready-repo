# 28 — Veteran Layer

> **What this records.** PRD 28's deliverables and their first follow-up: the
> twenty-rule register, the three-layer model in `ADOPTING.md`, the skipped-job
> guard that closes VD-14 in code, and — from the 2026-11-26 follow-up run —
> the `_Verify:` payload checker that closes VD-09, the adopter numbering
> reservation, the referee-line reader in the engine, and the docs
> reconciliation this record itself needed.
> **Provenance:** the mature downstream instance
> `vanilla-open-design-autoresearch` (38 registered seasons, 22 tracked close
> records, 75 rounds, a 25,046-line league); the adopter that forked instead of
> followed (`media-gen-ops-autoresearch` PRDs 28–31); knowledge capture
> `kb/raw/articles/2026-11-26-veteran-decisions.md`; intent
> [PRD 28](prd/28-veteran-layer.md).

## What

A register of twenty decisions in `docs/prd/28-veteran-layer.md`, each carrying
the failure that earned it, an enforcement cell and a source; tests holding
that table, the `_Verify:` convention and the numbering reservation to their
own claims; a layer model in `ADOPTING.md` that says where a game belongs; and
a three-line change to `scripts/local-ci.sh` that makes a skipped CI job fail.

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
| `test:` | 8 (VD-01..05, 09, 13, 14) | a test here fails if the rule stops holding |
| `test-partial:` | 5 (VD-07, 10, 18..20) | the mechanical half runs; the settlement half is a game's |
| `declared:` | 7 (VD-06, 08, 11, 12, 15..17) | this tree cannot enforce it, and a gap says who would |

`tests/unit/test_veteran_register.py` parses the table and asserts: twenty rows
with contiguous ids; five non-empty cells each; every `test:`/`test-partial:`
target exists in the tree; every `declared:` row appears by id in
`docs/gaps/28-veteran-rules-unenforced.md` and every id there is a row (both
directions, with VD-18 and VD-19 admitted as the two `test-partial:` rows it
lists); no cell carries an absolute path, a `scratchpads/` path, a `..`
traversal or a sibling checkout's name; and `ADOPTING.md` carries the layer
section with the configure-not-fork sentence.

**A pointer is not proof.** `tests/unit/test_verify_payloads.py` (AC-VET-009)
applies VD-09 to this repo: it reads every `docs/prd/NN-*.md`, takes each
`_Verify:` payload that names both a test file and an AC id, and requires the
file to resolve inside the repo root and to carry that id. The boundaries are
the ones a reader sees — a blank line, or a line whose first non-space
character opens a bullet, a table row or a heading. A marker quoted in
backticks discusses the convention and is not a payload; a letter-suffixed id
(`AC-URC-024b`, eleven of them cited here) is a distinct id and must appear
verbatim; a range expands; a passage between `~~` markers is retired; a cited
path that climbs out of the root is reported rather than read; and a missing
file is reported once, not again as an absent id.

Measured on this tree: 25 PRDs, 195 live payloads, 183 of them naming both a
path and an id, 0 findings.

**The numbering is prose a test reads.** `ADOPTING.md` reserves `01`–`49` for
the template's own core and instruments and tells an adopter to number its own
PRDs, records and gaps from `50` up; a sibling that spent `28`–`31` on its game
layer collided with this template's `28`–`30` on the next pull. AC-VET-010
asserts both halves of that sentence and that no PRD this template ships sits
at or above `50`.

**The referee's line is read, not trusted.** `measure.parse_metric` now reads
`LEG <name> <value> <lower|higher>` — the shape a league referee prints — after
`METRIC` and before a labelled line. The direction is the referee's own
declaration, never heard over the configured one, and the exact line is kept as
the record's `raw`. Forms are tried in the priority order listed, so a `LEG`
line outranks a plainer labelled line later in the same output; within one form
the last matching line wins (`AC-ENG-001b`). This closes the referee convention
the *Layer model* section names.

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

**The docs caught up with the register.** The follow-up run reconciled what
this record's first version had predicted with what the tree now does:
`ADOPTING.md` Step 2.5 shows the engine loop beside the contract loop, Step 3
carries the layer model and the numbering band, Step 5 points at `D0`–`D4` /
`sub1`–`sub4` and Step 6 names `README.md` as the home of the structure block;
the *Knowledge Base* and *Status* sections of `README.md` were brought up to
date; and gap 17 was archived, its resolution having landed in PRD 17 (rule 5).

## Verification

```
$ python3 -m pytest tests/unit/test_veteran_register.py \
      tests/unit/test_verify_payloads.py tests/unit/test_engine_measure.py -q
39 passed in 6.92s

$ python3 -m pytest tests/unit -q
674 passed

$ python3 -m pytest tests/integration -q
49 passed

$ python3 scripts/audit-chars.py
OK: every measured line is within 80 chars (7217 lines); 37 unbreakable

$ python3 scripts/audit-size.py --max-kb 60
OK: 406 tracked files within 61440 bytes (largest 56312 B)

$ python3 scripts/audit_pyramid.py
OK: 3 foundations green (37 files, ratio 5.8%)

$ bash scripts/verify-clone.sh | tail -1
RESULT: PASSED — 33 check(s) passed
```

Register parse, measured: 20 rows — 8 `test:`, 5 `test-partial:`, 7 `declared:`.

## What Works

- **The register fails when it rots.** Rebinding VD-03/VD-04 to a test file that
  did not yet exist produced exactly two failures naming both ids and both
  paths, and went green the moment PRD 29 landed that file. That is the gate
  doing its job on its own author.
- **The three kinds carry different weight and the test enforces the
  difference.** A `declared:` row with no gap listing fails; a gap listing for a
  plain `test:` row fails.
- **VD-09 is closed, by its own rule.** The register said a pointer is not
  proof; the checker now holds 183 payloads across 25 PRDs to the id they cite,
  and each of its shortcuts has a negative control that fails without it.
- **VD-19 was reclassified rather than noted.** It read `test:` with a prose
  footnote saying the payment half was not tested; it is now `test-partial:`
  and the gap lists it, so the cell and the gap agree with the code.
- **The numbering reservation is checked, not declared.** AC-VET-010 reads the
  band and the start out of `ADOPTING.md` and refuses a shipped PRD at or above
  `50`; a document stating only the start passes neither half.
- **The referee convention has a reader.** A `LEG speed 2.5 higher` line is now
  a metric on the same terms as `METRIC`, and an unknown direction token
  (`sideways`) is not, so a referee cannot rename its way into a reading.
- **The guard is proven by execution, not by reading.** The stub `act` returns 0
  having run nothing; the script still exits 1.
- **The layer model needed no code.** It is a paragraph plus a table, and
  `ADOPTING.md` is where an adopter already looks for what to keep.

## What Fails

- **Seven rules remain unenforced, by design.** They govern a tournament, a
  settlement, a scheduler fleet and a steward that this template does not ship.
  The register says so in the cell and the gap says so again; a reader who does
  not follow the cell will still over-read the rule.
- **VD-02's enforcement is narrower than the rule.**
  `_require_wall_funds_an_iteration` refuses a wall below the smallest usable
  one; it does not enforce that each iteration's *remaining* wall funds the
  next, which the veteran's rule states.
- **Twelve of the 195 payloads cannot be checked.** They state their proof as a
  CI job, a runner command or a docs record — one names an id with no test
  path, four name a path with no id and seven neither. The checker reports
  nothing about them, so those claims still rest on the reader.
- **`scripts/local-ci.sh` still carries four pre-existing over-80-column lines.**
  They are comments and one operator `echo`; the char audit scans `docs/`
  markdown and the two entry files, so it has never measured this script, and
  this change left them alone rather than widening its own diff.

## Resolution

One resolution per failure, in the order above.

- **Seven `declared` rules** — gap [28](gaps/28-veteran-rules-unenforced.md)
  lists every one by id with the layer that would close it; VD-09 was the
  cheapest and is now closed, so the next-nearest is a metric registry that can
  retire a leg (VD-08).
- **VD-02's narrower enforcement** — a PRD edit: narrow the rule sentence to
  what `_require_wall_funds_an_iteration` actually refuses.
- **Twelve unchecked payloads** — a PRD edit each, giving the claim an AC id
  and the test that carries it; until then the honest form is a payload that
  names a CI job and makes no id claim, which is what most of them already do.
- **Four over-80 columns in `local-ci.sh`** — left alone deliberately to keep
  this diff surgical; widening the char audit beyond `docs/` would be a
  separate PR with its own wave, not a rider on this one.

## Verdict

**works** — for what it claims. Both defects the first version recorded as open
— VD-09's missing checker and VD-19's wrong cell — are closed, and the claims
the tree still cannot enforce are stated as such in the register and in the
gap. The remaining limits are in *What Fails* rather than in a footnote.
