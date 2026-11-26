---
title: Veteran decisions — what 46 played seasons taught an autoresearch repo
date: 2026-11-26
kind: article
source_url: https://github.com/vanilla-republic/vanilla-open-design-autoresearch
source_type: downstream real-world instance, distilled
ingested: 2026-11-26
tags: [autoresearch, veteran, decisions, adopter, template]
sha256: 06ccaf5a7d8f1f1b38254c24f9380b1f8fae5176a918b8b245b2ff68ba391094
---
# Veteran decisions — the register a downstream instance earned

The veteran is `vanilla-open-design-autoresearch` (VOD), the mature
downstream of this template: the repo that stopped describing an
autoresearch loop and played one, season after season, against a real
target. This capture is a distillation, not a transcript: every rule below
was read out of the veteran's own tracked files, and each carries a
verbatim fragment from the file that states it.

## Scale, and what the tree actually records

Measured in the veteran checkout on 2026-11-26, from its root:

| Fact | Value | Command |
|---|---|---|
| PRD files | 23 | `ls docs/prd/*.md \| wc -l` |
| Python under `autoresearch/league/` | 25,046 lines | `find autoresearch/league -name '*.py' \| xargs wc -l` |
| Numbered seasons in `games.json` | 38 (1–38, games `g0`–`g13`) | read `autoresearch/league/games.json` |
| Tracked close records | 22 (`ledger/season-17..38.json`) | `ls autoresearch/league/ledger` |
| Rounds in `arena-corpus.json` | 75 over 33 seasons | read the corpus |

The brief for this capture said 46 played seasons. That figure is **not
reproducible from the tree**: the highest season number recorded anywhere
is 38, and `games.json` claims seasons 1–38 with none missing. Treat 46 as
unverified; the verified scale is 38 seasons, 22 of them with a tracked
close record, over 75 rounds.

## The decision register

Twenty rules. Each row is (a) the claim as the veteran states it, (b) the
load-bearing fragment, verbatim, and (c) the tracked file it came from. One
row carries an explicit **[UNVERIFIED]** marker rather than a manufactured
citation, and the intro above records the second figure that did not check
out.

### VD-01 — Unobserved is not stagnant

A crashed, timed-out or unserved trial yields NO reading, never a
zero-improvement reading.

> "is **unobserved**, not a measured zero"
> — `docs/prd/22-league-home.md`

> "an unreadable leg must not look like a leg that read zero"
> — `docs/29-league-season25.md`

Season 19 recorded its second seat as `no_reading` with profit 0, and its own
What Fails says that prices an unserved seat as a tie at zero, so an
unserved seat is indistinguishable from one that measured nothing to gain;
season 22's doc carries it forward as an open Resolution item. Season 25
then found the review doing the opposite in the other direction — pricing a
dead seat's leg **up** to 1.5 while pricing the leg that moved 19.5 %
**down** to 0.5 — and its Resolution applies the rule to the review's own
per-leg mean.

### VD-02 — The wall must fund what it starts

Refuse to begin an iteration whose remaining budget cannot fund it.

> "The engine refuses to start an iteration its remaining wall cannot fund."
> — `docs/26-league-season19.md`

> "Fund the trial you sell."
> — `docs/27-league-season22.md`

Season 19 shipped `_wall_exhausted` (stop when
`elapsed + agent_timeout + ITERATION_TAIL >= max_wall`). Season 22 found the
next layer: seats were granted 2–6 iterations and ran exactly one, because a
1,020 s slot could fund one 750 s call. The fix is arithmetic, not policy —
`BASELINE_ALLOWANCE + 2 × (agent_timeout + ITERATION_TAIL) <= SEAT_WALL −
ROUND_RESERVE` — shipped with the assertion in the test.

### VD-03 — A claim is readable only by a matching reader

A claim is readable only by a reader that matches the harness's real output
format (JSONL assistant text parts, not a generic line scan).

> "No line in that stream can begin with `CHANGE:`."
> — `docs/41-league-season35.md`

> "decodes harness JSONL and scans assistant text parts only"
> — `docs/42-league-season36.md`

