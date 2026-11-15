---
source_url: https://github.com/vanilla-republic/vanilla-open-design-autoresearch
ingested: 2026-11-15
sha256: 6c3fa12a5588e4110154de48a9d883dbdbe0d0c461058dd6be0084fe2539667c
source_type: distillation
kind: article
title: "Downstream frontier distillation — the 42-PR league record: R28–R39, fair-competition invariants, fail-closed eval doctrine, run-record shape"
---

# Downstream frontier distillation — what 42 PRs of live autonomous research taught

## Provenance

**What.** A distillation of the implementation repo
[vanilla-republic/vanilla-open-design-autoresearch](https://github.com/vanilla-republic/vanilla-open-design-autoresearch)
— the downstream fork that has run a continuous, competitively scored autoresearch
league (seasons 1–23, rounds to 71) against a real target repository. Scope is the
*knowledge* half of that fork: the mechanisms it was forced to build, the defects live
seasons exposed, and the rules it wrote in response. Not the league itself — `arena.py`
(4,980 lines), `referee.py` (2,580) and the captain/jackpot economy stay downstream; only
target-agnostic rules are ingested here.

**Which PRs.** Every pull request in `#1`–`#46` was read. `#5`, `#6`, `#7` and `#23` do
not exist in that repo (`#23` is an issue, not a PR), leaving **42 PRs reviewed**. D#1–D#3
and D#35 in the hygiene rows are that repo's own numbers; T#45–T#52 name template-side
PRs, cited only to mark divergence.

**When and how.** 2026-11-15, read-only. Ten theme reports were produced first, each
reading the complete PR body, the file list, and the diff at the merge commit
(`git show`), then validated for field completeness; constants and season numbers quoted
below were spot-checked against committed files (`metrics.json`, `games.json`,
`ledger/season-NN.json`, `arena.py`, `loop.py`) rather than taken from prose. The
distillation is therefore a **synthesis of a repository**, not a capture of one document —
hence `source_type: distillation` and one canonical `source_url`.

**Labels.** `[M]` measured by a command that ran; `[S]` stated in a PR body or a committed
season record (self-reported by that repo, quoted with its number); `[I]` inference.

**Why this repo cares.** This template's engine was the fork's ancestor two waves earlier.
The fork's live defects are the template's *future* defects, and the fork's rules are
already written as arithmetic with AC ids. Ten structural gaps found by the survey are
recorded in the same research round as the port plan; this capture is the durable part.

## Evidence table — one row per PR group

| # | PRs | Theme | Defect evidence (season/round + measurement) | Fix | Verdict |
|---|-----|-------|---------------------------------------------|-----|---------|
| 1 | #1–#4 | Realignment + repo housekeeping (downstream of template `b26f40a`) | Cut from template `eee1216` and drifted to five top-level roots (`contract/ engine/ data/ ops/ arena-runs-vod/`) while upstream regrouped under `autoresearch/`; the realign produced 7 conflicts plus a hand-arbitrated PRD renumber (arena 18→19, docs 18→20) whose only product is parity [S] | Apply the upstream range, resolve as upstream + local rows, archive instead of delete | specific |
| 2 | #11, #12, #15, #20 | The league moves home; the measured repo becomes a parameter | Wave 1's profile still pointed `referee`, `guard_command`, `runs_dir` at the *target's* `autoresearch/arena/`, so a round executed the target's evaluator and wrote the target's state; moving the evaluator out of the worktree also moved it out of `--protect`, so a seat could open `league/arena.py` by absolute path and no diff would see it [S] | `--target-repo`/`--target-profile` with pure `resolve_target()` (flag > env > cwd); every profile key declares *relativity* (league-owned vs target-relative); `evaluator_digest()`/`evaluator_tamper()` hashed at both ends of a round, `TAMPER_EVENT`, exit 4; `tools/import-runs.py` migrates state as a command | generic (parameter block ≈290 lines; tamper guard) |
| 3 | #25 | The objective becomes a tracked record | By season 17 every leg of the only game was at its measured floor or structurally unwinnable (`better` and `fresh` closed at 0; `cheaper` proved unmovable twice) and the league had no way to say "exhausted, here is its successor" without editing the constant that also describes seasons 1–17; hand-edited records loaded and played with duplicate metric names, missing directions, unregistered legs, two active games [S] | `metrics.json` (registry) + `games.json` (lineage) + `lineage.py` reader/validator; nine-field metric contract; fork is a record edit with `parent` + reason against the parent's floor; retire by status; exactly one `active` | generic (invariants ~120 lines) + pattern |
| 4 | #8, #13, #14 | Eval layer: dispersion, margin-gated keeps, inconclusive, provenance, A/A floor, drift canary, cheat probes | `measure.py` reduced repeats to a bare median and `decide.py` gated a keep on a relative 0.01 floor with `DEFAULT_REPEATS = 1`. For a proportion at n=100 the standard error is 0.05 (p=0.5) to 0.038 (p=0.82), i.e. **the floor sat 3.8–5× below one SE** — a recorded keep could be pure noise; PR #13 shipped the layer while seats still ran `--repeats 1`, so the gate was dormant while docs claimed it live; #14 switched 1→3 repeats and paid 10,800 s of a 21,600 s season for 4 of 8 planned rounds [S] | `Measurement` gains `repeats`/`spread`/`honest` derived in `__post_init__`; `MEDIAN_CONSISTENCY = 1.2533`; `standard_error_of_difference()` returns `None` below 2 repeats; `INCONCLUSIVE` + `Z = 1.96`, `margin() = max(floor, Z·SE)`; provenance block before the agent runs (`model`, `model_route`, `engine_version`, `referee_version = 'verify:'+sha256(cmd)[:12]`, `profile_sha256`, ISO-8601 UTC); A/A noise floor recorded with its values; drift canary append-only | generic (+709/−94 lines, stdlib only) |
| 5 | #29, #30 (+#31 docs) | Salvage, the round wall, the honest pot, `context_weight` | Season 18 round 60: seat A drove `spec_gap` **30 → 0** inside its worktree (one 100-line bats file, 15 tests, 30 ids), the opencode call hit the 570 s adapter timeout (exit 124), and the engine reverted the tree **unread** because `if not result.ok: _revert(...)` — round recorded `keeps: 0`; the wall was checked only at the top of an iteration, so `--max-wall 1680` with `--agent-timeout 750` started a 750 s call at t=900 s and the outer `timeout … 1800` SIGKILLed the engine mid-call; the wall was priced per seat, so two seats ran 3,600 s against an 1,800 s cap and season 18 measured **2,915 s** (62 % over); the pot paid +41.6667 for a keep every cherry-pick dropped and turned a −2 penalty into −6 [S] | `dead = not result.ok` falls through the *same* commit/guard/measure/margin pipeline, a win banks as `keep` with `salvaged: True` + `agent_exit_code`; `ITERATION_TAIL = 120` and `_wall_exhausted` (elapsed + agent_timeout + tail ≥ max_wall); `ROUND_RESERVE 120`, `ROUND_WALL = 2·SEAT_WALL + ROUND_RESERVE = 2400`, `seat_argv()` restates the wall in *both* the `timeout` wrapper and `--max-wall`; the pot pays only on a literal `landed=True`, `JACKPOT_FACTOR` scales the positive part only | generic (loop.py ≈110 lines; killpg helper) + pattern |
| 6 | #27, #28, #31, #32, #33, #45 | Season records: relocation vs play, honest verdicts, generator drift | `spec_gap` read **140** uncovered ids at `origin/uat` (b95ff0b), **133** at the round's base (ca6b551) and **30** in the trunk worktree the seats played in, because one commit deleted 18 arena test files while their PRDs stayed; `faster` "improved" **82.624 → 61.973 s** with no work behind it (`tests/docker-free.txt`: 55 bats entries at base, 36 at upstream), and season 19 repeated it 61.973 → 38.861 and called it "a reading only, and not play" although it moved (#27, #28, #31); one page generator printed "The four legs" over a table of six (seasons 17–18 mislabelled five as four since written) and defaulted an unfielded metric to `1.00` (a fabricated `faster 1.00`) [S] | Every reading carries its commit; verdicts classified by cause (play / improved / held / displaced / reading / regressed); denominator pinned at the base commit with declared/credited/uncovered recorded together; counts derived from the ledger, `--check` exits 0 only on byte identity, absent renders `-`; unbanked artefact kept at `evidence/round-60/` with its sha256 as a loss | pattern + generic (`arena_page_common.py` 113 lines, `--check` contract) |
| 7 | #9, #10, #18, #19, #40 | The overnight supervisor as a tracked, installable recipe | Launcher, prompt template and charter lived only in `~/.hermes/profiles/<profile>/scripts/` with profile, target, WebUI URL and UTC offset hardcoded — no diff, no review, no test; install without an explicit root resolved `~/.hermes` through `$HOME`, which inside a harness child is the per-profile home, so `cron create` ran beside live job `8e16abb73143` and minted duplicate `38c15a44dbda`; the live-round guard **failed open** in a real round (2026-11-15 12:07 UTC, round 64) because global flags sit between script and subcommand (`arena.py --target-profile … round --n 64`); `cron edit` cannot resume a job created `--paused` [S] | Recipe dir = files + `recipe.json` + `config.example.json` + 8-line `install.sh`, installed by one generic installer (`copy2`, config merge, `config_renames`, `--dry-run` writes nothing); root resolution flag → `HERMES_ROOT` → `HERMES_HOME` → `pwd.getpwuid().pw_dir/.hermes`, refuse a dir with no `config.yaml` (exit 2); create-vs-edit from `cron list --all`, two matches → exit 2; `ROUND_MARKER` regex behind a broad `pgrep` prefilter, dry-run counts as in-flight; interval tick + in-script window; `busy_session` over all sessions | generic (`install.py` 405 lines) + pattern |
| 8 | #16, #17, #21, #22, #24 | One registry, every surface; media as checked commands (recorded, not ported) | Nothing enumerated the entry points, so every prompt and cron recipe restated an argv that could drift; two tools (`arena-prune.py`, `arena-corpus-absorb.py`) were entry points with no command; safety marked from flag names flips two verdicts (`league.round` mutates even with `--dry-run`; `media.dashboard-check` executes the target's code); `subprocess.run(timeout=…)` killed only the direct child, so a 1,200 s render left ~256 MB Chrome workers running [S] | `_command(...)` declares mutates/executes_target_code/local_only once and `catalog()`/CLI/`--help`/REST/MCP derive from it; exposure computed from declared cost; a target is a declared name, never a path; no `shell=True`, every child bounded and `start_new_session=True` + `killpg` + reap; check-the-manifest-then-start-children | pattern (registry core ≈350 of 1,090 lines) |
| 9 | #34, #36, #37, #38, #39 | R28–R31: fairness is arithmetic | Season 19 round 61: one 1,800 s deadline served staggered seats — A granted **1,679 s**, used ~1,445 s, B left **235 s**, below `MIN_SEAT_WALL` (240), never launched, rc **199**, banks A **4.0 → 86.857142**, B **4.0 → 4.0** with both seats on the same model route, season 18's fresh-token spend measured equal (234,378 vs 216,360 of a 300,000 budget) and banks reset each season; the referee's own circumstance counter tested only `PENALTY_EVENTS`, so an unserved seat — rc 199, no event logged — was invisible and the season-19 weight review was computed from seat A's rows alone (#11, #34; R37/#43 later made the referee score count void rows as penalties); `seat_wall()` returned `int()` and floored the opener to 1,139 s while the follower got 1,140 s; a real seat's grandchild survived (`CRASH after 31.0s`, pid still alive) and competed during the other seat's slot; season 20 stamped `season_started_at` at open, nobody played, and every round then refused with `season wall exceeded: 37479s > 21600s`; season 21 round 62 scheduled `better` at a season-start reading of 0 (the floor) and paid +2 loc for an unlanded diff; season 22 ran a 3-round EXPLORE over 2 playable legs, giving B the only jackpot leg twice (+46.24 vs 0.0) [S] | `SEAT_WALL 1140`, slot *i* closes at `started + (i+1)·SEAT_WALL`, grant `min(SEAT_WALL, seat_wall(deadline, now))`; derived `ROUND_WALL 2400`/`MAX_WALL 2280`/`ROUND_START_BUDGET 3000`/`ROUND_CAP 7` so 7·3000 ≤ 21,600; `MIN_SEAT_WALL 240` + `SEAT_NOT_SERVED 199` (a value no wrapper, shell or signal returns); `seat_order(n)` alternates A/B and results travel as `(team, result)` pairs; `settle_teams(void=…)` is the only writer of the zero and every reader skips void rows through one `_observed` predicate; `season_started_at = None` until the first round; legs at floor filtered, unmeasured ≠ zero; rotation length = playable legs | generic (pure functions ≈150–250 lines) + pattern |
| 10 | #41, #42, #43, #44, #46 | R32–R39: agent intent survives validation; grants and charges honest; the guard before the banks; disjoint parallel work | R32 (round 65): the captain answered `{"strategy":"spec_gap","buy":3,…}` with a sound reason and `parse_captain` rejected the **whole** reply because buy > `BUY_MAX` (2), replaying the previous leg which crashed −1.00; the prompt stated the cap 6 and never 2. R33 (rounds 63–69): banks equalled `4 + Σpayoffs` while eight rows across rounds 65–69 carried `cost: 4`, and every seat ran exactly **one** trial per round although the grants ranged **2–6** iterations (fourteen seat-rounds; `results.{A,B}.iterations` 2/2, 4/2, 4/3, 2/5, 5/4, 4/5, 4/6) because `AGENT_TIMEOUTS 570/420` under a 1,020 s slot cannot fund two. R34 (round 66): the captain with no round history ran `ls` and dumped `state.json`, died at the 120 s ceiling. R35: `cheaper` 0 for 10 scheduled attempts (nine seat-rounds of season 22's fourteen plus round 62) with 1,313,437 bytes before and after; seasons 20–22 unlisted under g1. R36: `iterations_for` granted **4** under `ITERATION_CAP = 3`. R37: no season was ever scored on whether it served the competition. R38 (round 70): both seats `81 → 73`, both paid **+51.63**, trunk guard then failed on a duplicate `139`, `reset HEAD~1` removed B's cherry-pick **after** payment — replay reads 177/177 before the fix and 177/50 after. R39 (rounds 70–71): identical briefs (same 8 ids, AC1257–AC1264) collided on the next e2e number; on a profit tie a stable sort merged A first and the guard reverted the *last* merged, so B was reverted both rounds (r71 A +54.88 / B +9.96) [S] | Two-sided clamp of numeric fields with the agent's qualitative intent kept; every prompt limit formatted from the constant it enforces and all grants bounded by one cap; `settle_teams` banks `profit − cost` and writes `cost` on every row; `AGENT_TIMEOUTS → 330` with `AGENT_TIMEOUT_CEILING 360` and `BASELINE_ALLOWANCE 100` (100 + 2·(330+30) = 820 ≤ 1,020 s), `ITERATION_CAP 6 → 3`; last-three-rounds section + `CAPTAIN_NO_TOOLS`, `CAPTAIN_TIMEOUT 240`; `referee_score(rows, cap)` with one named reason per point and teeth on a negative score; `cmd_round` runs `guard_trunk` **before** both settle passes and `guard_reverted_team(merges)` names the commit; interleaved `spec_gap_share` (`rows[0::2]` / `rows[1::2]`, `--top 16`) and ties broken by the round's rotating opener | pattern (mostly prompt/ordering rules) + generic (clamp helper, score function) |
| 11 | D#35, T#45–T#52 | Runtime-state home, persistence, link gate, harness surface divergence | `jobs.py`/`workspace.py` resolved a *relative* `RESEARCH_JOBS_DB` against the process cwd, so the container (WORKDIR /app) wrote `service/data/` and a host run wrote root `data/` — one store, two homes; compose mounted no volume at the service data path, so `jobs.db` lived in the image layer while `service/README.md` claimed "survives restarts"; once a volume existed, `queued` rows had no dispatcher and `running` rows stayed `running` forever; the first link-gate run found **19** broken links downstream and **17** in this template's `main`, with no test catching either; three different things are named `autoresearch` (folder, command CLI, engine package) [S] | `_service_path()` joins a relative value onto `SERVICE_ROOT`; named volume `service-data` → `/app/data`; lifespan recovery re-dispatches `queued` and marks `running` `failed` with `interrupted: …` (never re-runs); 209-line stdlib link gate in the unit tier; a "three things named `autoresearch`" table with one runnable command per row | generic (resolver, recovery, link gate) |

## R28–R39 — the rule list

The fork writes every repair as a **numbered, dated, evidence-bearing rule** (R27 … R39,
a letter suffix for a follow-up found inside the same mechanism). Each rule carries, in
the constant's docstring and in the season doc: the season/round that produced it, the
measured numbers, the constants, the invariant as arithmetic rather than intention, the AC
ids, and an explicit *deliberately out of scope* list. A rule without its defect and its
test id becomes folklore; a rule with an out-of-scope list stops being re-litigated [S].

| Rule | PR | One-line principle |
|------|----|--------------------|
| R28 | #34 | Every competitor gets its own equal wall slot, allocated before the run starts: `now + grant + reserve ≤ slot close` — never a shared deadline divided by arrival order. A round that cannot serve every competitor is **void**, not scored. |
| R28a | #36 | The opener's grant is its whole slot (nothing ran before it), and a killed competitor takes its **process group** with it — `start_new_session=True` + `killpg` + reap. |
| R29 | #37 | The clock starts at **first work**, not at admission; and a rotation explores only the legs the current objective actually pays. |
| R30 | #38 | Never schedule a leg the current state cannot pay: a season-start reading of 0 is the metric's floor, so no keep can win it; an unmeasured snapshot is unknown, never zero. A bonus rides the landing gate. |
| R31 | #39 | A rotation is exactly as long as the set it rotates (`n` options → `n` rounds) — otherwise one competitor gets a second shot at the only prize by construction. |
| R32 | #41 | Clamp the agent's arithmetic, reject only its integrity: an over-limit integer is clamped to the documented bound with the agent's qualitative intent kept, and the bound is stated in the prompt from the constant that enforces it. |
| R33 | #42 | Anything you grant must be charged, and anything you charge must be granted: bank the net, write the cost cell on every row, charge nothing for a round never served — and grant only what the wall can fund. |
| R34 | #42 | Tell the agent its own history and forbid it to go looking: last-N outcomes plus "do not read files or run commands, answer now" turns exploration into an answer. |
| R35 | #42 | Price only the moves that can pay: offer only priced legs, mark the rest reading-only, and keep the parser permissive so narrowing the *offer* never narrows what is *accepted*. |
| R36 | #43 | Every grant — base, loss bonus, comeback bonus, bought iteration — is bounded by the **one** cap; `base = min(base, CAP)` before any buy is considered. |
| R37 | #43 | The referee is scored on its own job, separately from the players, one named reason per point, and a negative score has teeth. |
| R38 | #44 | Gate the reward on the state that is actually banked, and order the checks accordingly: any check over the *combined* result runs **before** the settlement that pays for it; a revert names the commit it removes. |
| R39 | #46 | Parallel agents get disjoint work and ties are not verdicts: split the ranked list interleaved, say so in the brief, and break an equal-score tie by the rotating opener — never by sort order. |

## Fair-competition invariants (target-agnostic)

Stated as arithmetic, checkable per launch, none of them league-specific:

1. **Equal seat slots, allocated up front.** `SEAT_WALL` per competitor, slot *i* closes
   at `started + (i+1)·SEAT_WALL`, grant `min(SEAT_WALL, remaining)`. Measured failure:
   1,679 s vs 235 s of one 1,800 s deadline (#34).
2. **Alternate the opener.** Pure `seat_order(round_number)`; results travel as
   `(team, result)` pairs so a reordered launch cannot re-map outcomes; the order is
   recorded per round for audit (#34, #46).
3. **Void a round nobody could be served in.** Single writer of the zero, every scoreboard
   component zeroed, payoff `[0,0]`, no loser named, unserved seats named, real work still
   merged — and **every** reader (estimates, matrices, audit rates, dashboards, season
   review) skips void rows through one shared predicate, or a zero masquerades as an
   observation (#34).
4. **A floor below which a competitor cannot start is its own rule.** Below it, record
   "not served" with an out-of-band exit code (`199`) rather than launch it to die on a
   wall that does not exist (#34).
5. **The clock starts at first work.** An idle or pre-opened container must not consume
   the season budget: `37479s > 21600s` on round 1 because the clock was stamped at open
   (#37).
6. **Never schedule a floor-leg.** At the metric's mathematical floor no keep can win; an
   unmeasured snapshot is unknown; an all-at-floor set falls back to the unfiltered list
   rather than an empty schedule (#38).
7. **Rotation length = option count.** `n` legs → `n` rounds, off-diagonal for every
   `n ≥ 2` (#39).
8. **A bound may never kill the run it bounds.** Before starting a unit of work, check the
   remaining budget pays for it in full (agent timeout + tail); if not, stop on the wall
   with a measured unit behind you (#29, `ITERATION_TAIL = 120`).
9. **The exit code decides nothing; the tree decides.** A timeout leaves a tree; commit
   it, guard it, measure it, judge it (#29).
10. **State the same wall in every layer that enforces it.** Wrapper `timeout` and inner
    `--max-wall` are one number found structurally, and an argv with neither is a hard
    error — "an unbounded engine under a bounded seat is the bug, not a fallback" (#30).
11. **Guard before bank.** Any check over the combined result runs between the merge and
    the settlement; the reverted competitor settles `landed=False` so pot, bonus and
    location credit drop together; a revert names its commit (#44).
12. **Clamp, don't discard, the agent's numbers.** Only a constitutional violation
    (scope, protected file, unparsable reply) forfeits a decision (#41).
13. **Tell the agent the limits it will be held to**, generated from the constants
    (`BUY_MAX`, `BUY_COST`, `ITERATION_CAP`, per-trial timeout), and tell it its history
    with tools forbidden (#41, #43).
14. **The referee is scored separately** — voids, unreadable readings, rounds where
    nothing moved, seasons played — one reason per point (#43).
15. **Every grant bounded by one cap**, and a bought attempt must fit the wall that
    executes it (`100 + 2·(330+30) = 820 ≤ 1,020 s`) (#42, #43).
16. **Disjoint agent ids and disjoint briefs** for parallel agents, and **a tie must not
    decide penalties**: ties go to the rotating opener, or the outcome is decided by code
    order rather than merit (#46).

## Relocation, not play

The single largest number in the fork's record was a booking error, twice.

- `spec_gap` 140 → 133 → 30 across three commits, because one commit deleted 18 arena
  test files while their PRDs stayed: the denominator moved with no line of test code
  changing (#27, #31). The season records pin the denominator as declared / credited /
  uncovered together: season 19's baseline row reads `1027 declared / 140 uncovered / 887
  credited` (`ledger/season-19.json`, commit b95ff0b), season 21's `1027 / 113 / 914`
  (`ledger/season-21.json`, commit cac0638) after a round — same declared total, a
  different credited/uncovered split (#27, #31).
- `faster` **82.624 → 61.973 s** with no work behind it — `tests/docker-free.txt` held 55
  bats entries at the base and 36 at `origin/uat`. Season 18's record classifies the move
  `displaced` (`season18-legs.json:69`, 82.624 → 61.973) and its doc calls it "none of it is
  play"; season 19's record still reads `held` (`season19-legs.json:93`, 61.973 → 38.861)
  while its doc calls the same class "a reading only, and not play" — the record mislabels a
  relocation `held` (#27, #28, #31).
- `cheaper` moved **0 bytes** across ten scheduled attempts (nine of season 22's fourteen
  seat-rounds plus season 21's round 62; eight rounds carry a reading) — 1,313,437 B
  before and after, while captains quoted the intel line back as their reason (#42, #45).
  Both counts are the same record: ten seat-level attempts, eight round-level readings.

Rules distilled:

1. A run record is a comparison of **two readings taken at two named commits**, or it is
   an anecdote. `season_start_commit`, `close_commit` and a per-leg `{commit, value}`
   map; absent stays absent.
2. Every move is **classified by cause before it is called a win**: play, improved, held,
   displaced, reading, regressed. A speedup whose cost merely moved elsewhere is
   `displaced`; a recalibrated instrument is `held`.
3. **Never compare a metric across a change to the instrument that measures it** — the
   instrument's size and hash belong in the record beside the score, because a shorter
   tier is a faster tier and nothing in the score says why.
4. **Pin the denominator at the base commit**, so deleting the objective is worth exactly
   zero; record declared / credited / uncovered together, because one number hides which
   half moved.
5. **Keep the artefact of a loss** (`evidence/round-60/` + sha256): it proves the leg was
   solvable without pretending the round won. An over-budget round is a loss, never an
   extension, and promoting it by hand converts a loss into a win.

## Fail-closed evaluation doctrine

The engine's job is to make "better" falsifiable, and every failure mode has a named,
non-zero answer:

1. **A keep clears `max(configured floor, z·SE)`**, with the SE taken from the dispersion of
   the actual repeats and carrying the estimator's consistency factor (median → 1.2533).
   A bare relative floor banks jitter as progress: 0.01 against an SE of 0.038–0.05 (#8, #13).
2. **Three verdicts, not two**: keep / discard / **inconclusive**. A delta inside the
   margin is neither proof nor penalty — revert it, cost nothing, tell the agent "retry
   only with a larger change" (#13).
3. **One repeat is not a measurement**: say so (`honest: false`, `spread: null`) instead of
   inventing a spread; set the repeat count where the decision is made (`SEAT_REPEATS = 3`
   default, `FASTER_REPEATS_MIN = 3`), because a statistical gate defaulting to n=1 is
   dormant while the docs claim it is live (#13, #14).
4. **A leg is measured honestly or it is dark.** An unconfigured leg reports nothing
   rather than a fabricated zero; **could_not_run → `null` + exit 1**; **all probes missed
   → exit 0 with rate 0.0** (absence is the finding); the gate reads the *rate*, never the
   exit code (#13, #29). The timed leg itself shipped at #8 as
   `statistics.median([first, second])` over exactly two bats runs — no dispersion, and
   nothing at all when unconfigured; #13 replaced it with `FASTER_REPEATS ≥ 3` plus a
   recorded `spread` and repeat count, and a median of two is now *dark* by rule
   (SC-evl-6).
5. **Measure the noise floor** — an A/A re-measure of the unchanged tree — and record it
   with its values; a deterministic metric honestly reports 0.0 (`context_weight`, A/A
   spread 0.0 over 5 reads) (#13, #29).
6. **Canary the evaluator**: re-measure unchanged trunk against a recorded baseline,
   treat a delta beyond `max(1.96·baseline spread, tolerance)` as drift, append one line to
   an append-only ledger, exit non-zero; refuse a baseline/ledger path the target tracks,
   the profile scores, or that lives under `.git` — a canary must not move the metric it
   watches (#13).
7. **Provenance is mandatory per accepted decision** — model, route, engine version,
   referee version derived from the scoring command (`'verify:' + sha256(cmd)[:12]`),
   profile content hash, ISO-8601 UTC timestamp — and **replay validates the recorded
   margin**, not just the delta, or a plausible fabricated margin validates (#13).
8. **Probe the documented exploit paths** in memory, never in the working tree, scoring a
   seeded-defect detection rate against ground truth; an all-missed run exits 0 with rate
   0.0 and a probe that could not run is `null` + non-zero (#13).
9. **Backward compatibility is proved over a parameter grid**, not claimed: because the new
   threshold is ≥ the old floor, every new keep is an old keep — brute-force it (3,584
   metric-pair × direction × floor points, 0 keep mismatches, 474 legacy discards) (#13).
10. **Report honestly about the harness itself**: PR #21's integration run was `1 failed,
    28 passed` on a test that fails identically on clean `origin/main`, and the 124 path was
    unreached — recorded as such, not smoothed (#21, #24).

## Salvage and wall arithmetic (the engine half)

- `dead = not result.ok` replaces the unread revert. A dead agent's tree falls through the
  same ignored-file check, scope, protected-hash, commit, guard, measure and margin steps;
  a tree clearing the margin banks as `keep` with `salvaged: True` and `agent_exit_code`.
  A dead tree that clears nothing reports `agent_error` **carrying** the metric it measured;
  scope/protected violations keep their own names, because a breach is about the tree, not
  the score. Season 19 iteration 2 timed out at 755 s and still landed 27 ids, 19 of them
  from the dead call (#29).
- `ITERATION_TAIL = 120` and `_wall_exhausted = elapsed ≥ max_wall or elapsed +
  agent_timeout + ITERATION_TAIL ≥ max_wall`, used by both the loop top and the stop-reason
  computation so refusal and reason are one predicate; `max_wall == 0` stays unlimited
  (#29).
- The reserve is restated once, as a literal: `ROUND_RESERVE = 120` is also hard-coded in
  `MAX_WALL = ROUND_WALL − 120` (`arena.py:153`), so the chain is derived except at that one
  point; `ROUND_WALL = 2·SEAT_WALL + ROUND_RESERVE`, `ROUND_START_BUDGET = ROUND_WALL + 600`,
  `ROUND_CAP = 7` so `7 × 3000 ≤ 21,600` (#29, #34). The cap is derived, not a
  taste: before #34 `ROUND_WALL` was 1,800 s and `ROUND_CAP` was 8; once the two-seat
  round's wall grew to 2,400 s (`2 × SEAT_WALL 1140 + ROUND_RESERVE 120`) eight rounds
  would have cost 24,000 s against the 6 h season, so the cap fell to 7 (#34).
- A round that is arithmetically a one-seat round should be **recorded** as one: with an
  1,800 s round and a 750 s call, a 780 s seat starts, refuses to fund an iteration, and
  stops on `max_wall` with 0 iterations (#29, #34).

## Objective as record

The objective is data, not a constant, because a code edit can only describe the objective
the code now ships with — every earlier result stays recorded against an objective that no
longer exists to be read (#25).

- Two tracked files, two shapes: `metrics.json` (registry of every metric a leg may name)
  and `games.json` (lineage: `parent`, `status`, priced legs + weights, readings played
  without pricing, prize keys, periods owned, `reason`). Records live beside the module,
  never in a target checkout.
- **Every metric is a nine-field contract**: `name, direction, unit, command, repeats,
  noise_floor, exploit, cheat_probe, guard`. No command → not re-measurable next season; no
  exploit → not told what could game it; no probe/guard → a number a faker can move.
- **Directions are refused, never defaulted** (`DIRECTIONS = ('lower','higher')`): a silent
  default turns every regression into a win for a metric that should only fall.
- **Exactly one objective is active**, and every period is owned by exactly one record.
- **Fork on exhaustion**, with the reason written against the parent's *measured*
  exhaustion (which leg closed at its floor, which band is wider than any achievable win);
  a fork with no floor evidence is a rewrite. **Retire by status, never by deletion.**
- Loaders raise on unreadable; `validate()` returns **every** contradiction as a list so a
  hand-edited record is fixed in one pass (duplicate name, missing field, bad direction,
  unregistered leg, two active, period owned twice, dangling parent, parent cycle,
  duplicate id, active with no legs). The duplicate matters twice: `direction_of` walks the
  registry and returns the **first** entry whose `name` matches, so with two rows of one
  name the answer is whichever came first — a duplicate name is a silently redefined leg,
  not a cosmetic problem (#25).
- Pay only for what the measurement can resolve: `metric_profit = 100 · weight ·
  relative_improvement`, a leg whose measured band ≥ its improvement pays 0.0, weights
  clamped `0.5 … 3.0`, and an unobservable leg prices **down** to the floor, never up
  (R14). A prize keyed on a leg with no headroom is a rule that can never fire.

## Run-record shape

Three artefacts per period, one derived view: one machine record, one prose record in the
docs eight-section form, one human page that re-renders byte-identically (`--check` exits 0
only on byte identity; a `pending` record or a period with no narrative entry exits 2) (#27,
#45).

- **Close record — 19 keys** in `ledger/season-<N>.json`: `archived_rounds, banks,
  baselines, circumstance, close_commit, floor_before, floor_after, game, head,
  keeps[{commit,round,team}], matrix[], referee, review{means,previous,reason,weights},
  rounds, rounds_played, season, season_start_commit, weights_before, weights_after` (#45).
  `referee` is the 19th key, added with R37/#43 (the referee scored on its own job); a
  record that closed before that rule carries 18 keys — season 22's on-disk record does —
  and a 19-key record first appears at season 23 `[I]` (inference from R37/#43 — no
  season-23 ledger exists yet).
- **Per-leg reading row**: `{name, unit, lower_is_better, before, after, command, raw,
  verdict, note}`, where `raw` holds the referee's own `MEASURE` line — the record keeps
  evidence, not a paraphrase.
- **`provenance.json` per round**: `commit, engine_version, referee_version,
  profile_sha256, model, model_route, environment{platform, python, seat_mode,
  token_budget, wall_ceiling_seconds}, cost{tokens, wall_seconds}, round, timestamp`.
- **Honest-verdict checklist** — ten questions a record must answer before a number is
  called a win: commits named; floor measured (A/A); denominator pinned; instrument
  unchanged; unit actually served; guard before bank; patch-id proof of landing; artefact
  of the loss kept; operator (referee) scored; prose re-derived from the record.
- **Prove landing by patch-id, not ancestry**: a cherry-picked keep is never an ancestor of
  the branch it was picked onto, so `merge-base --is-ancestor` denies every keep (#31, #45).
- **Every count in generated prose is derived from the record and proved by a re-render**;
  a hardcoded number in a template is a lie waiting for data to disagree, and the
  disagreement prints as fact — "The four legs" over six, "One rounds settled", a
  fabricated `faster 1.00` (#31).
- **A zero from a field the record never wrote is not a measurement**: assert field
  presence before aggregating (the archived corpus's round rows carry no `landed` key, so
  a count of landed keeps prints 0 — absence, not measurement), and give "played and gained
  nothing" its own value instead of sharing zero with "never played" (#45).
- Keep closed records exactly as they closed; correct the index instead. Because a record
  is collected over a window and merged later, state the window and re-derive the verdict
  against the tree at merge time (#32, #33).

## Unattended-loop recipe pattern

A schedule that starts research is **code**, and code that exists only inside a harness
profile is untested, unreviewable and unrecoverable elsewhere (#9).

- **Recipe dir**: `<recipe>/{recipe.json, config.example.json, install.sh, the files it
  names}`; `install.sh` is 8 lines (`${BASH_SOURCE[0]:-$0}` + `exec ../install.py
  "$(dirname "$0")" "$@"`), so N recipes share one installer and one `scripts/` dir.
- **One generic idempotent installer**: `copy2` (installed copy byte-equal, proven with
  `cmp`), config merge with `config_renames` applied before the merge so a retired key
  moves instead of being replaced, create-or-edit decided by the scheduler's own listing,
  `--dry-run` renders the plan and returns before every guard. Values resolve
  `DEFAULTS ← <script stem>.config.json ← config.json ← env`.
- **Never derive the harness root from `$HOME`**: flag → explicit env → derived env → the
  account home from the password database, print the source, and refuse a scope dir without
  its own `config.yaml` — the duplicate-job incident cost a live job (#10).
- **The scheduler's listing decides create-vs-edit**; a state file is a hint. One match →
  edit, none → create, two → exit 2 naming both, unreadable → exit 2. Pin the resolved root
  into every child env and re-list after any mutation: a command that exits 0 without
  changing state is a failure (#19).
- **Interval tick + in-script window** beats a cron expression the ticker may not parse
  (no `croniter` on py3.12 → `next_run_at` null, errors after the first fire), and the
  window is testable as a pure function at its boundaries.
- **Guard ladder, each failing closed (skip a tick, never write twice)**: `--dry-run`
  first; outside the configured window on the configured offset → exit 0 silently; an
  unreadable session API → log and exit 0, never fire blind; a streaming or
  recently-touched session of the target profile blocks (`busy_session` over **all**
  sessions plus `idle_minutes`, because a worker between tool calls reports not-running);
  a live round blocks. The round marker must match the **argv shape actually used**
  (`ROUND_MARKER = (?:arena\.py|registry\.py\s+league)\b.*\sround(?:\s|$)` behind a broad
  `pgrep` prefilter, dry-run counts as in-flight) (#40).
- **Render the prompt at fire time from tracked repo state**, every probe degrading to a
  labelled string (`(unavailable — <why>)`) instead of raising, no `${` surviving, and a
  negative test that the prompt cannot name a command that does not exist; one declared
  command per probe (#18).
- **Install is not resume**: `install --dry-run → install → status → render → resume`; a job
  found by recipe **name**, never a remembered id; `status` read-only; `pause`/`resume`
  re-list and exit 1 if the state did not move (#19).
- The recipe shipped dry-run-only for a day and said so (`partial`); it closed `works` only
  on live evidence — installed files byte-identical, three idle ticks firing at 18:12,
  20:14, 22:16 UTC, and a fourth firing nothing because a session was live (#33, #9).

## What this capture does not carry

The league itself: `arena.py` (4,980 lines) with its captain protocol, banks, buys,
jackpot, golden buzz and location bonus; `referee.py` (2,580) and its five target-specific
metrics; `lineage.py` (475); `commands/registry.py` (1,090) as *content*; media film/voice
pipelines; the season pages and their film; `games.json`'s g0/g1/g2 history as history.
Those are properties of one target and one operator's iteration lengths, not of the
pattern. Constants quoted above (`SEAT_WALL 1140`, `ROUND_CAP 7`, `SEASON_WALL 21,600`,
`BUY_MAX 2`, `BUY_COST 2`) are that operator's choices — the *arithmetic between* them is
the durable part.
