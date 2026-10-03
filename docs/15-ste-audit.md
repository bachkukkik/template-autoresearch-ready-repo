# 15 — STE-style Audit

## What

`scripts/audit-ste.py` measures markdown prose against the machine-checkable half of the
output-medium doctrine's rung 2 — controlled English, ASD-STE100-style — namely the
sentence-length cap and passive-voice constructions. It exits `0` when the share of
within-limit sentences is at least the threshold (default 80%), and `1` otherwise.

## Why

- Rung 2 of the ladder is controlled English. The recommendation is to write "80% of the
  way to ASD-STE100", so the target is a share, not perfection.
- The ASD-STE100 dictionary is copyrighted and is not vendored, so only the rules that
  need no dictionary are machine-checkable.
- A prose rule with no tripwire decays. The audit is that tripwire for this repo's docs.

## How

Stdlib-only Python 3, one file, about 150 lines, no config files.

- `strip_markdown` removes fenced code, tables, headings, list markers and footnote
  markers.
- `split_sentences` splits on `[.;:]` plus whitespace, but protects the common
  abbreviations (`e.g`, `i.e`, `vs`, …) and the section form `§ N.`.
- `measure` counts the sentences over `--max-words` (default 25, descriptive), the longest
  sentence, and passive-voice matches (`be`-verb plus past participle).
- The default inputs are `docs/*.md` and `README.md`, anchored at the repo root.

Exit `0` when the within-limit share is at least `--threshold` (default 80). Otherwise
exit `1` and print every offender as `file: [Nw] first 100 chars`.

| Flag | Default | Meaning |
|---|---|---|
| `--max-words` | 25 | descriptive sentence cap, in words |
| `--threshold` | 80 | minimum share of within-limit sentences, in percent |
| `--verbose` | off | print the per-file table even on success |

## Verification

Run from the repo root, 2026-10-03.

```bash
python3 scripts/audit-ste.py --verbose
# -> within-limit: 1447/1462 = 99.0% (threshold 80%)   exit 0
python3 -m pytest tests/unit/test_ste_audit.py -q
# -> 3 passed
python3 -m pytest tests/unit -q
# -> 135 passed
```

Expected: the share is at least 80%, so exit 0, and the three AC-STE guards pass.

## What Works

- The repo's own docs pass at 99.0% (1447/1462), 19 points above the 80% floor. The three
  stage-6 docs added in this change measure 0 over-limit sentences each.
- AC-STE-001 asserts the real docs pass. A doc edit that drops the repo below 80% fails
  CI before merge.
- AC-STE-002 proves the auditor discriminates: a 60-word sentence fails at threshold 80
  and passes at 50, and a 60-word line inside a code fence is exempt.
- AC-STE-003 pins the CLI contract: `--help` exits 0, and a missing input file exits 1
  while naming the path.
- The auditor is hermetic. The test loads it by path and drives `main(argv)` in-process —
  no subprocess, no transport.

## What Fails

- **Two rules only.** The dictionary-dependent rules — approved vocabulary, one word per
  meaning, no gerunds — are not checked, because the ASD-STE100 dictionary is ASD's
  copyright and is never vendored.
- **A share, not a verdict.** The default 80% threshold passes a document with a minority
  of long sentences, exactly as the recommendation intends. It cannot certify a rung-2
  document.
- **Sentence splitting is heuristic.** The splitter protects a fixed abbreviation list. An
  unlisted abbreviation before a period splits a sentence and can cause a false positive.

## Resolution

- **Two rules only:** the audit covers rung 2's machine-checkable half, and the human
  rules stay in review. The script docstring and `docs/prd/15-ste-audit.md` state the
  scope.
- **A share, not a verdict:** the threshold is a floor for the repo, not a quality target
  for one document. Raise `--threshold` for a stricter run.
- **Heuristic splitting:** add the abbreviation to `PROTECTED_BEFORE_PERIOD` when a false
  positive appears — the list is data, not logic.

## Verdict

**works** — The auditor runs 99.0% within limit over the repo's own docs, 19 points above
its 80% floor, and three hermetic unit guards (AC-STE-001..003) pin the threshold, the
discrimination and the CLI contract. The recorded limits are the two-rule scope (the
dictionary is not vendored), the share-based threshold, and the fixed abbreviation list.
