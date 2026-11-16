---
source_url: https://github.com/vanilla-republic/vanilla-open-design-autoresearch
ingested: 2026-11-16
sha256: 906a1ab068e9103b388b4742be464342f92eb450b52cd75582047390390e311c
source_type: code-capture
kind: article
title: "Objective and run records — the lineage validator and the close record (code capture)"
---

# Objective and run records — a code capture

## Provenance

**What.** The two tracked records that make a downstream league season comparable, read
from the code and the committed files rather than from prose:
`autoresearch/league/lineage.py` (the module docstring, `REQUIRED_METRIC_FIELDS`,
`_metric_problems`, `_game_problems`, `validate`, `names`, `direction_of`,
`active_game`), `autoresearch/league/metrics.json` (six metrics, nine fields each),
`autoresearch/league/games.json` (three games: `g0`, `g1`, `g2`), all seven
`autoresearch/league/ledger/season-*.json` close records, and
`autoresearch/league/season19-legs.json` (the per-leg readings rows). Read-only,
2026-11-16.

**What it is not.** The 4,980-line `arena.py`, the 2,580-line `referee.py`, the captain
economy, the seats and the media are not captured. Only the record shapes, the
validation rules and the lookups are.

**Labels.** `[M]` read directly in the code or the file at the path cited; `[S]` stated
by the downstream repo's own record; `[I]` inference.

**Why this repo cares.** The template's engine records a baseline and trials, and its
report answers "what did this run do". Nothing records *what was optimised* across runs,
and nothing records a reading with the evaluator's own line beside it.

## Two files, two shapes

`lineage.py` states the split in its docstring `[M]` (lines 1-48):

| File | Shape | Answers |
|---|---|---|
| `metrics.json` | a registry: `{"metrics": [ ... ]}` | what can be measured, and how |
| `games.json` | a lineage: `{"games": [ ... ]}` | what a period optimises, and what it forked from |

A game entry is `{id, parent, status, legs, readings, rules, seasons, dry_streak,
reason, notes}` `[M]` (`games.json`). `legs` is a **map of name to weight**
(`{"better": 0.6667, "cheaper": 2.0, "faster": 0.5}`), and `readings` is the list of
metrics the game records without pricing (`["fresh"]`) `[M]`.

## The nine-field metric contract

`lineage.py:75-85` `[M]`:

```
REQUIRED_METRIC_FIELDS = (
    "name", "direction", "unit", "command", "repeats",
    "noise_floor", "exploit", "cheat_probe", "guard",
)
```

The docstring's justification is the part worth porting: a metric with no `command`
cannot be re-measured next season; one with no `exploit` has not been told what could
game it; one with no `cheat_probe`/`guard` is a number a faker can move without a
consequence `[M]`. `DIRECTIONS = ("lower", "higher")` at line 90 `[M]`.

`direction_of(metrics, name)` (`lineage.py:363-384`) refuses an unregistered name rather
than defaulting, and refuses a declared-but-unusable direction: "not lower" is not
"higher" `[M]`. It resolves the **first** registry entry whose name matches, which is why
a duplicate name is a validation error rather than a harmless redundancy `[M]`.

`metrics.json` additionally carries a `baseline` block per measured metric — for
`spec_gap`: `{value: 140, declared: 1027, credited: 887, commit: b95ff0b7e171,
command, measured: "2026-11-14"}` plus `noise_floor_source` and a
`baseline_sensitivity` sentence naming three reads of the same metric at `origin/uat`
(140), `ca6b551` (133) and a trunk worktree (30) `[M]`. The denominator is recorded as a
triple, never as one number.

## Validation: raise on unreadable, list every contradiction

Two loaders, two halves, one cross-check `[M]`:

- `load_metrics` / `load_games` raise `LineageError` naming the path when the file is
  unreadable or not a `{key: [...]}` object — an operator error stops the read.
- `_metric_problems` and `_game_problems` **return** every contradiction, and
  `validate(metrics, games)` concatenates them plus the one rule neither file can answer
  alone: a leg naming an unregistered metric.

The rules, as the docstring numbers them `[M]` (`lineage.py:23-48`): every required
metric field; a declared direction; unique metric names; every leg registered; exactly
one active game; one game per season; a parent that exists and a chain that ends; an
active game with legs. The comment above them says why they are not hygiene: each
refuses a record that would still load and still play while paying for something nobody
can measure `[M]`.

## Fork, retire, and the floor

`games.json` is the record the module makes possible `[M]`:

- `g0` (root, archived) priced `better 0.6667 / cheaper 2.0 / faster 0.5` over seasons
  1-17, with `fresh` as a reading only.
- `g1` (parent `g0`, archived) dropped `faster` to a reading and added `spec_gap 1.0`
  for seasons 18-22. Its `reason` is written against the parent's measured exhaustion:
  "better and fresh both closed season 17 at their floor (0), cheaper proved unmovable
  across two season-16 iterations, and faster's measured band (4.2 %) is wider than any
  win a round can produce" `[M]`.
- `g2` (parent `g1`, active) prices `better 1.0 / spec_gap 1.0` for season 23, drops
  `cheaper` to a reading, and its reason records that season 22 played `cheaper` eight
  times across both seats for `1313437` bytes before and after `[M]`.

`g1.notes` records the record-drift failure in the repo's own words: seasons 20, 21 and
22 were played on `g1` but never listed, so a close called them `g0`'s; they are listed
now `[S]`. `g2.notes` records season 23 attributed to `g0` at close for the same reason,
and says the close record is not rewritten because "a close record is the season's own
output" `[S]`.

