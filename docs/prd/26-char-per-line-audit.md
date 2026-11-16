# PRD 26 — Char-Per-Line Audit: One Column Cap, Enforced

> Intent: make the 80-column prose rule structural. One stdlib-only script
> measures every prose line under `docs/`, `README.md` and `AGENTS.md`, and CI
> fails on any wrap-able over-cap line, so the rule no longer depends on a
> reviewer noticing. **Domain:** `chars` — line width across prose and source
> text. **Canonical tests:** `tests/unit/test_audit_chars.py`
> (`AC-CHARS-001..006`). **Renumbered:** ported from
> `bachkukkik/template-agentic-ready-repo` @ `18694c5`
> (`docs/prd/09-char-per-line-audit.md`). `09` is this repo's `AGENTS.md`
> context-budget record, so the ported pair lands at 26/27 in both layers.

## Context

A prose line wider than 80 columns re-wraps in every terminal, diff viewer and
agent context window, so reading cost follows the renderer instead of the text.
No width rule was enforced here, and the cost was measured before the rule:
1,966 of 5,328 measured lines ran over 80 columns across 63 of the 64 files in
the default scope, the widest at 542 characters, and nothing failed when the
next long line landed.

Reflow and gate land as one change, because a hard gate can only hold on a
corpus that passes it. Both are delivered: the corpus was reflowed in the same
pass that made the run strict, and the default run now exits 0 at 0 of 6,450
measured lines over 80 columns across 69 files. The measured state, including
the 37 structural `unbreakable` lines, is recorded in
`docs/26-char-per-line-audit.md`.

`[ASSUMPTION]` No `kb/` page covers line width: `grep -ril 'width' kb/` returns
four hits, all model width or memory bandwidth in the engine notes, and none is
about line length. So 80 columns is a policy choice, not a knowledge-backed
finding. It follows the conventional terminal width and the measure this repo's
older prose already keeps.

## Deliverable

`scripts/audit-chars.py` — stdlib-only CLI, no config file, no fixer:

| Flag | Default | Effect |
|------|---------|--------|
| `FILE...` | default scope | Measure exactly these paths. |
| `--max-chars` | `80` | Cap in characters. |
| `--advisory` | off | Report the offenders without failing. |
| `--json` | off | One JSON object instead of the report. |
| `--verbose` | off | Print the per-file table even when clean. |

Scope and exemptions:

| Input | Measured | Exempt |
|-------|----------|--------|
| `docs/**/*.md` | prose lines only | fences, tables, headings |
| `README.md` | prose lines only | blockquote, list, footnote marks |
| `AGENTS.md` | prose lines only | as above |
| any other path | raw, char for char | nothing |

Symlinks are skipped, so the `CLAUDE.md`, `GEMINI.md` and
`.github/copilot-instructions.md` aliases of `AGENTS.md` are never counted
twice. A markdown line loses its blockquote marker, list marker and footnote
references before it is measured; a non-markdown file is measured raw, because a
`.py` or a `.yml` has no markdown exemption to honour.

The run is strict by default: exit 1 when any wrap-able measured line is over
the cap, so CI holds the line without a ratchet. `--advisory` reports the same
offenders and exits 0, for the staged adoption pass. There is no `--strict`
flag.

An over-cap line carrying a whitespace-delimited token wider than the cap — a
long URL or a bare link — is classified `unbreakable`: no whitespace wrap can
bring that token under the cap, so the line is never an offender and never a
failure. It is counted apart in `totals['unbreakable']` and printed as
`unbreakable: U ...`. A line of ordinary words is always an offender, because
every token fits and a wrap fixes the width.

`tests/unit/test_audit_chars.py` — hermetic unit tier (`AC-CHARS-0NN`):

| ID | Asserts |
|----|---------|
| `AC-CHARS-001` | Default (strict) run exits 0 with `over == 0`; paths are repo-relative; the default scope spans at least 15 files. |
| `AC-CHARS-002` | 120-character prose fails; a fence, a table row and a heading of the same width are exempt. |
| `AC-CHARS-003` | `--help` exits 0; a missing path exits 1 and is named; the documented default is 80; `--advisory` exits 0 on an over-cap line. |
| `AC-CHARS-004` | A non-markdown file is measured raw: a 100-character source line is reported at its full width. |
| `AC-CHARS-005` | The auditor and its test module hold the cap they enforce. |
| `AC-CHARS-006` | An over-cap line carrying a token wider than the cap is `unbreakable` and does not fail the run, whether the token stands alone or follows a word; a 120-character line of ordinary short words is an offender and does fail it. |

