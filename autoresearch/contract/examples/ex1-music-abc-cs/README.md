# ex1-music-abc-cs — a two-seat arena over `val_bpb`

The same music-ABC example ex1 already ships, played as a game: two seats, one
frozen `prepare.py`, a bank, a sealed captain per seat and a settlement. The
evaluator, the baseline and the candidates are ex1's own — `game.py` only
declares how they become a game. See `../arena/README.md` for the rules.

Nothing here is random. `play.py` replays `game.py` deterministically, so
`scoreboard.json` and `scoreboard.md` are byte-identical on any machine; they
are the vendored record of the replay below.

## The story the record tells

Trunk start `3.765056` (unigram, `alpha=1.0`, no context). Four rounds,
`PORTABLE` economy, A opens the odd rounds.

| round | opener | A / B strategy | payoff A / B | what happened |
|---|---|---|---|---|
| 1 | A | context / smoothing | 42.137169 / 0.000717 | A's lam sweep lands `lam=0.7` → `2.178568`; B keeps a 0.0007 smoothing gain |
| 2 | B | context / context | 0.000000 / 0.000000 | B lost, so it gets the loss bonus *and* buys: 6 attempts, 3 used, none better than the trunk A already landed |
| 3 | A | smoothing / smoothing | 0.000000 / 0.000000 | B never gets its slot (injected) → the round is void; A's `alpha=0.5` gain is discarded |
| 4 | B | smoothing / smoothing | 0.000000 / 0.000000 | both pools are spent: zero attempts, a 0-0 tie to the opener |

Round 2 is the economy's point in one row: B's bank paid `2` for one extra
attempt and that attempt found nothing, because the trunk already held the
best candidate the pool had. Round 3 is the fairness rule's point: a seat that
is never served voids the round rather than scoring it, and the other seat's
work does not silently land either. Round 4 is the honest ending — with both
pools spent the record shows zero attempts, not invented work.

Final: banks A `46.137169`, B `2.000717`; trunk `2.178568` (ex1's own best
`val_bpb`). Equilibrium: **not reached** — with the trunk at the pool's best,
`context`-vs-`smoothing` still pays `42.137169` more than the cell A ended on,
against a threshold of `2.5`. Every cell was explored; the regret alone blocks
the verdict, which is the honest reason to keep playing.

## What it proves

- Two seats on one frozen evaluator, with a bank that pays for attempts and
  charges for them (`cost` in every row).
- The loss bonus and the R36 clamp: a loser gets base 5, buys 2, and receives
  one extra attempt for `2` because the cap leaves room for one.
- A void round: labelled `injected`, both payoffs zeroed by the settlement,
  banks untouched, no winner, no landing.
- Payment only for work that landed: A's round-3 keep is real and still pays
  nothing, because the round was void.
- An honest equilibrium verdict: `reached: false` with the regret named.

## How to replay

```bash
cd autoresearch/contract/examples
python3 arena/play.py replay --game ex1-music-abc-cs/game.py \
  --out "$TMPDIR/ex1-cs"
diff -r "$TMPDIR/ex1-cs/scoreboard.json" ex1-music-abc-cs/scoreboard.json
```

Run it twice into two `--out` directories and `diff -r` them: identical. Never
replay into the example directory — it would overwrite the vendored record with
your own seat scratch. Seat directories (`seat-*/`, `trunk-measure/`,
`landing/`) are gitignored and never vendored; `round-N/` carries only the
sealed captains.

## Files

| file | what it is |
|---|---|
| `game.py` | the `GAME` declaration: base, editable file, metric, rounds, strategy pools, scripted captains, the injected unserved seat |
| `scoreboard.json` | the full record: every round's captains, results, payoff, banks, matrix and equilibrium |
| `scoreboard.md` | the same record as one table row per round |
| `round-N/captain-{A,B}.json` | the sealed captain choice, canonical JSON |
| `round-N/captain-{A,B}.sha256` | sha256 of that json file, exactly as written |

The captain replies are scripted text, not a model's output: CI cannot afford a
model call per round, and a replay must be deterministic. A live round uses the
recipe in `../arena/README.md`.
