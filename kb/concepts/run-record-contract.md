---
title: Run-Record Contract
created: 2026-11-15
updated: 2026-11-15
type: concept
tags: [autoresearch, data-model, research-method]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md]
confidence: medium
---

# Run-Record Contract

A period of autonomous research is only evidence if its record answers a fixed set of
questions. The downstream league converged on **three artefacts per period** — one machine
record, one prose record in the docs eight-section form, one derived human view that
re-renders byte-identically — because each answers a question the others cannot.

> **Evidence.** `[S]` marks a figure **self-reported by the downstream repo** — read from a
> committed record, a PR body, or the code it cites. Key counts below were checked against
> the six on-disk `ledger/season-NN.json` files.

## Artifact 1 — the close record (19 keys)

`ledger/season-<N>.json`, one per period `[S]`:

```
archived_rounds  banks  baselines  circumstance  close_commit
floor_before  floor_after  game  head  keeps[{commit,round,team}]
matrix[]  referee  review{means,previous,reason,weights}  rounds  rounds_played
season  season_start_commit  weights_before  weights_after
```

`referee` is the 19th key and the newest: it arrives with R37/#43, which scores the referee
on its own job. A record that closed before that rule carries 18 keys — season 22's on-disk
record does — so a 19-key record first appears at season 23 `[I]` (inference from R37/#43;
no season-23 ledger exists yet).

`review` is a **record**, not prose: `review{means, previous, reason, weights}` — a close can
be diffed key for key, and a zero-round season still writes a `reason` rather than nothing
(season 20 played nothing and closed with `rounds_played: 0`, an empty matrix, and a reason
string) `[S]`.

## Artifact 2 — the reading, per leg

`{name, unit, lower_is_better, before, after, command, raw, verdict, note}` plus a `baselines`
map carrying a commit per leg. `raw` holds the referee's own `MEASURE` line — the record keeps
**evidence, not a paraphrase**, which is what makes a later re-derivation possible and what
[[relocation-not-play]] reads to classify a move.

Per round, a `provenance.json`:

```
commit  engine_version  referee_version  profile_sha256  model  model_route
environment{platform, python, seat_mode, token_budget, wall_ceiling_seconds}
cost{tokens, wall_seconds}  round  timestamp
```

`referee_version` is derived from the actual scoring command (`'verify:' +
sha256(cmd)[:12]`), never a hand-written label; replay validates the recorded **margin**, not
just the delta. See [[deterministic-keep-gate]] for the decision these fields make auditable.

## Artifact 3 — the derived view, checked

`--check` exits 0 only on byte identity; a `pending` record or a period with no narrative
entry exits 2 before rendering. **Every count in generated prose is derived from the record** `[S]`:
the hardcoded version printed "The four legs" over a table of six (seasons mislabelled for as
long as they had been written), "One rounds settled" for one round, and defaulted an unfielded
metric to `1.00` — a fabricated number rendering as fact. The trigger worth remembering: the
third hand-maintained list sitting beside its own data is where a project stops writing lists
and starts deriving them.

## The honest-verdict checklist

Ten questions a record must answer before its number is called a win:

1. Are the two commits named?
2. Is the noise floor measured (A/A re-measure of the unchanged tree)?
3. Is the denominator pinned at the base commit, with declared/credited/uncovered together?
4. Did the instrument change (size + hash beside the score)?
5. Was the unit actually served (void rows excluded, not zeroed)?
6. Did the guard run **before** the bank, and does the revert name its commit?
7. Is landing proved by **patch-id**, not ancestry? A cherry-picked keep is never an ancestor
   of the branch it was picked onto, so `merge-base --is-ancestor` denies every keep.
8. Is the artefact of the loss kept, with its hash, and explicitly not promoted?
9. Is the **operator** scored (voids, unreadable readings, rounds where nothing moved), not
   just the players?
10. Is every count in the prose re-derived and proved by a re-render that fails on drift?

## Integrity rules

- **Keep closed records exactly as they closed; correct the index instead.** A rewritten
  ledger is unfalsifiable.
- A record is **collected over a window and merged later** — state the window and re-derive
  the verdict against the tree at merge time. One entry was true when collected and false five
  minutes later, because a concurrent merge had already landed the record it denied.
- **Assert field presence before aggregating.** A zero from a field the record never wrote is
  not a measurement: an archived corpus whose rows carry no `landed` key yields "0 landed
  keeps" — absence, not measurement. Give "played and gained nothing" its own value instead of
  sharing zero with "never played".
- **Leave negative results in as first-class rows**: the leg that moved zero bytes over ten
  scheduled attempts (eight rounds), the attempt that was refused, the round that settled on
  its third try. The failures are what a later run can act on.

## In this repo

The engine's ledger today records outcomes per trial but no period record, no per-leg reading
row and no `provenance.json`; `displaced`/`held` judgements live in prose. This page is the
contract to implement, not a description of shipped code. Salvage and the wall reservation
that keep the record honest about a dead agent are on [[deterministic-keep-gate]] and
[[loop-stop-conditions]].

^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

## Related

- [[relocation-not-play]] — how a recorded move is classified before it is a win.
- [[objective-as-record]] — the game id and weights the close record adopts.
- [[deterministic-keep-gate]] — the per-decision contract behind every row.
- [[fair-competition-invariants]] — void rows, guard-before-bank, the referee score.
- [[loop-stop-conditions]] — why a period can end with zero rounds and must say so.
