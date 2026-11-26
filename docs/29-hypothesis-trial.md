# 29 — Hypothesis-Driven Trial

> **What this records.** PRD 29 as built: an opt-in claim on the mandatory
> `CHANGE:` line, one reader that matches the harness it reads, a hypothesis
> object beside every settled trial, refutation memory, and a t-quantile margin.
> **Provenance:** the veteran's two seasons graded blind
> (`vanilla-open-design-autoresearch` `docs/41`, `docs/42`) and the margin TODO
> its `decide.py` had carried since the eval layer landed; knowledge capture
> `kb/raw/articles/2026-11-26-veteran-decisions.md` (VD-03, VD-04, VD-05);
> intent [PRD 29](prd/29-hypothesis-trial.md).

## What

`autoresearch/engine/autoresearch/claim.py` (159 lines, stdlib only) plus an
opt-in path through `prompt.py`, `config.py`, `cli.py`, `loop.py` and
`report.py`. Two new `run` flags: `--hypotheses` and
`--margin-quantile {z,t}`.

## Why

The keep gate grades an outcome, never a prediction, so the ledger could not
separate an idea that was tested and held from one that was changed at random
and happened to move the number. The veteran paid twice to learn that the fault
in its own attempt was never the agent's: both seasons printed the claim and
both recorded `hypothesis: null`, because the reader scanned raw stdout lines
while the harness emitted JSONL. A second season then lost a seat to a
typewriter's minus sign, `U+2212`, which `float()` refused.

The margin defect was already written down in this tree. `decide.py` said:
`Z = 1.96` is the asymptotic quantile and "a future PRD may switch to `t`-based
margins". At the smallest honest sample the true value is 12.706.

## How

**One claim line.** With `--hypotheses`, instruction 6 of the prompt becomes a
single line carrying four labelled fields: `CHANGE:`, `HYPOTHESIS:`,
`PREDICT:`, `FALSIFIED IF:`. The word `HYPOTHESIS:` appears exactly once in the
rendered prompt.

**One reader, matched to the harness.** `claim_from_transcript` walks the
transcript line by line. A JSON line yields text only from an assistant text
part — three shapes are accepted (`{"type":"text","part":{"text":…}}`,
`{"part":{"type":"text","text":…}}`, and an assistant `message.content` list
whose elements are typed `text`). Every other key is ignored on purpose: a claim
echoed inside a tool result is **not** a claim. A non-JSON line is scanned as
plain text, so a harness that prints prose still works. The number parser maps
`U+2212`, `U+2013` and `U+2014` to `-`, tolerates `+`, whitespace and a trailing
unit word, and returns `None` rather than raising.

**One object beside the result.** A settled trial carries
`hypothesis = {text, predict, falsified_if, sign_match, calibration}`.
`sign_match` is `true`/`false` only when both sides are measured and non-zero,
`null` otherwise; `calibration` is `"sign"` or `"n/a"`. An opted-in trial with
no claim carries `hypothesis: null` and is reported as unread, never as
non-compliant.

**Refutations are remembered, crashes are not.** A sign mismatch appends
`{text, reason, count}` to `state_dir/refuted.json`, incrementing `count` on an
exact text match and keeping the last ten distinct texts. The file is written
atomically (tmp + `os.replace`). `agent_error`, `crash` and `guard_failed` never
append and never increment — the veteran's season-25 defect, where a dead seat
was priced as stagnation.

**The margin chooses its quantile.** `T_QUANTILES_975` carries the published
two-sided 95% Student-t values for `df` 1..30; `t_quantile(df)` returns the
table value, and falls back to `Z` for `df <= 0` or `df > 30` rather than
raising.
`margin(..., quantile_name="t")` multiplies the SE by `t_quantile(n - 1)`, where
`n` is the honest repeat count the SE came from; fewer than two repeats falls
back to `Z`. The default is `"z"` and computes `Z * se` exactly as before.

## Verification

```
$ python3 -m pytest tests/unit/test_hypothesis_claim.py \
    tests/unit/test_engine_prompt.py tests/unit/test_engine_decide.py \
    tests/unit/test_engine_ledger.py tests/unit/test_engine_loop.py \
    tests/unit/test_engine_report.py tests/unit/test_veteran_register.py -q
121 passed

$ python3 -m pytest tests/unit -q
634 passed, 1 warning

$ python3 -m pytest tests/integration -q
47 passed

$ python3 scripts/audit-chars.py
OK: every measured line is within 80 chars

$ python3 scripts/audit-size.py --max-kb 60 ; python3 scripts/audit_pyramid.py
OK: 386 tracked files within 61440 bytes
OK: 3 foundations green (34 files, ratio 5.5%)
```

