# 31 — The game layer ships as an example, not as a layer

**Layers:** kb ↔ prd
**Status:** resolved
**Opened:** 2026-11-27

## Observation

The knowledge base now carries an arena's economy and its fairness rules — a
bank, a loss bonus, a buy, a cap, an audit transfer, a void round, a
landed-only pot — captured from the instance that paid for them. The PRD set,
until now, declared there is no place in this repo for that knowledge. PRD 31
acts on it as a worked example. The two statements are reconcilable, but only
if a reader is told which one moved; no document said so.

| Side | Source | Claim |
|------|--------|-------|
| KB | `kb/concepts/cs-style-arena.md` | an economy, a settlement and three fairness rules are codified and portable |
| PRD 28 | `docs/prd/28-veteran-layer.md:62` | layer 2 — the game — is **configure downstream, never fork**; ship the contract only |
| PRD 28 | `docs/prd/28-veteran-layer.md:119` | out of scope: the game layer (no `league/`, no economy, no seats in the engine) |
| PRD 20 | `docs/prd/20-agent-evals.md:68` | this repo has no arena or scoring layer to host the referee half |
| PRD 22 | `docs/prd/22-target-profile.md:87` | any scoring layer in this repo; PRD 20's *Out of Scope* still holds |
| PRD 31 | `docs/prd/31-cs-arena-reference-game.md:85` | the template now ships **one reference game as a worked example** |

The divergence is not that any of the five is false. It is that PRD 28's
out-of-scope line and PRD 20/22's *no scoring layer* read as a prohibition on
ever showing the shape, while PRD 31 shows it. Left unstated, an adopter reads
the prohibition, concludes no game exists here, and re-derives one — the exact
fork PRD 28 was written to prevent.

## Evidence

```
$ grep -n "never fork" docs/prd/28-veteran-layer.md
62:| 2 — game | the domain's own economics: scoring, pricing, seats, seasons, ranking | **configure downstream, never fork** — ship the contract only |

$ grep -n "no arena or scoring layer" docs/prd/20-agent-evals.md
68:`faster` leg. This repo has no arena or scoring layer to host them; shipping

$ grep -n "any scoring layer in this repo" docs/prd/22-target-profile.md
87:4,980-line `arena.py` (they stay downstream); any scoring layer in this repo

$ grep -n "Out of scope, explicitly" -A 3 docs/prd/28-veteran-layer.md
119:Out of scope, explicitly: the game layer (no `league/`, no economy, no seats in
120-the engine) — one worked example ships under `autoresearch/contract/examples/`
121-(PRD 31), read not inherited; the steward router (PRD 25 downstream — its rules
122-stay `declared` here); any per-domain metric.
```

The line 119 quote above is the *post-amendment* text: the pointer to PRD 31 is
the one-line change this gap's resolution already landed while staying open for
its stage-6 record.

## Impact

Informational, but load-bearing for an adopter. Nothing behaves differently at
runtime: no engine module imports the example, no CI job was added, no
dependency was taken. The damage is that PRD 20 and PRD 22, read alone, answer
"what does a game look like here?" with "there is none" — and the cost of that
answer is measured in PRD 28's own context: roughly 2,361 lines of re-derived
intent in a downstream repo that had no worked shape to copy.

## Resolution

**PRD edit** — PRD 31
(`docs/prd/31-cs-arena-reference-game.md`) lands with its AC set and one line
of amendment in each of PRD 28 and PRD 20. The gap closes when
`docs/31-cs-arena-reference-game.md` records the replay's verdict, because an
example is only "shipped" once a run has been observed.

**Closed 2026-11-27.** [docs/31](../31-cs-arena-reference-game.md) records the
verdict `works`: ex1-cs and ex2-cs replay byte-identical to their vendored
`scoreboard.json` and `scoreboard.md`, ex3-cs's attack is gate-rejected at exit
2 with `gate_ok: False` while the surviving trunk passes the frozen gate, and
`pytest tests/unit/test_arena_rules.py tests/unit/test_arena_examples.py -q`
reports 52 passed with `tests/integration/test_arena_ex3.py -q` reporting 3
passed. The one-line PRD 28 and PRD 20 amendments now point at an observed
record, so PRD 28's prohibition no longer reads as "no game exists here".
Archived to `docs/gaps/_archive/` as `resolved` (rule 5); `NN` 31 stays used.