Season 35 is the clean statement of the failure: both agents printed
`CHANGE: … | HYPOTHESIS: …` and both trials filed `hypothesis: null`,
because the adapter scanned raw stdout lines while the harness emitted JSONL
with newlines escaped inside `part.text`. Two seasons had been graded
against a reader that could not hear the message it asked for. Season 36
repaired the reader and both claims parsed.

### VD-04 — Accept the harness's typography

A U+2212 minus sign and escaped newlines are the harness's spelling, not a
seat's silence.

> "A prediction was lost to a glyph."
> — `docs/42-league-season36.md`

> "a leading U+2212 / U+2013 / U+2014 and NBSP padding are accepted as a sign"
> — `docs/42-league-season36.md`

Season 36's seat A printed `PREDICT: −1` with U+2212; `float()` refused it
and `claim_compliance` read 1 of 2. The grammar now accepts the typographic
minus family and NBSP padding, with a negative control proving the vectors
bite. The record was not retro-fitted: the archive says what was recorded at
trial time.

### VD-05 — Small-n margins use the t quantile

z is asymptotic; at two repeats the 95 % quantile is 12.706, not 1.96.

> "so a margin at n = 2 is 12.706·SE, never 1.96·SE"
> — `docs/prd/24-hypothesis-driven-loop.md`

> "at two repeats the 95% quantile is 12.706"
> — `docs/38-hypothesis-driven-loop.md`

`--margin-quantile {z,t}` computes
`max(floor, t(0.975, min(n1,n2)−1)·SE)` with a table for df 1–30 and 1.96
beyond. The worked case in `docs/38` is the argument: the same candidate
against the same incumbent is `z 1.737 keep` and `t 11.2603 inconclusive`.
The cost is stated too — at two or three repeats almost every realistic gain
becomes inconclusive, so `t` pairs with `--repeats 5` or more.

### VD-06 — A brief must be sized to its own gate's margin

A brief sized below its gate's margin is inconclusive by construction.

> "Size the brief to the gate, or the leg to the brief."
> — `docs/41-league-season35.md`

> "The brief taught the annotation, not the pin."
> — `docs/43-league-season37.md`

Season 35 asked for one annotation against a 4.3-bullet margin, so a seat
that reached 429 was graded inconclusive. Season 36 asked for five and the
leg kept for the first time in the registry's history. Season 37 sized the
brief at eight criteria against a 6.3 margin and learned the second half:
the brief taught the annotation and never mentioned the size pin, so the
work was refused by a gate it was never told about.

### VD-07 — Every metric declares its whole contract

Direction, unit, a re-runnable command, a measured noise floor, a documented
exploit and a cheat probe — or it does not enter the registry.

> "noise floor (A/A) | **0.0** over 5 reads"
> — `docs/25-league-season18.md`

> "A metric enters the registry only with its noise floor and cheat probe"
> — `docs/22-cron-recipes.md`

`docs/25` is the applied shape: `spec_gap` is registered with a definition,
a direction and unit, one command, a baseline, an A/A floor over five reads,
four named exploit paths and three probes, "each seeded with a genuinely
uncovered id so none can pass vacuously". `docs/22` is the rule behind it —
the registry schema names exactly those fields, and no metric enters without
its floor and probe.

### VD-08 — Retire a metric a census shows is unwinnable

> "zero honestly winnable services"
> — `docs/41-league-season35.md`

> "A dead leg was retired without spending a season number."
> — `docs/41-league-season35.md`

`health_contract` was rejected as a leg three times and then retired on a
census: 7 distroless gates, 1 distroless `tailcat`, 1 one-shot init
container and 1 already-healthchecked daemon add up to zero winnable
services. The retirement is a record edit — `lifecycle.status` in
`metrics.json` — and `lineage.py` refuses any active game that pays a
retired metric, so "retired" is enforced, not annotated.

### VD-09 — A pointer is not proof

An annotation counts only when the named verifier cites the same
acceptance-criterion id.

> "A pointer can no longer be bought."
> — `docs/43-league-season37.md`

> "exists and cites the bullet's own AC id"
> — `docs/43-league-season37.md`

Season 36 paid for five `_Verify:` payloads naming one existing test file
that asserted nothing about the criterion. Measured at the next base: of 463
annotated bullets, only 258 cited their own id — 44 % of what the league
called "annotated" was uncoupled. `annotation_coverage` replaced
`verify_coupling` on that measurement, with a probe (`annotation_pointer_only`)
that seeds a real file whose titles never name the criterion.

