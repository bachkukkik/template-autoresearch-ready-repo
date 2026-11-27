# 31 — CS-Style Arena Reference Game

> **What this records.** PRD 31 as built: one scripted two-team arena under
> `autoresearch/contract/examples/arena/`, three counterparts over ex1–ex3, and
> the tests that hold each record to its own banks. An example, not a layer —
> no engine module imports it.
> **Provenance:** the mature downstream instance
> `vanilla-open-design-autoresearch` @ `e85cc56` (an archived 1,387-line
> portable arena, plus the live league's season-38 preset), distilled into the
> kit; knowledge capture
> `kb/raw/articles/2026-11-27-cs-arena-rules-capture.md` and
> [cs-style-arena](../kb/concepts/cs-style-arena.md); intent
> [PRD 31](prd/31-cs-arena-reference-game.md).

## What

One stdlib kit — `rules.py` decides every number, `play.py` does the I/O — that
replays a two-team round from a sealed script, and three counterparts (ex1-cs,
ex2-cs, ex3-cs) that each put a different half of the settlement on the record.

## Why

PRD 28 said a game is configured downstream, never forked, and shipped no shape
to copy. A boundary with no shape is how the fork happens: a sibling repo
re-derived its own arena instead of reading one. Prose states invariants; an
example states them with numbers a reader can replay. Distilling 1,387 archived
lines into one kit keeps the cost of reading the shape below the cost of
inventing it.

## How

**The kit is pure where it can be.** `rules.py` imports only the standard
library and opens nothing, spawns nothing and reads no clock, so every economy
branch is a unit test (AC-ARN-001, AC-ARN-019). `play.py` is the only module
that touches the filesystem: `replay` writes one round's seat trees, captain
seals and settlement under `--out`; `settle` folds two seat results into a
state file. Two presets carry the economy, and only one is replayed:

| preset | base | loss bonus | buy | cap | transfer | floor step |
|---|---|---|---|---|---|---|
| `PORTABLE` | 4 | +1 | 2 at 2 | 6 | 10 | 0.005 |
| `LEAGUE_S38` | 2 | +1 | 2 at 2 | 1 | 10 | 0.005 |

`LEAGUE_S38` is the live league's collapse to one deep attempt per seat: an LLM
call that outlives its slot produces nothing, so the cap fell from 6 to 1 and
`min(2 + 1, 1)` keeps the loss bonus from ever exceeding it.

**Each counterpart proves one half.** All three import the same kit; none
re-implements it.

| counterpart | metric | what its record puts on the page |
|---|---|---|
| `ex1-music-abc-cs` | `val_bpb`, lower | a loss bonus, one paid buy (2 bank), a landing, a void round |
| `ex2-iris-knn-cs` | accuracy, higher | a fallback captain, a clamped buy, an exact tie, an unreached equilibrium |
| `ex3-hotpath-speedup-cs` | median seconds, lower | a gate-rejected attack, an audit round, arithmetic with no timer read |

**The bug this run found.** `play.py` never recorded the text that actually
landed, so `landed_text[team]` stayed `None` for a whole game: the fallback
never offered `audit`, and an audit seat was handed nothing to re-run — an
audit round could never fire, in any game. The fix is one line, at
`play.py:327`:

```python
landed_text[winner] = results[winner]["_text"]
```

The vendored ex1-cs and ex2-cs records replay byte-identical before and after,
because neither plays `audit`; ex3-cs does, and its round 2 now settles.

**ex3 compares no timing value.** A median seconds figure is a measurement this
tier cannot reproduce, so the test reads structure only: the attack's
`crash` count equals its `attempts`, its `keeps` is empty, its `best` equals
the trunk reading, and `landed` is false. The rejection is then proved to be
the gate's, not the driver's, by re-applying the attack's patches to the
pristine `train_baseline.py` in a fresh tree: exit 2, `gate_ok: False`, with
`median_seconds: 0.241895` — faster than the trunk and still rejected on
`key 'total_chars' differs`. The surviving trunk prints `gate_ok: True` and
`gate: exact match on 2 run(s)`.

## Verification

```bash
$ python3 -m pytest tests/unit/test_arena_rules.py \
      tests/unit/test_arena_examples.py -q
52 passed in 0.99s

$ python3 -m pytest tests/integration/test_arena_ex3.py -q
3 passed in 95.42s

$ python3 -m pytest tests/unit -q
726 passed, 1 warning in 78.10s

$ python3 -m pytest tests/integration -q
52 passed in 220.33s
```

The two vendored records are checked by replay, not by trust:

```bash
$ cd autoresearch/contract/examples
$ OUT=$(mktemp -d)
$ python3 arena/play.py replay --game ex1-music-abc-cs/game.py \
      --out "$OUT/ex1" > /dev/null
$ cmp "$OUT/ex1/scoreboard.json" ex1-music-abc-cs/scoreboard.json \
      && cmp "$OUT/ex1/scoreboard.md" ex1-music-abc-cs/scoreboard.md \
      && echo identical
identical
$ python3 arena/play.py replay --game ex2-iris-knn-cs/game.py \
      --out "$OUT/ex2" > /dev/null
$ cmp "$OUT/ex2/scoreboard.json" ex2-iris-knn-cs/scoreboard.json \
      && cmp "$OUT/ex2/scoreboard.md" ex2-iris-knn-cs/scoreboard.md \
      && echo identical
identical
```

The ex3 replay is the long one (about 90 s), and its output is read, never
compared:

```bash
$ python3 arena/play.py replay --game ex3-hotpath-speedup-cs/game.py \
      --out "$OUT/ex3"
round 1: passes/attack payoff 42.472896/-1.000000 A
round 2: scan/audit payoff 54.261152/0.000000 A
```

```bash
$ python3 scripts/audit-chars.py | tail -1
OK: every measured line is within 80 chars (7651 lines); 37 unbreakable

$ python3 scripts/audit-size.py --max-kb 60 | grep '^OK'
OK: 407 tracked files within 61440 bytes (largest 56312 B, ...)
```

## What Works

- **A replay is the same bytes on every machine.** Both ex1-cs and ex2-cs
  reproduce their vendored `scoreboard.json` and `scoreboard.md` exactly: no
  timestamp, no absolute path, no wall second in the record.
- **The banks are the rows.** For all three counterparts the closing bank
  equals the opening bank plus the sum of `payoff - cost` over the settled
  rows, the attack's failed attempt included as a `-1.000000` row.
- **An unserved seat voids the round exactly once.** `settle_teams` is the
  single writer of that zero: ex1 round 3 leaves both banks untouched, names
  no loser, and the row is skipped by the equilibrium.
- **The gate, not the driver, kills the attack.** The patch set applies
  cleanly to the pristine baseline and the frozen gate rejects the result on
  its own: exit 2, `gate_ok: False`, while the trunk prints
  `gate: exact match on 2 run(s)`.
- **The audit runs.** ex3 round 2 has seat B play `audit` and re-measure the
  file A landed (`kind: audit`, one attempt, `audit_hits: 0` — a clean landing
  pays nothing). Before the fix the fallback never offered `audit` and the
  seat was handed nothing to re-run, so this path was dead.
- **The example cannot fork the template.** No engine module imports the kit;
  deleting the directory would change no behaviour outside its own tests, and
  AC-ARN-032 asserts no ex4-cs or ex5-cs directory exists.

## What Fails

- **Late rounds settle 0-0.** ex1 and ex2 rounds 2–4 pay nothing: a strategy's
  pool holds one to three candidates against four to six granted attempts, so a
  seat that spends its pool records no reading — ex1 round 4 runs zero attempts
  on both seats. The examples show a first round and a void, not a season.
- **The ex2 tie sits at the measurement ceiling.** Both seats reach accuracy
  `1.000` and both are paid `7.142895`; the tie goes to the opener, so the
  winner is a rule, not an advantage.
- **A timing round has no stable winner.** ex3's payoffs, banks and trunk value
  derive from a median seconds figure this tier cannot reproduce, so the record
  proves the gate and the arithmetic and says nothing about who played better.
- **`LEAGUE_S38` is a preset no example plays.** Only `PORTABLE` is replayed;
  the league preset is pinned by unit tests (AC-ARN-001, AC-ARN-003) and never
  exercised end to end.
- **The live-mode recipe is untested in CI.** It needs a model, a wall clock
  and a network, and a captain that differs every run cannot be a fixture.
- **ex4 and ex5 have no counterpart, by design.** No two-seat transcript
  exists for the live LLM example, and the real-OSS example needs a repository
  and a heavy setup against a timing metric.
- **`tests/unit/test_arena_rules.py` has 196 bytes of headroom.**
  20,284 B against the 20,480 B default cap; CI's `--max-kb 60` hides that, and
  the next rule set would fail `audit-size.py` at its own default.

## Resolution

One resolution per failure, in the order above:

- **Late rounds 0-0** — accepted as a scripted-pool artefact: each
  counterpart's README says the second half of the game is empty by
  construction, and a live game has no pool to exhaust. The story the example
  tells is round 1 and the void; a longer one needs a live seat.
- **Ex2 at the ceiling** — keep it. A real tie is the only way to observe the
  opener rule on recorded numbers; PRD 31 states the rule as local, never
  attributed to the league.
- **No timing winner** — by design: the test reads `crash`, `keeps`, `best`,
  `landed` and the gate, never a value. Freezing a timing figure would compare
  a measurement the tier cannot reproduce, which the metric-tier doctrine
  forbids.
- **`LEAGUE_S38` unplayed** — shipped so the cap collapse is code rather than a
  footnote; a replayed S38 game needs a counterpart no transcript supports, and
  PRD 31's out-of-scope list names it.
- **Live recipe untested** — labelled untested in the arena `README.md` and in
  PRD 31's *Confidence*; the scripted replay runs the same reader, fallback,
  clamp, seal and settlement code, so only the model call is unproven.
- **ex4/ex5 absent** — documented in the `README.md` CANNOT section with the
  reason, kept absent by AC-ARN-032, and named as a follow-up issue rather than
  a promise.
- **196 bytes of headroom** — split the file by concern (economy, settlement,
  captain) with the AC ids kept in one mapping before the next rule set lands;
  do not raise the cap, which gap 27 already owns.

## Verdict

**works** — every SC has a passing test, the scripted path is byte-reproducible
on two of three counterparts and structurally checked on the third, and the two
rules exercised hardest (gate rejection, banks-as-rows) hold on recorded
numbers. The limits in *What Fails* are declared scope and scripted-pool
artefacts, not a failing path; one real defect — an audit that could never fire
— surfaced during the run and is fixed.
