# 26 — Char-per-Line Audit

## What

`scripts/audit-chars.py` measures the width of every prose line under `docs/`,
`README.md` and `AGENTS.md`, and fails the run when any wrap-able line is over
`--max-chars` (default 80). It is ported here from
`bachkukkik/template-agentic-ready-repo` @ `18694c5` (its own doc 09) and
renumbered to 26, because `09` is this repo's `AGENTS.md` context-budget record.

## Why

A line wider than 80 columns re-wraps differently in every terminal, diff viewer
and agent context window, so reading cost follows the renderer instead of the
text. This repo had no such rule, and the cost was measurable: 1,966 of 5,328
measured lines ran over the cap across 63 of 64 files, the widest at 542
characters, and nothing failed when the next long line landed.

Reflow and gate land as one change, on the principle that a hard gate can only
hold on a corpus that passes it. The reflow is in: every wrap-able over-cap line
was wrapped in the same pass that made the run strict, so the corpus now stands
at 0 lines over the cap and `python3 scripts/audit-chars.py` exits 0.

## How

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

Flags:

| Flag | Default | Effect |
|------|---------|--------|
| `FILE...` | default scope | Measure exactly these paths. |
| `--max-chars` | `80` | Cap in characters. |
| `--advisory` | off | Report the offenders without failing. |
| `--json` | off | One JSON object instead of the report. |
| `--verbose` | off | Print the table even when clean. |

The run is strict by default: exit 1 when any wrap-able measured line is over
the cap. Offenders print as `file:line: [N chars] first 80 chars`, capped at 20
lines with a `... N more` tail. `--advisory` reports the same list and exits 0,
which is the staged-adoption path.

An **unbreakable** line is an over-cap line carrying a whitespace-delimited
token wider than the cap — a long URL, a repo-relative link target or a bare
link. No whitespace wrap can bring that token under the cap, so the line is not
an offender: it never fails the run, it is counted separately in
`totals['unbreakable']`, and it prints as `unbreakable: U ...`. A line of
ordinary words is always an offender, because every token fits and a wrap fixes
it.

## Verification

Run from the repo root, 2026-11-16, on the corpus this record ships with — after
the reflow, not before it:

```
$ python3 scripts/audit-chars.py > /dev/null; echo "exit=$?"
exit=0

$ python3 scripts/audit-chars.py | grep -E '^lines over|^unbreakable|^OK'
lines over 80 chars: 0/6450 = 0.0%
unbreakable: 37 (token wider than 80)
OK: every measured line is within 80 chars (6450 lines); 37 unbreakable
```

Measured totals:

```
$ python3 scripts/audit-chars.py --json | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["totals"])'
{'files': 69, 'lines': 6450, 'over': 0, 'worst': 135, 'unbreakable': 37}
```

The widest measured line is 135 characters, and it is one of the 37 unbreakable
ones: a markdown link token that no wrap can shorten. Those 37 sit in 24 of the
69 measured files, led by `docs/prd/16-quality-controls.md` with four; 31 are
`kb/…` targets, 3 are `docs/…` targets and 3 are GitHub URLs in `README.md`. The
baseline this change was planned against — 1,966 of 5,328 over the cap — is
gone, so the offender count is no longer a corpus state but a token class.

The gate's own tests, on their own:

```
$ python3 -m pytest tests/unit/test_audit_chars.py -q
6 passed in 0.05s
```

All six behaviours pass, including `test_chars_holds_on_real_repo`
(`AC-CHARS-001`), which asserts `over == 0` on the real tree and pins
`unbreakable <= 37`: the count measured after the reflow, held as a ratchet that
may shrink and must never grow.

The five files this change adds hold the cap themselves:

```
$ python3 scripts/audit-chars.py docs/prd/26-char-per-line-audit.md \
    docs/prd/27-file-size-audit.md docs/26-char-per-line-audit.md \
    docs/27-file-size-audit.md docs/gaps/27-file-size-cap-cannot-hold.md
lines over 80 chars: 0/462 = 0.0%
OK: every measured line is within 80 chars (462 lines)
```

## What Works