### VD-10 — Price what moved, not what was attempted

> "exactly the improvement the round paid for"
> — `docs/29-league-season25.md`

> "The close priced an unmoved leg up and the moving leg down."
> — `docs/41-league-season35.md`

Season 25 is the positive case: `spec_gap` 41 → 33 is 0.1951, the number the
round paid 19.51 metric profit on, re-measured on the merged trunk and still
33. Season 35 is the negative one: the close priced the leg that moved 5.26 %
down to 0.5 and the leg that moved nothing up to 1.5. Season 38 added the
cost side — `refused_spend` counts the tokens a guard refusal consumed
(46,313 that round, 93,082 the season before) so an attempt is priced
even when it is refused.

### VD-11 — The trunk outlives delivery

Re-establish and re-measure the base before paying for a round.

> "The readings were re-measured on that ref before the round was paid for"
> — `docs/42-league-season36.md`

> "measured again after the merge, it still reads 33"
> — `docs/29-league-season25.md`

The kickoff hands the season to `uat` as a squash and deletes the promote
PR's `arena/trunk` head with it, so season 36 opened with no trunk at all.
The trunk was re-established at the delivery head, re-measured, and only
then paid for; it reproduced the season-35 close to the unit (18 of 1,086
and 430 of 888), which is what keeps the fork arithmetic valid. The same
page records the limit: had `uat` drifted, the season would have opened on a
different baseline with nothing in the plan saying so.

### VD-12 — One writer per target

Scheduled jobs that mutate the same state consolidate onto one router.

> "The steward is this league's only hourly session driver after cutover"
> — `docs/45-cron-overlap-consolidation.md`

> "one cron per league, the arena as a steward rule"
> — `docs/45-cron-overlap-consolidation.md`

Six overlaps were confirmed in one night: two hourly schedulers firing agent
sessions into the same repo and profile blind to each other, a sentinel
resuming the session the arena supervisor owned, one uat red re-fired eight
times in 24 h, three live scripts tracked in no repo. The consolidation
made the steward the only driver, gave the sentinel the drivers' own state
files as its ownership test, and deleted `runner-keeper`.

### VD-13 — Schedules are intervals plus an in-code window

Never a cron expression the host may not be able to parse.

> "an interval schedule needs no `croniter`"
> — `docs/45-cron-overlap-consolidation.md`

> "so a cron expression would silently never fire"
> — `docs/prd/21-cron-recipes.md`

The trap is not an error, it is a silence: with `croniter` absent the job
reads `[active]` with `next_run_at: null` and never fires again. It happened
twice — once before the recipes moved to `0 18-23,0-2 * * *` on a hand
`pip install`, and again after a gateway rebuild dropped that install. The
settled form is an interval schedule plus the window in the launcher, with
the installer failing closed when a verified job has no next run.

### VD-14 — A skipped job is a failure

Local CI must fail when the actor skips jobs.

> "A job act never ran is not a pass"
> — `scripts/local-ci.sh`

> "The local CI script cannot pass on a skipped job."
> — `docs/46-measurement-coverage.md`

`act` exits 0 having run nothing when the platform has no image, so the
script pins `-P self-hosted=…`, greps the log for `Skipping unsupported
platform -- Try running with` and marks the job FAIL with that reason; a
stubbed `act` proves both halves. The same rule reached the scheduler: the
installer now exits 1 when a verified job has no next run and its badge is
anything but paused or disabled.

### VD-15 — Deterministic first, LLM last; the ceiling lives in code

> "Deterministic playbooks cost nothing."
> — `docs/39-steward-situation-router.md`

> "A prompt is not a ceiling."
> — `docs/39-steward-situation-router.md`

The steward is probes (no LLM) → rules table (no LLM) → playbooks, and only
an `agent`-mode playbook spends a session; merge and promote run catalog
argv with zero tokens. The delivery limit is `policy.check` in code
(SC-stw-4, "The ceiling is code"): this repo to sub5, the implementation
repo to sub4, never its `main` — because, as the doc puts it, "a bot told
that in prose can still merge to `main`".