## Success Criteria

- **SC-cl-1** — The gate is hard and holds here: the default run exits 0 on this
repo, whose measured lines all fit the cap after the reflow, and exits 1 on
any wrap-able over-cap line. _Verify:_ `tests/unit/test_audit_chars.py`
(`AC-CHARS-001`).
- **SC-cl-2** — A 120-character prose line fails the default run; a fenced
block, a table row and a heading of the same width are exempt. _Verify:_
`tests/unit/test_audit_chars.py` (`AC-CHARS-002`).
- **SC-cl-3** — `--help` exits 0, a missing input exits 1 naming the path, the
documented default is 80, and `--advisory` exits 0 on an over-cap line.
_Verify:_ `tests/unit/test_audit_chars.py` (`AC-CHARS-003`).
- **SC-cl-4** — A non-markdown file is measured raw: a 100-character source line
is reported at its full width, with no markdown exemption applied. _Verify:_
`tests/unit/test_audit_chars.py` (`AC-CHARS-004`).
- **SC-cl-5** — The auditor and its test module hold the cap they enforce, so
the gate cannot exempt itself. _Verify:_ `tests/unit/test_audit_chars.py`
(`AC-CHARS-005`).
- **SC-cl-6** — An over-cap line carrying a token wider than the cap (a long
URL) is counted as `unbreakable` and does not fail the run, whether the token
stands alone or follows a word; a 120-character line of ordinary short words
is an offender and does fail it. _Verify:_ `tests/unit/test_audit_chars.py`
(`AC-CHARS-006`).

## Test Mapping

| SC | Test | Tier |
|----|------|------|
| Repo passes the gate at 0 over | `AC-CHARS-001` | unit |
| Discrimination and exemptions | `AC-CHARS-002` | unit |
| CLI contract and `--advisory` | `AC-CHARS-003` | unit |
| Raw path for non-markdown | `AC-CHARS-004` | unit |
| Sources fit the cap | `AC-CHARS-005` | unit |
| Unbreakable over-wide token line | `AC-CHARS-006` | unit |

## CI/CD Gate

The `unit` job's `Machine gates` step runs, in order,
`python3 scripts/audit_pyramid.py`, `python3 scripts/audit-chars.py` and
`python3 scripts/audit-size.py --max-kb 60`, so the char gate fails the job
directly: a wrap-able line over 80 characters blocks a merge without waiting on
pytest. The tests pin the behaviour; the step is the enforcement. `--advisory`
is for local adoption runs only and never appears in CI.

## Source attribution

No `kb/` page covers line width, so the 80-column default is `[ASSUMPTION]`
above. Conventions: `AGENTS.md` §5 (PRD → Test → CI) and `PRD.md` §
*Verification Policy*. The gate shape — one numeric cap, exit 1 on a violation,
a reporting-only flag for adoption — mirrors `scripts/audit-ste.py`
(`docs/prd/15-ste-audit.md`). Ported from
`bachkukkik/template-agentic-ready-repo` @ `18694c5`, PRD 09.

## Assumptions

- `[ASSUMPTION]` 80 columns is the right default: it is the conventional
terminal width and the measure the repo's older prose already keeps, and it is
CLI-overridable (`--max-chars`).
- `[ASSUMPTION]` Prose is the target, not code: markdown prose plus the two
entry documents is the default scope, and a source file is measured only when
it is named.
- `[ASSUMPTION]` The `unbreakable` exemption is safe because it is structural: a
line qualifies only by carrying a token no wrap can shorten, which
`AC-CHARS-006` pins in both directions.

## Confidence

**High** — the script is a hermetic stdlib auditor and all six of its ACs pass,
and SC-cl-1's corpus clause is a measurement rather than a target: the default
run exits 0 at 0 of 6,450 measured lines over 80 columns across 69 files.
`AC-CHARS-001` pins the 37 structural `unbreakable` tokens as a shrink-only
ratchet, as `docs/26-char-per-line-audit.md` records.
