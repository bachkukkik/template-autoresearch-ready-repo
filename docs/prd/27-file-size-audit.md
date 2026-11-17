# PRD 27 — File-Size Audit: A Byte Ceiling, Adopted at 60 KB

> Intent: put a numeric ceiling on every tracked file, so a file that stops
> being reviewable fails CI instead of growing quietly. The script keeps a
> strict 20 KB default; this repo runs the gate at an adopted 60 KB and exempts
> the three file classes it is forbidden to shrink. The deviation and its cost
> are stated in *Deviations from upstream*, not hidden in a flag. **Domain:**
> `size` — tracked-file byte size. **Canonical tests:**
> `tests/unit/test_audit_size.py` (`AC-SIZE-001..006`). **Renumbered:** ported
> from `bachkukkik/template-agentic-ready-repo` @ `18694c5`
> (`docs/prd/10-file-size-audit.md`). `10` here is the methodology record, so
> the ported pair lands at 26/27 in both layers. **Open gap:**
> `docs/gaps/27-file-size-cap-cannot-hold.md`.

## Context

A file that grows without a ceiling stops being reviewable: a 200 KB article is
skipped by reviewers and truncated by context windows, and an agent asked to
edit it pays for bytes it does not need. Nothing measured tracked file size here
before this gate, so growth was bounded by attention alone.

Upstream sized its cap to its own corpus: 91 tracked entries, 87 regular files,
largest 19,830 bytes, so a 20 KB cap was live with 650 bytes of headroom. This
repo tracks **423 regular files** (430 `git ls-files` entries, the 7 skipped
being symlinks), and 30 of those 423 are over 20,480 bytes — 22 inside the
measured scope and 8 inside the exempt classes. A 20 KB cap here would fail 30
files on the day it landed, none of which this repo is allowed to shrink. These
counts move as the repo grows — `python3 scripts/audit-size.py --max-kb 60
--json` is the authoritative source.

`[ASSUMPTION]` No `kb/` page covers file size: `grep -ril 'size cap' kb/`
returns nothing. 20 KB is a policy choice, and so is the 60 KB adoption below.

## Deliverable

`scripts/audit-size.py` — stdlib-only CLI:

| Flag | Default | Effect |
|------|---------|--------|
| `FILE...` | tracked scope | Measure exactly these paths. |
| `--max-kb` | `20.0` | Cap = `int(max_kb * 1024)` = 20480 bytes. |
| `--json` | off | One JSON object instead of the table and findings. |
| `--verbose` | off | Print the per-file table even when clean. |