### VD-16 — Facts fail closed

A missing fact must not satisfy a rule.

> "`rules._holds` returns False for a `None` fact"
> — `docs/43-steward-uat-red-accuracy.md`

> "a half-explained failure is not a fact"
> — `docs/43-steward-uat-red-accuracy.md`

A failed `gh run view` or log read yields `null` rather than a guess, and a
`null` fact fails its condition. The design note is the subtle part: the
fix was rule ordering, not a `ne` condition, because a `ne` on a `None` fact
would send an unclassified reading to `idle` and a red delivery gate would
go silent. Infra reports, code/unknown/absent repairs — fail-open toward
work, fail-closed on the fact.

### VD-17 — Digest the facts so a repeat fire is recognised

> "`facts_digest(plan)` hashes the plan's facts"
> — `docs/43-steward-uat-red-accuracy.md`

> "two trailing fires at the same digest, then a `skip`"
> — `docs/43-steward-uat-red-accuracy.md`

Every `fired` ledger line records a 16-hex digest of the plan's facts; at
`kill_after` trailing fires at the same digest the tick returns `skip`,
writes the reason, opens no session and touches no state. The criterion is a
*trailing run*, not a history count, so a fact state that changes and later
recurs fires again — which is the difference between stopping a loop and
going deaf.

### VD-18 — "Landed" gates payment; the guard does not re-run after a revert

> "`guard_trunk` now runs between the merges and the banks"
> — `docs/27-league-season22.md`

> "the guard is not re-run after a revert"
> — `docs/27-league-season22.md`

The first half is a rule: round 70 paid both seats +51.629629 for a trunk
that failed its guard on a duplicate test prefix, and one seat's keep was
reset away by the revert. PR #44 moved `guard_trunk` between `merge_teams`
and the settlement, and a reverted seat settles `landed=False` — no pot, no
golden buzz, no location bonus, `metric_profit` kept, `guard_reverted` in
the row.

**[UNVERIFIED] The second half is not supported.** The brief's wording —
"the guard re-runs after a revert" — is contradicted by the same document,
which lists the opposite as a known limit of the fix: "the guard is not
re-run after a revert so the record cannot show the post-revert trunk green".
No later season doc (34–38) records a re-run being added. The template
should adopt the rule as the veteran states it (*landed* gates payment, and
the post-revert trunk is not re-verified), not as the brief phrased it.

### VD-19 — Salvage a dead agent's tree

Salvage the tree a dead agent left, measure it, and never read it as a
refutation of the leg.

> "it is not evidence for the leg and it is never a refutation of it"
> — `docs/40-league-season34.md`

> "a win past the margin is a `keep` with `salvaged: true`"
> — `docs/26-league-season19.md`

Season 18 threw away the work that decided it: a seat drove `spec_gap` 30 → 0
in its own worktree, the agent timed out, and the engine reverted the tree
unread. Season 19 made a dead agent fall through the same pipeline, so a
timed-out iteration whose verify measured a win lands as
`salvaged: true, agent_exit_code: 124`. Season 34 added the other half: the
killed seat's dirty patch is kept as a salvage *candidate* with its own
measure (1,170 bytes, measure 8) while the house rule (SC-hyp-3) keeps that
trial unmeasured — never a zero, never a refutation.

### VD-20 — The record measures itself

Record fidelity, review coverage, an attempt ledger.

> "What the record measures about itself"
> — `docs/40-league-season34.md`

> "A retried round keeps every attempt's spend."
> — `docs/46-measurement-coverage.md`

The self-measurement set is a family, not one number: `record_fidelity`
(are the seat prompts and event logs in the archive?), `review_coverage`
(paid / realised / unpriced), `claim_compliance` (served / graded /
uncompliant), `brief_diversity` (duplicate brief slots), `seat_seconds`
(with its exclusion list printed beside the median), `salvage`,
`refused_spend` and `keep_rate_per_100k`. The attempt ledger closes the
cost hole: a replayed round rotates its token ledgers instead of
overwriting them and the close lists each attempt as settled, superseded or
unknown, so a season's spend is a total rather than a lower bound.

## Evidence table

Every row: the claim, and where in the veteran it is stated.