`rules.jackpot_keys` rides the legs with measured headroom — `["better","cheaper",
"faster"]` on `g0`, `["spec_gap"]` on `g1` and `g2` — and `g1.rules.why` states the rule
that produced it: "the pot rides the one leg a round can still move … a jackpot over
[`better`] could never fire" `[M]`.

## The close record

One file per season under `autoresearch/league/ledger/`. Counted from the seven
on-disk files `[M]`:

| Season | Keys | What it has |
|---|---|---|
| 17-18 | 15 | `archived_rounds banks circumstance floor_after floor_before game head keeps matrix review rounds rounds_played season weights_after weights_before` |
| 19-22 | 18 | the above plus `baselines close_commit season_start_commit` |
| 23 | 19 | the above plus `referee` |

`keeps` is `[{commit, round, team}]`; `matrix` is one row per round with each seat's
legs, events, improvement, landed flag, payoff and reading status `[M]`. `review` is a
record, not prose — `{means, previous, reason, weights}` — and season 23's reason reads
"stagnant better priced up; the three weights average 1.0 before the final clamp (means
{'better': 0.0, 'spec_gap': 0.084094})" `[M]`.

`baselines` carries a commit per leg, and `spec_gap`'s entry carries `declared 1027 /
credited 946 / uncovered 81` beside `{commit, value}` `[M]` (`season-23.json`). That is
the pinned-denominator rule as data: the numerator and the denominator are recorded
together.

The 19-key record arrives with `referee`, which scores the operator: season 23's block is
`{penalties: ["r4: a round neither team moved anything", ...], rewards: [...], score: 2}`
`[M]`.

## The per-leg reading row

`season19-legs.json` carries a `legs` list whose rows are exactly
`{name, unit, lower_is_better, before, after, command, raw, verdict, note}` `[M]`:

```
{"name": "spec_gap", "unit": "ids", "lower_is_better": true,
 "before": 140, "after": 113,
 "command": "autoresearch/bin/autoresearch referee measure --target ... --metric spec_gap --base arena/trunk",
 "raw": "spec_gap: uncovered=113 of 1027 declared at 608e17d2dc03",
 "verdict": "improved",
 "note": "27 ids covered by two keeps ... Declared 1027 unchanged, so the denominator did not move; this is play, not relocation."}
```

`raw` is the referee's own output line, not a paraphrase `[M]`. The verdict is prose-only
downstream: season 18's record labels `faster` 82.624 → 61.973 `displaced`, season 19's
labels 61.973 → 38.861 `held` although it moved, and both docs call the move relocation,
not play `[S]`. That drift is why the template makes `verdict` an enum with a required
note.

## The honest-verdict checklist

Ten questions a record must answer before its number is called a win `[S]` (the league
converged on them across PRs #27-#45): the two commits named; the noise floor measured;
the denominator pinned and declared/credited/uncovered recorded together; the instrument
unchanged (size and hash beside the score); the unit actually served; the guard run
before the bank; landing proved by patch-id, not ancestry; the artefact of the loss kept
with its hash; the operator scored; every count in the prose re-derived and proved by a
re-render that fails on drift.

Four of them have a measured failure behind them `[S]`:

- **Solved but unbanked.** Season 18 round 60 drove `spec_gap` 30 → 0 in a worktree, both
  agent calls timed out, so `keeps: 0` and nothing was cherry-picked.
- **A pot paid on an unkept tree.** The same round's jackpot fired off a worktree
  snapshot the engine never accepted.
- **A baseline read at different commits.** `spec_gap` read 140 at `origin/uat`, 133 at
  the round's base and 30 in the worktree; `faster` "improved" 82.624 → 61.973 s while
  `tests/docker-free.txt` fell from 55 bats entries to 36.
- **A vacuous zero-row.** An archived corpus carrying no `landed` key printed "0 landed
  keeps" — absence, not measurement.

## What this port takes, and leaves

**Taken** (the generic core): the two-shape split where a record declares what is
optimised; the nine-field leg contract with an explicit `guard` and `noise_floor`; refuse
directions, never default them; exactly one active objective and one owner per period; a
parent chain that is rooted and acyclic with a reason owed by every fork and retirement;
a leg at its floor leaves the rotation and the rotation is exactly as long as the
playable legs; every contradiction in one list; the close record with named commits,
per-leg baselines, keeps, a review record and the operator's own check; the reading row
with the evaluator's own `raw` line and a verdict classified by cause; `--check` that
re-renders and fails on drift.

**Left downstream** (SPECIFIC): the captain economy, seats, buys, buzz, the pot and its
`jackpot_keys`, band-gated pay, the roster of six metrics, the media and the season
pages, and `dry_streak` — which is declared in the schema, printed by one prompt, and
written or read by no code `[M]`.

**This repository's implementation** (not downstream evidence, recorded so the capture
is not mistaken for a specification): `autoresearch/objective/registry.json` plus
`autoresearch/engine/autoresearch/objective.py` (validator and resolver),
`autoresearch/engine/autoresearch/record.py` (close record and `--check`),
`init --objective/--objective-leg` deriving the engine's one metric from the resolved
leg, and `report --record/--check`. A leg may declare `best` and `floor` so the at-floor
rule is answerable once a measurement exists; weights are kept as data but nothing is
repriced; `dry_streak` is not ported. See
[kb/concepts/objective-as-record.md](../concepts/objective-as-record.md) and
[kb/concepts/run-record-contract.md](../concepts/run-record-contract.md).