- Scope: the regular files in `git ls-files` — 386 measured today, from 423
regular entries, the rest exempt (below). Untracked files never fail the gate.
A tree that is not a git repository falls back to a recursive walk.
- Skipped entries: the 7 tracked symlinks — `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, `.claude/{commands,plugins,skills}`,
`.opencode/commands`. A link's own size says nothing about its target, and
every target is already in scope under its real path.
- The cap is inclusive: exactly 61,440 bytes passes at `--max-kb 60`, 61,441
fails. At the default 20 KB the boundary is 20,480 / 20,481.
- Strict by default: exit 1 when any measured file is over the cap.
- An unreadable file is a warning on stderr, counted as 0 bytes, never raised.
- Exempt paths are never measured, so they can never affect the exit code, and
they are never silent: each is counted as `exempt` in the summary line and in
the `--json` totals.

`tests/unit/test_audit_size.py` — hermetic unit tier (`AC-SIZE-0NN`):

| ID | Asserts |
|----|---------|
| `AC-SIZE-001` | The shipped tree passes at the adopted 60 KB cap; totals agree with the rows; the largest row sorts first. |
| `AC-SIZE-002` | The default cap is inclusive and exact — 20,481 bytes fails, 20,480 passes — and `--max-kb 30` lifts the cap over the same file. |
| `AC-SIZE-003` | The default is 20.0 KB, `limit_bytes` yields 20480, `--help` exits 0, and a missing path exits 1 naming it. |
| `AC-SIZE-004` | Positional paths replace the tracked scope rather than add to it. |
| `AC-SIZE-005` | The auditor and its test module hold the 80-column rule. |
| `AC-SIZE-006` | The three policy exemptions are skipped and counted, never reported as offenders, and a same-sized ordinary file is still an offender at the unchanged 20 KB default. |

## Deviations from upstream

Four statements, because a port that hides its arithmetic is a port nobody can
audit later.

1. **The script keeps `DEFAULT_MAX_KB = 20.0` and stays strict.** The default
cap, the inclusive boundary and the `git ls-files` scope are upstream's, and
`AC-SIZE-002`/`AC-SIZE-003` pin them. Nothing about the default is relaxed:
`python3 scripts/audit-size.py` on this tree exits 1 with 22 offenders.
2. **CI runs `--max-kb 60`.** The `Machine gates` step runs
`python3 scripts/audit-size.py --max-kb 60`, and `AC-SIZE-001` asserts the
same adopted cap, so the gate this repo actually holds is 61,440 bytes per
file.
3. **`EXEMPT_PATHS` covers only classes this repo may not shrink.** The
mechanism is three literal entries — no globs, no config file, no CLI flag —
and each has a doctrine reason:

   | Entry | Kind | Why exempt |
   |-------|------|------------|
   | `kb/raw/` | directory prefix | Funnel rule 3 makes raw sources append-or-archive: an ingest may never edit or trim an existing source, so a byte cap could only be met by an edit the doctrine forbids. |
   | `kb/log.md` | whole path | The knowledge log is append-only (funnel rule 5): its growth *is* the record, and trimming it loses history rather than fat. |
   | `autoresearch/uv.lock` | whole path | Generated by `uv`: its size follows the dependency graph, and a hand edit breaks the lock. |

4. **Measured state.** 386 measured files, largest 56,312 bytes
(`tests/unit/test_harness_neutrality.py`), 0 over at 60 KB; the 37 exempt
files include `autoresearch/uv.lock` at 317,842 bytes.

**What the deviation costs.** A 56 KB test module can grow to 60 KB — 5,128
bytes, 8.3% — before the gate speaks, where upstream's largest file had 650
bytes of headroom at 20 KB. The gate here is therefore coarser than upstream's:
it catches a file that has become unreviewable, not a file that has crept past a
tight budget. The 20 KB policy this PRD's default names does not hold in this
corpus, and the convergence path is the live gap
`docs/gaps/27-file-size-cap-cannot-hold.md`.

## Success Criteria

- **SC-fs-1** — Every measured tracked file is within the adopted 61,440-byte
cap, the totals agree with the per-file rows, and the largest row sorts first.
_Verify:_ `tests/unit/test_audit_size.py` (`AC-SIZE-001`).
- **SC-fs-2** — The default cap is inclusive: at 20 KB, 20,481 bytes fails and
20,480 passes, and `--max-kb 30` lifts the cap over the same file. _Verify:_
`tests/unit/test_audit_size.py` (`AC-SIZE-002`).
- **SC-fs-3** — The default is 20.0 KB, `limit_bytes` yields 20480, `--help`
exits 0, and a missing path exits 1 naming the path. _Verify:_
`tests/unit/test_audit_size.py` (`AC-SIZE-003`).
- **SC-fs-4** — Positional paths replace the tracked scope rather than add to
it, so a test can measure one synthetic oversize file. _Verify:_
`tests/unit/test_audit_size.py` (`AC-SIZE-004`).
- **SC-fs-5** — The auditor and its test module hold the 80-column rule.
_Verify:_ `tests/unit/test_audit_size.py` (`AC-SIZE-005`).
- **SC-fs-6** — `kb/raw/`, `kb/log.md` and `autoresearch/uv.lock` are exempt
whatever their size, are counted as `exempt`, and a same-sized ordinary file
is still an offender at the default cap. _Verify:_
`tests/unit/test_audit_size.py` (`AC-SIZE-006`).

## Test Mapping

| SC | Test | Tier |
|----|------|------|
| Shipped tree within the adopted cap | `AC-SIZE-001` | unit |
| Inclusive boundary and the flag | `AC-SIZE-002` | unit |
| CLI contract and cap arithmetic | `AC-SIZE-003` | unit |
| Explicit-path override | `AC-SIZE-004` | unit |
| Sources fit the 80-column rule | `AC-SIZE-005` | unit |
| Policy exemptions skipped and counted | `AC-SIZE-006` | unit |

## CI/CD Gate

Two enforcements, one rule. The `unit` job's `Machine gates` step runs
`python3 scripts/audit-size.py --max-kb 60`, so an over-cap tracked file fails
the job before pytest starts; and `AC-SIZE-001` asserts the same cap from inside
the unit tier, so a hand-run CLI and a CI run cannot disagree about the adopted
number. A failure names the file and its byte count. The script's own default
stays 20 KB and stays strict, which is why the hand-run command and the CI
command differ by one flag.

## Source attribution

No `kb/` page covers file size, so both numbers — 20 KB default, 60 KB adopted —
are `[ASSUMPTION]` above. Conventions: `AGENTS.md` §5 (PRD → Test → CI) and
`PRD.md` § *Verification Policy*. The tracked-scope rule follows funnel rule 1
(`AGENTS.md`): a document outside stages 1–6 is a defect, and an untracked file
is not part of the doctrine the gate protects. The exemption reasons follow
funnel rules 3 and 5 (`kb/raw/` append-or-archive, `kb/log.md` append-only).
Ported from `bachkukkik/template-agentic-ready-repo` @ `18694c5`, PRD 10.

## Assumptions

- `[ASSUMPTION]` 20 KB is the right default for a corpus the size of upstream's,
and 60 KB is the right adoption for this one: 60 KB is the smallest round
budget that holds the largest measured file with headroom.
- `[ASSUMPTION]` The three exemption classes are complete: every other class in
this tree can shrink, so an over-cap file elsewhere is a refactor, not a
policy exception.
- `[ASSUMPTION]` A byte cap is the right proxy for reviewability; it does not
measure structure, so a 55 KB file can be well organised and a 15 KB one can
be a tangle.

## Confidence

**Medium** — the mechanism is verified (`tests/unit/test_audit_size.py`: 6
passed) and the boundary arithmetic is exact, but the policy the default names
is not met by this corpus: 22 measured files are over 20 KB today, the adopted
cap is 4× upstream's, and only the refactor waves named in the gap make the two
numbers converge. The deviation is adopted deliberately, not discovered late.
