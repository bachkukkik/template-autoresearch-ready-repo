# ex3-hotpath-speedup-cs — a two-seat arena over `median_seconds`

The same hot-path example ex3 already ships, played as a game: two seats, one
frozen `prepare.py`, a bank and a sealed captain per seat. The evaluator is
ex3's exact-output gate, so a candidate is valid only when it reproduces the
frozen reference on both the seeded and the held-out workload; speed is
measured afterwards, never instead. `game.py` only declares how the example
becomes a game — see `../arena/README.md` for the rules.

Two rounds, `PORTABLE` economy, A opens round 1. Nothing here is vendored: the
metric is wall-clock time, and the next section says why that forbids a record.

## The story the record tells

| round | opener | A / B | what happened |
|---|---|---|---|
| 1 | A | passes / attack | A's pass economy removes a full token pass per starting letter (a ~35% median cut on the build host); B aggregates a tenth of the document, fails the gate, earns nothing and pays the 1-point event penalty |
| 2 | B | scan / audit | B re-runs the file A landed, under the gate: 0 hits, because a landed trunk reproduces the reference exactly; A's C-level scans land as well |

Round 1 is the anti-Goodhart rule in one row: B's attack is the fastest thing
in the run and the only attempt that pays a penalty. Round 2 is the audit's
point: a seat that re-runs the rival's landed work finds nothing, and the
transfer moves nothing — a hit would have paid 10 and cost the rival 10, but
the landed file passes the gate or it would not be the trunk.

Marginal moves stay marginal. The second candidate in each pool (aggregates
derived from the unique-word counts; `len(data)` for `total_chars`) is a much
smaller cut than the first, so on a loaded host it may be discarded instead of
kept. The record never promised otherwise, which is exactly why it is not
vendored.

## Why nothing is vendored

`median_seconds` is a T2 statistical field
(`kb/concepts/better-cheaper-faster-metrics.md`): it moves with the machine, so
a vendored `scoreboard.json` would encode one host's second and read as a claim
about every host. Worse, it would decide the artifact: the second candidate in
each pool sits within noise, so a keep flipping changes the trunk, the payoff
and sometimes the round's winner. ex1-cs and ex2-cs can vendor their records
because `val_bpb` and `accuracy` are exact; here the honest artifact is the
declaration plus the properties below.

`tests/integration/test_arena_ex3.py` replays this game into a temp directory
and asserts those properties directly, so the example still earns its numbers
in CI.

## What is deterministic (and therefore tested)

- **The attack never passes the gate, and never lands.** The guard refuses a
  reading unless the `gate_ok` line reads `True`, so the seat records the
  candidate as a crash — ex3's own word for a fast wrong answer — keeps
  nothing, and the round cannot hand it the trunk. Re-applied to the untouched
  baseline in a fresh tree, the patch exits `2` with `gate_ok: False`.
- **The final trunk passes ex3's frozen gate.** Re-run from the last round's
  landing, `train.py` prints `gate_ok: True` and an exact match on both
  workloads; the union of the two landed pools is output-identical to the
  baseline by construction.
- **Banks are arithmetic.** Each bank equals `start_bank + Σ(payoff − cost)`
  over the matrix rows: the attack's penalty and A's two payoffs reconcile to
  the bank the record shows.

No timing value and no round winner is compared anywhere: the gate, the
arithmetic and the absence of a landing are the facts a timing metric can
support.

## How to replay

```bash
cd autoresearch/contract/examples
python3 arena/play.py replay --game ex3-hotpath-speedup-cs/game.py \
  --out "$TMPDIR/ex3-cs"
```

One replay takes roughly 80–95 s on the build host: every candidate run pays
for the gate (two full workloads) and five timed reps, and the baseline is
deliberately slow. Run it twice and compare the keeps and the gate side, not
the medians. Never replay into this directory — nothing here is vendored, so
its whole output would be scratch.

## Files

| file | what it is |
|---|---|
| `game.py` | the `GAME` declaration: base, editable file, gate line, rounds, the three strategy pools, the scripted captains |
| `README.md` | this file: the story, the deterministic claims, the replay |
| `.gitignore` | seat scratch and a local record, so a stray replay is never mistaken for a vendored one |

There is no `scoreboard.json`, no `scoreboard.md` and no `round-N/`: by design,
not by omission.

## Where the candidates come from

The `passes` and `scan` pools are ex3's own kept candidates, regrouped by what
they trade: Python-level passes over the token list, and C-level scans over
the document. Every anchor is a literal block of `train_baseline.py`, so each
candidate applies to the baseline on its own rather than after an earlier
keep — a pool is a set of independent moves, not a chain.

The `attack` is rebuilt at the top of `run()`: the base example's version
anchors on the post-`re.findall` text, so it only applies after an earlier
keep. Truncating the document before anything reads it makes the same
Goodhart move stand alone, and the gate rejects it for the same reason — it
aggregated a tenth of the input.
