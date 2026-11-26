# 30 — Measurement Coverage

> **What this records.** PRD 30 as built: cost beside score, the attempt ledger,
> the report's denominators, and the JUnit metre. Additive only — no verdict, no
> delta, no margin moves because a cost was recorded.
> **Provenance:** the veteran's two cost defects (`docs/28`, `docs/29`: a season
> reported spend `0` because the only round that spent anything died before
> settling, and a retried round overwrote its own token ledger); knowledge
> capture `kb/raw/articles/2026-11-26-veteran-decisions.md` (VD-01, VD-10,
> VD-20); intent [PRD 30](prd/30-measurement-coverage.md).

## What

One new engine module (`usage.py`), one new script (`scripts/ci_metrics.py`),
and additive fields in `loop.py`, `ledger.py` and `report.py`.

## Why

A keep rate without a denominator is a slogan. The engine published `keeps` and
`best` with no cost, and a trial that never settled wrote no row, so the
published total was silently a lower bound — the veteran's exact defect, twice.

## How

**One token reader.** `usage.py` decodes the harness transcript and accepts a
`usage` object at the top level, under `message`, or under `part`; it prefers
`total_tokens`, else sums `input_tokens + output_tokens`, and returns `None`
when no line carries usage. It lives in its own module because `adapters.py` is
already over 300 lines.

**Cost on settled trials only.** `keep`, `discard` and `inconclusive` carry
`cost = {tokens, wall_seconds}`. `wall_seconds` is the iteration's own elapsed
time from one monotonic clock started at the iteration's first line — not a
second clock, and not the run's wall. `tokens` is `null` when the transcript
carries none: absent information stays absent, never `0`.

**The attempt ledger.** A new event kind `attempt` carries
`{phase, exit_code, cost}` and is written on a `KeyboardInterrupt`
(`interrupted`) and on an unexpected exception (`agent`, `measure` or `guard`,
whichever phase the loop had reached). Two carve-outs keep it honest: the
engine's own refusals (`ConfigError`, `LedgerError`, `GitError`) write no
attempt, because a refused invocation must touch nothing; and a wall stop writes
none, because the wall is only checked *between* iterations, so it always
follows a settled trial and an attempt there would double-count.

**The report says what it measured.** A `## Cost` section prints
`keeps: k / n settled`, then `keeps / 100k tokens` and `keeps / hour`, each with
its own `n/a (<reason>)` form. The numerator is read from the same subset as its
denominator, so a leg with no token usage cannot inflate a ratio. When attempts
exist, `## Result` gains
`unsettled: N attempt(s) — the totals above are a lower bound`. `results.tsv`
gains two trailing columns, empty when unknown.

**The metre is a script, not a gate.** `scripts/ci_metrics.py --junit <file>`
prints a fixed-width table per suite (cases, fail, error, skip, seconds) and one
total line; a missing or non-numeric `time` counts `0.00` and the row is flagged
`?`; a missing or unparseable file exits 2 with one stderr line.

## Verification

```
$ python3 -m pytest tests/unit/test_engine_cost.py \
      tests/unit/test_engine_attempts.py tests/unit/test_ci_metrics.py \
      tests/integration/test_measurement_report.py -q
25 passed

$ python3 -m pytest tests/unit -q
657 passed, 1 warning

$ python3 -m pytest tests/integration -q
49 passed

$ python3 scripts/audit-chars.py ; python3 scripts/audit-size.py --max-kb 60
OK: every measured line is within 80 chars (7014 lines); 37 unbreakable
OK: 386 tracked files within 61440 bytes

$ python3 scripts/audit_pyramid.py
OK: 3 foundations green (34 files, ratio 5.8%)

$ python3 -m pytest tests/unit/test_ci_metrics.py -q --junitxml=/tmp/u.xml
$ python3 scripts/ci_metrics.py --junit /tmp/u.xml
suite                                         cases   fail  error   skip   seconds
----------------------------------------------------------------------------------
pytest                                            7      0      0      0      0.95
total                                             7      0      0      0      0.95

$ python3 scripts/ci_metrics.py --junit /tmp/nope.xml ; echo "exit=$?"
ci_metrics: /tmp/nope.xml: no such file
exit=2
```

**A verdict cannot be bought.** AC-MCV-005 runs the same scripted trial twice —
once where the agent prints `{"message": {"usage": {input 900, output 334}}}`,
once silent — and asserts `outcome`, `metric`, `margin`, `se`, `spread`,
`values`, `guard` and the derived delta are equal, while `cost.tokens` reads
`1234` against `null`.

## What Works

- **Absent stays absent all the way out.** No usage means `tokens: null` in the
  event, an empty tsv cell, and `n/a (no token usage)` in the report. Nothing in
  the chain turns "I do not know" into `0`.
- **The attempt row is written where a run actually dies.** An interrupt and an
  exception mid-iteration both leave a row with the phase they reached; the
  ledger and the report accept it without any existing count moving.
- **The metre is readable in one screen** and its own failure mode is a clean
  exit 2, not a traceback.
- **The additive rule held.** The only pre-existing assertions touched are two
  exhaustive enumerations that any new field must extend — the tsv header and
  `OFF_TRIAL_KEYS` — and both changes are one line.

## What Fails

- **A killed process writes no attempt.** `SIGKILL`, an OOM kill or a container
  reap leaves the ledger exactly as it was: no row, no cost, no explanation. The
  attempt ledger covers the paths the process still controls.
- **A wall stop writes no attempt.** The wall is checked between iterations, so
  a wall stop always follows a settled trial. That makes the double-count
  impossible, and it also means a run that burned its whole budget on one
  expensive iteration reports one settled trial and no attempt.
- **Token cost exists only where the harness prints it.** A harness that writes
  prose yields `null` forever, so `keeps / 100k tokens` is `n/a` on exactly the
  adapters that would benefit most from a cost number.
- **`keeps / hour` is trial time, not run time.** Git operations, guard runs
  outside the timed window and idle between iterations are excluded, so the
  ratio flatters a run whose overhead is large.
- **`ci_metrics.py` measures and never gates.** A suite that doubles its runtime
  prints a bigger number and nothing fails. Wiring it into CI would make a slow
  suite red, which is a separate decision this PRD deliberately did not take.
- **The report's `n/a` forms are three separate strings.** A reader parsing the
  report rather than a human reading it will find no numeric value there, which
  is correct but easy to mis-handle.

## Resolution

One resolution per failure, in the order above:

- **Killed process** — accepted as out of scope: an attempt row needs a live
  process. The mitigation is a run-level marker (the engine already writes one
  for the supervisor), and reconciling it is a separate PRD.
- **Wall stop** — keep the carve-out and say so, as this record does; the
  alternative double-counts a settled trial.
- **Harness without usage** — the same "one pinned transcript per harness" item
  that `docs/29` records; when a harness prints usage, its fixture proves the
  reader, and until then `n/a` is the honest answer.
- **`keeps / hour` is trial time** — rename nothing, document it: the section is
  `## Cost` and the line says what it divides by; a run-level ratio is a
  different line for a different PRD.
- **`ci_metrics.py` never gates** — deliberate, stated in the PRD and here; the
  measurement ships first so that any later threshold is chosen against real
  numbers.
- **Three `n/a` strings** — a test pins each form, so a parser breaks loudly at
  the pin rather than silently reading a zero.

## Verdict

**works** — the fields are additive and proven not to move a verdict; the
attempt row covers the paths a live process can report; the metre answers "which
tier costs the wall clock" on a real JUnit file. The limits are in *What Fails*:
the number is honest about what it does not know, which is the whole point of
the PRD.