**The off path is proved, not asserted.** Three independent checks:

1. `tests/unit/test_engine_prompt.py` (AC-ENG-070..076) is untouched and still
   renders and pins the default prompt.
2. AC-HYP-001 pins the whole prompt byte-for-byte against a capture taken before
   any edit, and pins the trial key set — no `hypothesis` key, no `refuted.json`,
   no `calibration` line.
3. `tests/unit/test_eval_statistics.py` — its
   `test_the_recorded_margin_is_the_one_the_verdict_used` case spies on
   `decide.margin` with its **old** signature and still observes exactly two
   calls — which is why the loop passes `quantile_name` only when it is
   non-default.

A side-by-side run of the pre-change engine and the working tree on identical
fixtures produced a byte-identical prompt and `results.tsv`, and
`run.json`/`report.md`/`events.jsonl` identical modulo path, sha, timestamp and
elapsed seconds.

## What Works

- **The reader is tested against the harness, not against an ideal.** A claim in
  a tool result is ignored, a claim in an assistant text part is read, and the
  U+2212 case that cost the veteran a seat is a fixture.
- **`null` is a first-class outcome.** An unread claim is recorded as `null` and
  the report says `calibration: n/a (no numeric predictions measured)` rather
  than scoring compliance the archive cannot support.
- **The t table is boring on purpose.** Thirty published values and a fallback,
  which is far easier to review than an incomplete-beta implementation nobody
  would test.
- **The flag genuinely gates the feature.** No flag, no key, no file, no line.

## What Fails

- **Last claim wins.** If an agent prints a claim and then summarises in a later
  assistant message, the summary — if it repeats the labels — is the one read.
  The veteran's convention is one line at the end, so this is right for the
  convention and wrong for a chatty harness.
- **Three transcript shapes, no more.** A harness whose JSONL nests text
  differently is a reader defect waiting to happen. The mitigation is a fixture
  per harness, not a cleverer parser; that fixture does not exist yet for any
  harness but the one in the integration test.
- **Calibration grades the sign, not the magnitude.** A claim of `-1` that
  realises `-40` scores the same as `-1` realising `-1.2`. That is deliberate —
  requiring a magnitude band would fail most honest claims — but it means
  "calibration" is a misnomer for what is measured.
- **`--margin-quantile z` does not reset a recorded `t`.** The default flag
  defers to `run.json`; the CLI value wins only when non-default. That is
  byte-identity's price, and it is surprising enough that an operator switching
  back to `z` on an existing run dir will not get what they typed.
- **No live model has driven it here.** Every AC runs against a scripted agent;
  the prompt contract has never been served to a real harness from this tree.
- **`refuted.json` is per state dir, not per claim lineage.** Two runs sharing a
  state dir share the memory; the cap is ten distinct texts, so a long campaign
  forgets the oldest refutation silently.

## Resolution

The open items are recorded rather than scheduled. One resolution per failure,
in the order above:

- **Last claim wins** — correct for the one-line convention this PRD asks for;
  if a second harness is trusted, its fixture decides, not a parser change.
- **Three transcript shapes** — take one recorded transcript per supported
  harness and pin it as a fixture, so VD-03 is enforced per adapter instead of
  once. This is the next item worth doing.
- **Calibration grades the sign** — a PRD edit if the word is ever read as a
  magnitude measure; the metric's own name is the fix.
- **`z` defers to a recorded `t`** — a line in the `run` help text; no code
  change, because byte-identity is the constraint that produced it.
- **No live model yet** — recorded as a limit, not a task: the first real run is
  the adopter's, and its transcript becomes the second pinned fixture.
- **`refuted.json` is per state dir** — accepted: a campaign that wants isolated
  memory uses an isolated state dir, which `--state-dir` already gives it.

## Verdict

**works** — the feature is live behind a flag, the flag-off path is proved
byte-identical three ways, and the reader is tested on the exact two defects
that cost the veteran two seasons. The limits in *What Fails* are the honest
boundary of a first instrument: one harness shape proved, five more assumed.