| Claim | Where in the veteran |
|---|---|
| VD-01 unobserved ≠ stagnant | `docs/prd/22-league-home.md` (SC-lge-12), `docs/27`, `docs/29`, `docs/40` |
| VD-02 wall funds what it starts | `docs/26` (PR #29, `_wall_exhausted`), `docs/27` (R33 economy) |
| VD-03 reader matches harness format | `docs/41` (finding), `docs/42` (`_transcript_lines`) |
| VD-04 typographic minus accepted | `docs/42` (grammar row + What Fails) |
| VD-05 t quantile for small n | `docs/prd/24` (SC-hyp-5), `docs/38` (table, worked case) |
| VD-06 brief sized to the gate margin | `docs/41` (Resolution c), `docs/43`, `docs/44` |
| VD-07 full metric contract | `docs/25` (spec_gap property table), `docs/22` (registry schema) |
| VD-08 retire the unwinnable leg | `docs/41` (census, fork `g11`), `metrics.json` lifecycle |
| VD-09 pointer ≠ proof | `docs/43` (630 of 888, probe), `docs/44` (622 lands) |
| VD-10 price the movement | `docs/29` (41 → 33 exact), `docs/41` (close), `docs/44` (`refused_spend`) |
| VD-11 re-establish and re-measure the base | `docs/42` (trunk deleted), `docs/29` (re-measure) |
| VD-12 one writer per target | `docs/45` (six overlaps, cutover) |
| VD-13 interval + in-code window | `docs/45` (both runs), `docs/prd/21` (ASSUMPTION note) |
| VD-14 skipped job is a failure | `scripts/local-ci.sh`, `docs/46`, `docs/45` (installer) |
| VD-15 deterministic first, ceiling in code | `docs/39`, `docs/prd/25` (SC-stw-4) |
| VD-16 facts fail closed | `docs/43-steward-uat-red-accuracy.md` (rules, facts) |
| VD-17 facts digest, kill_after | `docs/43-steward-uat-red-accuracy.md` (launcher) |
| VD-18 landed gates payment; re-run **unsupported** | `docs/27` (PR #44; the limit is in the same Verdict) |
| VD-19 salvage, measured, not a refutation | `docs/40` (SC-hyp-3), `docs/26` (`salvaged: true`) |
| VD-20 the record measures itself | `docs/40` (self-measure block), `docs/46` (SC-mc-5) |

All paths are repo-relative to
<https://github.com/vanilla-republic/vanilla-open-design-autoresearch>.

## Adopter-fork evidence

The second adopter, `media-gen-ops-autoresearch` (MGO), hand-forked the
veteran instead of adopting this template. Its PRD heads are the evidence
that it had to re-derive contracts the template already owns.

| Adopter PRD | One line, verbatim | Contract the template already owns |
|---|---|---|
| `docs/prd/28-mgo-referee.md` | "a **scoring layer that lives in the harness and never in the checkout it measures**" | verify/guard contract; target-profile |
| `docs/prd/29-mgo-league.md` | "gates payment on evidence and on having landed, voids a round nobody served" | fair-competition invariants; script-owned keep/revert |
| `docs/prd/30-mgo-league-runner.md` | "the evaluator hashed at both ends, a settlement through `economy.settle_seat`" | run-record contract; evaluator tamper guard |
| `docs/prd/31-mgo-arena-overnight-supervisor.md` | "starts ONE `league round` **detached**" | unattended-loop recipe; guard ladder |

**Finding.** The adopter re-derived, PRD by PRD, four contracts this
template already ships: an evaluator that lives outside the tree it measures
and is hashed at both ends, an economy that pays only for landed work and
voids an unserved round, a run record that can be replayed, and one
detached writer behind a window that a recipe installs. That is the
template's failure signal: the judgment was available here and did not
travel, so the adopter paid for it a second time — and the twenty rules
above are the part of that judgment still worth carrying.

## What this capture does not establish

- **VD-18's re-run clause** — contradicted by its own source; see the row.
- **The 46-season figure** — not reproducible; the tree records 38.
- **Whether any rule generalises outside this lineage.** Every fragment above
  is one repo's evidence. The rules are stated as the veteran applied them;
  none has been re-tested on this template's own loop.
