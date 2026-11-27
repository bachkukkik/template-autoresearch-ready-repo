# The arena — one reference game, shipped as an example

This directory is a **worked example, not a layer**. It distils a real
two-team "counter-strike" arena (an archived 1,387-line portable rule set plus
a live league's season-38 preset) into one readable kit: `rules.py` decides
every number, `play.py` does the I/O, and three counterparts replay it over
ex1, ex2 and ex3. No engine module imports it, and deleting this directory
would change no behaviour outside its own tests — which is what "example, not
layer" means mechanically.

It amends PRD 28 layer 2 **only by shipping the example**: an adopter's real
game is still configured downstream, never forked; there is still no league,
no seasons and no seats in the engine. PRD 31 is the intent, PRD 22 the target
profile a real deployment's referee should follow.

"CS-style" names the **economy**, not the video game. Nothing here captures,
reads or scores Counter-Strike gameplay — no client, no demos, no servers.

## Roles

| role | who | what it does |
|---|---|---|
| referee | `play.py` | measures the trunk before each round, runs each seat's candidate, keeps or reverts, settles |
| seat | team A / team B | a worktree copy of the trunk plus the frozen files; only the editable file may change |
| captain | a scripted reply (`game.py`) or a live agent | picks a strategy and how many attempts to buy, **before** the round is played |
| bank | `rules.Economy` | funds attempts, pays for buys, moves by `payoff - cost` |

Fairness is three rules, each with its own test: **equal slots with an
alternating opener** (`seat_order`), **an unserved round is void, not a zero**
(`settle_teams` is the single writer of that zero), and **pay only for work
that landed** (`settle(..., landed=)`).

## The rules, in one table

`PORTABLE` is the archived arena's numbers (PRD 19). `LEAGUE_S38` is the live
league's season-38 preset: same settlement, but a seat gets **one** attempt.

| rule | PORTABLE | LEAGUE_S38 | note |
|---|---|---|---|
| `start_bank` | 4 | 4 | both seats open equal |
| `base_iterations` | 4 | 2 | attempts before buying |
| `loss_bonus` | 1 | 1 | +1 attempt if you lost last round |
| `buy_max` | 2 | 2 | most attempts a captain may ask for |
| `buy_cost` | 2 | 2 | bank per bought attempt |
| `iteration_cap` | 6 | 1 | hard ceiling after bonus and buys |
| `audit_transfer` | 10 | 10 | per hit, both directions |
| `event_penalty` | 1 | 1 | per `crash`/`agent_error`/`scope_violation`/`protected_violation` |
| `loc_bonus` | 2 | 2 | paid for a smaller diff, and not when unlanded |
| `jackpot_factor` | 3 | 3 | scales a **positive** subtotal only |
| `ratchet_step` | 0.005 | 0.005 | the floor rises every round |
| `default_floor` | 0.01 | 0.01 | the bar a round must clear |

**Why `LEAGUE_S38` exists.** It is not a variant for variety: in the live
league a seat's wall funds one deep attempt, because an LLM call that outlives
its slot produces nothing (season 24 rule R40, still live at season 38). The
cap collapsed from 6 to 1, so nothing can be bought; `base_iterations=2` keeps
the loss bonus from ever exceeding the cap (`min(2+1, 1) = 1`). The archived
preset is the one this example replays; the league preset is here so the
collapse is documented in code, not in a footnote.

Two settlements are worth reading twice. `relative()` is the archived
semantics verbatim: no reading is `0.0`, a zero start is `±1.0`, otherwise the
delta over `abs(start)`. And a **jackpot needs two legs**: with an empty
`jackpot_keys` it returns `false`, so a single-metric game can never have one —
`ex1-cs` and `ex2-cs` both declare none.

## One round, in order

1. The floor starts at `default_floor` and ratchets `0.005` per settled round.
2. The referee measures **the trunk** (the tree as it stands, not a seat's
   work) → the round's baseline metric.
3. `seat_order(N)`: A opens odd rounds, B even ones.
4. Each captain's reply is parsed (`parse_captain`), sealed as canonical JSON
   plus its sha256 **before** the round plays. A bad reply falls back to the
   team's last strategy with reason `captain fallback`; an over-limit `buy` is
   clamped and marked `"clamped": true`.
5. `iterations_for(bank, buy, lost)` grants attempts and charges for the
   bought ones. R36: the clamp applies to the base first, so a loss bonus can
   never lift a seat past the cap.
6. Each seat plays its next unplayed candidates from its chosen pool, at most
   `iterations`: apply the patch (an anchor that does not match exactly once
   is an `anchor_miss`, consumes the attempt, changes nothing), run, keep only
   a strictly better reading, otherwise revert. A run that fails the guard or
   prints no metric is a `crash`.
7. The round settles (`rules.settle`): metric profit is `100 ×` the relative
   improvement, an audit pays and charges the transfer, each penalty event
   costs a point, and a location bonus is paid for a smaller diff.
8. The higher profit wins; an exact tie goes to the **opener** (a local rule —
   the live league named no winner on a tie). If the winner kept anything, its
   file is re-measured; only then does it become the trunk (`landed`).
9. If a seat was never served, the round is **void**: both payoffs zeroed,
   cost 0, banks unchanged, no loser, the reason recorded on the row.
10. The equilibrium verdict is taken over the matrix actually played: reached
    only when neither team has an unexplored strategy and no regret exceeds
    `100 × floor`.

## Replay it

```bash
cd autoresearch/contract/examples
python3 arena/play.py replay --game ex1-music-abc-cs/game.py \
  --out "$TMPDIR/ex1-cs"
cat "$TMPDIR/ex1-cs/scoreboard.md"
```

`--out` is scratch: `round-N/seat-*/`, `round-N/trunk-measure/` and
`round-N/landing/` are working trees. The record is `scoreboard.json`,
`scoreboard.md` and `round-N/captain-*.{json,sha256}`. Output carries no
timestamp, no absolute path and no wall second, so two runs diff clean —
`tests/unit/test_arena_examples.py` asserts exactly that against the vendored
files.

## Live mode — the recipe, **untested in CI**

CI runs the scripted replay: a model call per round is too slow and too
variable, and a captain that is different every run cannot be a fixture. The
live path exists and is documented here, **untested in CI**, in two steps.

Run the engine once per seat, each in its own worktree, so the two seats never
share a working tree:

```bash
# two seats, one per worktree, off the same base
git worktree add ../seat-A -b seat-a
git worktree add ../seat-B -b seat-b

bash autoresearch/engine/bin/autoresearch init --repo ../seat-A \
  --verify "python3 train.py" --metric-name val_bpb --direction lower \
  --scope train.py --protect prepare.py
bash autoresearch/engine/bin/autoresearch run --repo ../seat-A \
  --agent hermes --max-iterations 4

# seat B: same init, --max-iterations from iterations_for(bank, buy, lost)
```

`--verify` is the same command the referee runs on the trunk, so the trunk
measurement and a seat's measurement are the same measurement — that is the
frozen-evaluator claim. `--max-iterations` is `iterations_for`'s first return
value for that seat's bank and buy, not a guess.

Then settle the two results by hand, one round at a time:

```bash
python3 arena/play.py settle --state state.json --a a.json --b b.json \
  --round 3
```

`a.json` / `b.json` are the seat results in the shape the replay writes
(`kind`, `direction`, `baseline`, `best`, `cost`, `strategy`, optional
`landed`). `settle` writes the settled `state.json` back with the banks moved,
the row appended and the floor ratcheted; a missing file or key exits `2` with
a message. The engine supplies the candidates, so this path has no scripted
pool — and no CI test, which is why it is labelled untested rather than
verified.

## What this can do

- two scripted teams on one frozen evaluator;
- an economy: bank, loss bonus, buy, iteration cap, two presets;
- sealed captains with a fallback and a two-sided clamp;
- an audit transfer — a seat that re-runs the rival's landed work is paid for
  hits, and pays for the rival's;
- a jackpot when a game declares two or more legs;
- equal slots with an alternating opener;
- a void round when a seat is not served;
- payment only for work that landed;
- an honest equilibrium verdict over the matrix actually explored;
- a live-mode recipe through the template engine (documented; untested in CI).

## What this cannot do

- **No `ex4-llm-repo-speedup-cs`.** ex4 is one live LLM transcript, i.e. one
  seat's record, not two; a two-team replay would have to be invented, and an
  invented transcript is worse than an absent example.
- **No `ex5-real-oss-speedup-cs`.** ex5 needs a real repository and a heavy
  build, and its metric is wall time — a replay would be a different artefact
  every run. It is a follow-up issue, not a promise.
- No jackpot on a single-metric game: `jackpot()` returns false with no keys,
  by design.
- No deterministic winner on a timing metric:
  [ex3-hotpath-speedup-cs](../ex3-hotpath-speedup-cs/) checks the gate and the
  audit, never the winner.
- No equilibrium claim while a strategy is unexplored: the verdict stays
  `false` and names the cell.
- No LLM-as-judge referee: a judge is a second nondeterministic measurement,
  and a settlement must be arithmetic.
- No referee inside the measured tree of a real repository: a seat grading
  itself is the failure mode PRD 22's target profile and evaluator hash exist
  to prevent.
- No capture or analysis of actual Counter-Strike gameplay (video, demos,
  servers): "CS-style" names the economy.
- No seasons, 13-leg league, bounty, films or supervisor: they stay
  downstream (PRD 28 layer 2).

## Requests that make no sense

Each is refused here so the refusal travels with the code.

- *"Make it play actual Counter-Strike."* — the example is an economy over a
  measured number; there is no client, map or demo reader. Instead: read
  "CS-style" as the economy and point a real game at a real metric.
- *"Replay ex4 as a two-team game."* — one live transcript exists, not two
  seats; a replay would be fabricated. Instead: read ex4's transcript for what
  one agent did, and use ex1/ex2 for the two-seat shape.
- *"Add a jackpot to a one-metric game."* — the pot needs two legs to be a
  pot, and with one key the rule returns false. Instead: declare
  `jackpot_keys` only when the game measures two or more legs.
- *"Pick a timing winner deterministically."* — a median seconds value cannot
  decide a round in CI. Instead: gate the timing (ex3-cs) and stop at
  passed/failed; the winner is not a determinable fact.
- *"Declare equilibrium early."* — the verdict is false while any strategy is
  unexplored, and `ex2-cs`'s vendored record shows it staying false. Instead:
  play the unexplored cell, or read `unknown` and report "not yet".
- *"Move the referee into the measured tree."* — a referee inside the measured
  tree is a seat grading itself. Instead: use PRD 22's target profile with the
  evaluator hash taken at both ends of a round.
- *"Have an LLM judge the round."* — a judge is a second nondeterministic
  measurement. Instead: parse one line per leg into `rules.settle`, which is
  arithmetic and reproducible.
- *"Run the live recipe in CI."* — it needs a model, a wall clock and a
  network. Instead: run the scripted replay in CI, and keep the live recipe as
  an operator step.
- *"Replay straight into the example directory."* — it would overwrite the
  vendored record with your own scratch. Instead: `--out "$TMPDIR/..."` and
  `diff` against the vendored files.

## Writing your own `game.py`

A game is one dict. Declare it beside your example; `play.py` needs nothing
else.

```python
GAME = {
    "name": "my-task-cs",
    "base": "../my-task",            # dir relative to game.py
    "start": "train_baseline.py",    # copied to the editable as the trunk
    "files": ["prepare.py"],         # frozen, copied into every seat
    "editable": "train.py",          # the only file a candidate may change
    "run": ["python3", "train.py"],  # argv, no shell
    "timeout": 60,                   # seconds per run
    "metric": "val_bpb",             # a line that reads "<metric>: <number>"
    "direction": "lower",
    "gate": None,                    # or a line name that must read "True"
    "economy": "PORTABLE",           # or "LEAGUE_S38"
    "rounds": 4,
    "jackpot_keys": [],              # two or more legs, or no pot
    "audit": False,                  # add "audit" to the strategy list
    "strategies": {"name": [("desc", [("regex", find, replace)])]},
    "captains": {1: {"A": "<reply>", "B": "<reply>"}},
}
```

Four things to get right, all of them cheap:

1. **Anchors must match exactly once** in whatever the trunk currently says —
   prefer a regex over a literal so a candidate applies after an earlier keep.
   An anchor that misses is recorded as `anchor_miss` and costs an attempt.
2. **The metric must be one parseable line** the guard can trust. If a wrong
   answer can be fast or accurate-looking, add a `gate` line that must read
   `True` — that is what ex3 does.
3. **Keep candidate lists small and honest.** They are scripted, so they prove
   the mechanism, not that a team plays well. Pools larger than
   `base_iterations` are what make a four-round story possible; pools smaller
   than it are swept in one round and the later rounds will honestly tie.
4. **Script the fault, label it.** A seat that is never served belongs in
   `unserved`, not in a fake crash; the record then says `injected`.

Then replay it, diff two runs, and vendor `scoreboard.json`,
`scoreboard.md` and `round-N/captain-*` — never the seat directories.