- The gate holds on the real corpus: the default run exits 0 over 69 files and
  6,450 measured lines, with 0 wrap-able lines over 80 columns, so a reflow
  regression fails the `unit` job rather than landing.
- The auditor runs, is strict by default, and reports repo-relative paths with
  line numbers, so an offender is actionable without a second command.
- Fences, tables and headings are exempt by construction: a 120-character table
  row or fenced URL does not count, verified by `AC-CHARS-002`.
- Non-markdown input is measured raw: a 100-character source line is reported at
  its full width, verified by `AC-CHARS-004`.
- The `unbreakable` exemption is narrow and pinned in both directions by
  `AC-CHARS-006`: a line carrying a token wider than the cap passes and is
  counted apart, while a 120-character line of ordinary short words still fails.
- The gate enforces rather than advises: the `unit` job's `Machine gates` step
  runs the script directly, so a violation fails the job without waiting on
  pytest, and `--advisory` appears nowhere in CI.
- The audit holds its own rule — `scripts/audit-chars.py` and its test module
  are within 80 columns, verified by `AC-CHARS-005` — so the gate cannot exempt
  itself from the standard it enforces.
- `--json` carries `advisory`, `totals.unbreakable` and a per-file table, so a
  dashboard can separate real offenders from bare links.

## What Fails

- **A token wider than the cap is outside the gate's reach.** 37 over-cap lines
  survive across 24 files, each carrying one whitespace-delimited token wider
  than 80 columns — 31 `kb/…` targets, 3 `docs/…` targets and 3 GitHub URLs in
  `README.md`. The gate reports and counts them; it cannot repair them, because
  the only fix is a shorter link target, which breaks the link.
- **The 37 are a ratchet, not headroom.** `AC-CHARS-001` pins
  `unbreakable <= 37`, so the count may shrink but a 38th over-wide token fails
  the suite, and the only fix — a shorter link target or a wrapped reference —
  is manual work no gate can do.
- **Tables, headings and fences are exempt by construction.** A 400-character
  table row or heading is invisible to the measure, so width discipline there is
  editorial, not enforced.
- **Non-markdown source is only measured when named explicitly.** The default
  scope is docs prose plus the two entry documents, so a `.py` or `.yml` line is
  unchecked until someone passes the path.
- **A hand run can pass without holding the cap.** `--advisory` prints the same
  report and exits 0, and the script does not distinguish a local advisory run
  from a local enforcement run — only CI's bare invocation keeps it strict.

## Resolution

- **Unbreakable tokens:** accept them and keep the class narrow. The line is
  exempt only because one of its tokens already exceeds the cap, which
  `AC-CHARS-006` pins in both directions, so the count is a measurement to
  re-check when a link target shortens — never a licence to leave a wrap-able
  line wide.
- **The ratchet:** keep the bound at 37 and let it fall as link targets shorten.
  It is never raised, because the cap is not re-baselined to meet the corpus: a
  new over-wide token fails the suite until someone shortens it.
- **Structural exemptions:** leave them. A table's width is set by its columns
  and a fenced block is code that reflow would break; check wide tables and
  headings by eye at review time.
- **Source outside the default scope:** name the file when it matters —
  `python3 scripts/audit-chars.py scripts/gen-env.py` — and keep the default
  scope on prose, which is what the cap exists for.
- **The advisory path:** keep `--advisory` for adoption passes only. The
  `Machine gates` step runs the script bare, so a local advisory run is never
  the gate; a reflow pass drops the flag and re-runs strict before it commits.

## Verdict

`works` — the gate is live and green on this corpus: 0 of 6,450 measured lines
over 80 columns across 69 files, exit 0, with 37 unbreakable lines counted
apart. All 37 are structural — 31 `kb/…` targets, 3 `docs/…` targets and 3
GitHub URLs in `README.md`, tokens that no whitespace wrap can bring under the
cap — and they span 24 of the 69 files. Fences, tables and headings are exempt
by construction, the unbreakable rule is pinned in both directions, and the
script holds the cap it enforces; all six ACs pass too, `AC-CHARS-001` pinning
those 37 as a ratchet, so the count can only fall. What remains is the 37
tokens themselves, not the mechanism.
