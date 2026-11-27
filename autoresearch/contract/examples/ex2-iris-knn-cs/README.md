# ex2-iris-knn-cs — a two-seat arena where the metric runs out

ex2's iris kNN, played as a game with the direction inverted (`accuracy`,
higher is better — the same inversion ex2's own ledger uses). One frozen
`prepare.py`, two seats, four rounds, `PORTABLE` economy. See
`../arena/README.md` for the rules; `game.py` declares how ex2 becomes a game.

The replay is deterministic, so the vendored `scoreboard.json` and
`scoreboard.md` are the record of exactly what `play.py` prints on any machine.

## The story the record tells

Trunk start `0.933333` (1-NN, Euclidean, raw features). A opens the odd rounds.

| round | opener | A / B strategy | payoff A / B | what happened |
|---|---|---|---|---|
| 1 | A | k / k | 7.142895 / 7.142895 | both sweep K=3 → 5 → 7; both land on `1.000000`; an exact tie goes to the opener |
| 2 | B | vote / k | 0.000000 / 0.000000 | A asks to buy 3, is clamped to 2, pays `4` and gains nothing; B's reply is malformed and falls back to a spent pool |
| 3 | A | distance / vote | 0.000000 / 0.000000 | normalization drops the score to 0.933333, Manhattan only ties the ceiling; the weighted vote ties too |
| 4 | B | k / distance | 0.000000 / 0.000000 | both pools are spent: zero attempts, a 0-0 tie to the opener |

Round 1 is the ceiling: 1.000000 is every test row, so two equal bests produce
an exact tie and the seat that had to move first keeps the trunk. Rounds 2-4
are what a reached ceiling does to an economy — nothing can pay, so every
round ties at zero, the opener takes it, and the bank column stops moving
except for what a buy costs. That is the honest record; the script did not
invent a late improvement to make the ending livelier.

Two captain rules show up in round 2. A's `buy: 3` is **clamped** to the
economy's `buy_max` of 2 with `"clamped": true`, and the R36 clamp then leaves
room for both bought attempts — so A is granted 6 attempts and pays `4` for
them, of which it needs one. B's reply contains no JSON object at all, so
`parse_captain` records the fallback: strategy `k`, buy 0, reason
`captain fallback` — and `k` is already spent, which the round shows as zero
attempts rather than an invented candidate.

Final: banks A `7.142895`, B `11.142895`; trunk `1.000000`. Equilibrium:
**not reached** — A's `distance`-vs-`distance` cell was never played
(`unknown: ["distance"]`), and B's regret against `k`-vs-`k` is `7.142895`
against a threshold of `2.5`. A verdict of "not yet" is the point: the matrix
was not explored, so no one may claim the game is solved.

## What it proves

- Direction inversion survives the game: every comparison in the seat loop and
  in the settlement is direction-aware, and a lower accuracy is never a keep.
- An exact tie is not ambiguous: `round_winner` gives it to the opener, so the
  trunk advance is decided.
- A captain reply is parsed, not trusted: one clamped integer and one
  fallback, both sealed before the round was played.
- The equilibrium verdict is honest: it stays `false` while a cell is
  unexplored, even though A's own regret is zero.
- The economy does not mint headroom: at the ceiling a buy is pure cost.

## How to replay

```bash
cd autoresearch/contract/examples
python3 arena/play.py replay --game ex2-iris-knn-cs/game.py \
  --out "$TMPDIR/ex2-cs"
diff -r "$TMPDIR/ex2-cs/scoreboard.json" ex2-iris-knn-cs/scoreboard.json
```

Two runs into two `--out` directories diff clean. Never replay into the
example directory: it would overwrite the vendored record. Seat scratch
(`seat-*/`, `trunk-measure/`, `landing/`) is gitignored and never vendored.

## Files

| file | what it is |
|---|---|
| `game.py` | the `GAME` declaration: base, editable file, metric, rounds, three strategy pools, scripted captains |
| `scoreboard.json` | the full record: captains, results, payoff, banks, matrix, equilibrium |
| `scoreboard.md` | the same record as one table row per round |
| `round-N/captain-{A,B}.json` | the sealed captain choice, canonical JSON |
| `round-N/captain-{A,B}.sha256` | sha256 of that json file, exactly as written |

Captains are scripted text, not a model's output, so the replay is
deterministic. A live round uses the recipe in `../arena/README.md`; the
engine, not this file, would supply the candidates.
