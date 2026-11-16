# PRD 22 — Target Profile: the Measured Checkout as a Parameter

> Intent: ship the **contract** by which a harness scores a repository it does not
> live in. One JSON profile declares, key by key, what is resolved in the harness and
> what is resolved in the measured checkout; a target is a declared name, never a
> path; and a round hashes its evaluator surface at both ends, voiding itself when the
> evaluator moved. The tournament that motivated the contract (a 4,980-line arena, a
> captain economy, seasons of media) is **not** ported.
> **Domain:** `tpr` — target profile; this revision adds `obj` (the objective record)
> and `rec` (the run record) as a second, additive scope — see *Part B* below.
> **Canonical tests:** `tests/unit/test_target_profile.py` (`AC-TPR-001..016`),
> `tests/integration/test_target_profile_engine.py` (`AC-TPR-201..203`);
> `tests/unit/test_engine_objective.py` (`AC-OBJ-001..016`),
> `tests/unit/test_engine_record.py` (`AC-REC-001..012`),
> `tests/integration/test_objective_record_replay.py` (`AC-OBJ-201`, `AC-REC-201`).
> **Grounding:**
> [target-profile-contract](../../kb/concepts/target-profile-contract.md),
> [reward-hacking-countermeasures](../../kb/concepts/reward-hacking-countermeasures.md),
> [evaluator-legitimacy](../../kb/concepts/evaluator-legitimacy.md),
> [verify-guard-contract](../../kb/concepts/verify-guard-contract.md),
> [objective-as-record](../../kb/concepts/objective-as-record.md),
> [run-record-contract](../../kb/concepts/run-record-contract.md),
> [relocation-not-play](../../kb/concepts/relocation-not-play.md); raw sources
> [2026-11-16 target-profile contract](../../kb/raw/articles/2026-11-16-target-profile-contract.md),
> [2026-11-16 objective and run records](../../kb/raw/articles/2026-11-16-objective-and-run-records.md).
> **Builds on:** PRD 17 (engine). It adds a resolution layer in front of `init`, plus one
> additive engine flag — `--state-dir` — so the resolved `runs_dir` is the state a live
> round actually uses; without the flag the engine behaves exactly as PRD 17 records.
> **Stage 6:** `docs/22-target-profile.md` — **pending**; it is written from a
> verification run, not from this plan.

## Context

The engine already takes `--repo`, so one harness can measure many checkouts. What it
does not have is an **evaluator-side** contract: which files score the checkout, where
the state lives, and what happens when the evaluator itself moves. Every adopter meets
that question first, and the default answer — keep the evaluator inside the measured
repo — is wrong. The downstream league learned this with four live failures, each of
which this PRD turns into a success criterion:

1. **The profile pointed at the target's own evaluator.** Wave 1 copied the league's
   files but left `referee`, `guard_command` and `runs_dir` naming the target's
   `autoresearch/arena/`, so a round executed the measured repo's referee and wrote its
   state. AC-LGE-002/007/008 downstream. → SC-tpr-2: harness keys resolve in the
   harness, and a test pins that two targets produce the same evaluator path.
2. **Moving the evaluator out of the worktree moved it out of protection.** `--protect`
   only accepts a path inside the worktree a seat owns, so the evaluator had to leave
   the protected list — yet a seat runs as the same OS user and can write its absolute
   path, and the worktree diff never sees it. AC-LGE-012/015. → SC-tpr-5: a per-round
   evaluator hash that voids the round, with the two-read limit stated rather than
   hidden.
3. **A coverage claim that was not re-run.** "One test carries all 43 cases" carried the
   happy path. AC-LGE-017/025. → the Test Mapping below is per-AC and every id is
   re-run by the tier that names it; no SC rests on a restated count.
4. **A required key naming the subject's own artifacts went stale.** When the target
   deleted its test files, `arena_test_files` could not be deleted from the profile: the
   failure mode is "missing key", not "engine behaved badly". AC-LGE-002 again. →
   SC-tpr-4: an honest empty value ships as `[]`, and a deleted key is refused by name.

**Users.** (a) An adopter running this harness against their own repo who must know
which paths a round may edit and which files score it; (b) a reviewer who must decide
whether a recorded reading was produced by a surface the candidate could reach.

**Constraints.** Stdlib only; no `shell=True`; every subprocess bounded by a timeout;
no secret value in a profile or a printed plan; mutating execution stays out of scope —
`profile` prints a plan, `init`/`run` remain the only writers and are not invoked by
this layer.

## Scope

In: `autoresearch/target/` — `target.py` (one schema, `resolve_target`, `profile_path`
/ `load_profile` refusal-by-name, `apply_profile` per-key relativity with reasons,
`engine_argv`), `guard.py` (`evaluator_files`, `digest`, `tamper`, `RoundGuard`),
`cli.py` (`autoresearch profile <name> [--repo PATH] [--json]`), `import_runs.py`; the
declared profiles under `autoresearch/targets/` (`example.json`); the wrapper's
`profile` dispatch in `autoresearch/engine/bin/autoresearch`; the engine's additive
`--state-dir PATH` on `init`/`run`/`status`/`report` (config field `state_dir`); the
`.gitignore` rule for `autoresearch/runs/*`; the ACs above.

Out: the arena, referee, captain economy, corpus, media, season pages and the 4,980-line
`arena.py` (they stay downstream); any scoring layer in this repo (PRD 20's *Out of
Scope* still holds — the example profile's `referee` names a path the adopter supplies);
mutating round execution; REST/MCP exposure of `profile`.

**Part B (W2) — the objective and the run record.** In: `autoresearch/objective/registry.json`
(the tracked record of what is optimised), `autoresearch/engine/autoresearch/objective.py`
(reader, validator, lookups, CLI), `autoresearch/engine/autoresearch/record.py` (close
record, readings, `--check`), the engine's additive `init --objective/--objective-leg`
and `report --record/--check`, the run config's four objective fields, and the `raw`
line a measurement now carries in its ledger event. Out: the captain economy, seats,
buys, buzz, pots, jackpots, media and season pages — all downstream-specific. The
divergences are recorded in *Assumptions* rather than implied.

## Success Criteria

- **SC-tpr-1 — A target is a declared name, resolved once and purely.** The checkout is
  the flag, else `$AUTORESEARCH_TARGET_REPO`, else `cwd`, resolved before any state is
  read. A profile is `autoresearch/targets/<name>.json`: an undeclared name is refused
  naming the declared ones, and a traversal-shaped name (`../x`, `a/b`, `..`, `~x`, a
  `*.json` filename, an empty string) is refused as a path before the filesystem is
  touched. A profile that is unreadable, is not an object, is missing a key, or calls
  itself a different name is refused **by name** with the missing keys listed.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-001..005, AC-TPR-014),
  `tests/integration/test_target_profile_engine.py` (AC-TPR-202).
- **SC-tpr-2 — Every path key declares its relativity, and the harness half does not
  move.** Harness-owned keys — `engine`, `referee`, `guard_command`, `runs_dir` —
  resolve against the repo that ships the profile. `engine`, `referee` and
  `guard_command` accept an absolute path as given (an adopter's evaluator may live
  outside this tree); `runs_dir` is harness-relative or an absolute path **inside** the
  harness repo, because state that lands elsewhere is state nobody owns. Target-relative
  keys — `program`, `scopes`, `protected`, `docker_free_tier`, `e2e_dir`, `context_dir`,
  `dockerfile`, `fresh_script`, `guard_steps`, `fresh_instruction`, `arena_test_files` —
  resolve inside the named checkout. The split is stated in the profile's own `$comment`;
  two checkouts resolve to one evaluator path and two different target paths.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-006, AC-TPR-013),
  `tests/integration/test_target_profile_engine.py` (AC-TPR-201, AC-TPR-202).
- **SC-tpr-3 — A misdescribed profile is refused key by key, never half-applied.** A
  target-relative key that is absolute, contains `..`, or escapes the checkout is
  returned as a reason in `refused` beside every other bad key (wrong type, unknown
  direction, unknown key, name mismatch); nothing is raised one key at a time and the
  keys that did resolve stay resolved, so a caller reports the whole misdescription
  once and the plan is never emitted for a refused profile.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-005, AC-TPR-007).
- **SC-tpr-4 — An honest empty value ships empty; a deleted key is refused.** A list
  key whose honest value is empty (`arena_test_files: []`) resolves to an empty tuple
  and is not refused; deleting the key is refused by name. This is the downstream PR
  #20 lesson made mechanical: present-but-empty is information, absent is a typo.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-008, AC-TPR-014).
- **SC-tpr-5 — The evaluator is hashed at both ends of a round; a change voids it.**
  `evaluator_files` covers the referee, the profile file, the three contract modules,
  the engine wrapper and every engine package module. `digest` is a sha256 per file with
  `None` for a missing one; `tamper` is a pure comparison returning the void record
  (`round: void`, `event: protected_violation`, reason, the changed paths). A round
  whose evaluator sits inside the measured checkout is refused at start — a file the
  subject can edit cannot be the thing that scores it — and so is a round whose
  evaluator is missing. A round whose evaluator changes settles nothing, keeps the
  tampered files as evidence, and writes nothing to the checkout. Two hash reads cannot
  see a write-then-restore — that limit is stated in `guard.py`'s docstring and in the
  KB page, not papered over.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-010..012, AC-TPR-016).
- **SC-tpr-6 — The profile resolves to a plan, and the plan runs.** `engine_argv()`
  names the harness engine, the checkout, `--state-dir <runs_dir>/state`, the substituted
  `--verify` / `--guard` commands, `--metric-name`/`--direction`, one `--scope` per leg
  path (deduplicated), `--protect` per protected file and `--program`; it is emitted as a
  list (never shell text) and is never executed by this layer. In the integration tier
  the emitted argv initialises a scratch checkout and a replay against it records a keep
  with a valid ledger.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-009, AC-TPR-014, AC-TPR-015),
  `tests/integration/test_target_profile_engine.py` (AC-TPR-201).
- **SC-tpr-7 — An external record moves by one copy command, through one validator.**
  `import_runs.py` copies `state.json`, `scoreboard.md`, `season-*` and `round-*` into a
  profile's runs directory; `--dry-run` writes nothing and prints every item with its
  file count; an existing `state.json` refuses (exit 1) without `--force`; `*.lock` and
  `__pycache__` are never carried. The destination is `runs_dir` read by
  `target.load_profile` / `apply_profile` — the same pair `profile` uses — so a
  traversal-shaped name, a missing profile, or a `runs_dir` outside the harness repo is
  refused with the validator's own reason, and an absolute `runs_dir` inside the harness
  repo is accepted.
  _Verify:_ `tests/unit/test_target_profile.py` (AC-TPR-013).
- **SC-tpr-8 — The round's state is the harness's, and the engine is told where.**
  `init`, `run`, `status` and `report` take an optional `--state-dir PATH`; it moves
  `run.json`, the ledger, the report and the `command` adapter's prompt file, and its
  absolute path is persisted as `state_dir` in `run.json` so a later command is told
  where to look rather than guessing from the checkout. Without the flag the engine is
  byte-for-byte the old behaviour (`<repo>/.autoresearch`), so an existing ledger replays
  unchanged. With it, a profile-driven round writes no `.autoresearch` into the measured
  checkout — the claim the contract is for.
  _Verify:_ `tests/unit/test_engine_config.py` (AC-ENG-046),
  `tests/unit/test_target_profile.py` (AC-TPR-015),
  `tests/integration/test_target_profile_engine.py` (AC-TPR-203).

## Success Criteria — Part B (objective and run record)

- **SC-obj-1 — An objective is a tracked record, and one leg at weight 1.0 is the
  degenerate case.** `autoresearch/objective/registry.json` declares every objective:
  its legs (name, direction, unit, command, repeats, noise_floor, guard, and an optional
  pinned `baseline` of `commit` plus the `declared/credited/uncovered` trio), its
  weights, its status, its parent, the seasons and rounds it owns, and a reason.
  `objective validate` lists every contradiction in one pass — exit 1 for an
  inconsistent record, exit 2 when `--file` names a file that cannot be opened, the
  same operator-error code `init` uses; `objective resolve` prints the
  `--verify/--metric-name/--direction/--repeats/--noise-floor` arguments a leg implies,
  as argv, never shell text that is then run. A single leg at weight 1.0 resolves, and
  the shipped record validates.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-001, AC-OBJ-014).
- **SC-obj-2 — Every leg is a contract, and a direction is refused rather than
  defaulted.** A leg missing `unit`, `command`, `repeats`, `noise_floor` or `guard` is
  named with the missing field; a duplicate leg name is refused (a leg is a lookup
  key); a direction outside `lower|higher` is refused, because a silent default turns
  every regression into a win for a metric that should only fall.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-002, AC-OBJ-003, AC-OBJ-004).
- **SC-obj-3 — Weights are complete and clamped.** Every weight names a declared leg,
  every leg carries a weight (an unweighted leg is not priced), and every value lies in
  `[0.5, 3.0]` inclusive — the downstream clamp, stated as data.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-005, AC-OBJ-006).
- **SC-obj-4 — Exactly one objective is active, and every period has one owner.** Two
  active objectives are refused naming both (two weights for one run and no way to say
  which settled it); a season or a round listed by two objectives is refused naming
  both accounts.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-007, AC-OBJ-008).
- **SC-obj-5 — A fork has a parent that exists, a chain that ends, and a reason.** A
  dangling parent and a parent cycle are refused; a fork with no reason and a
  retired/archived objective with no reason are refused. The reason is where the
  parent's measured exhaustion is written; a fork without it is a rewrite.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-009, AC-OBJ-015).
- **SC-obj-6 — A leg at its floor leaves the rotation, and the rotation is exactly as
  long as the playable legs.** A leg with `best` and `floor` declared at its floor is
  refused in a rotation (a scheduled leg nobody can move hands a free zero to whoever
  draws it); a rotation longer or shorter than the playable legs is refused, and a
  playable leg it drops is named. An active objective with no legs is refused.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-010, AC-OBJ-011).
- **SC-obj-7 — Every contradiction is reported in one pass.** Three or more simultaneous
  defects — duplicate leg, bad direction, out-of-clamp weight, unknown weight key, two
  actives, dangling parent — come back as one list, each naming its offender; the CLI
  exits 1 and prints every problem, so a hand-edited record is fixed once.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-012, AC-OBJ-014).
- **SC-obj-8 — The record feeds the engine, and the report names it.**
  `init --objective <file>` stores the absolute record path, its id, the resolved leg
  and the leg's unit in `run.json`, and derives verify/metric/direction/repeats/
  noise-floor/guard from that leg; an explicit flag that **restates** the leg is
  accepted, and one that **contradicts** it is refused with exit 2 — a run measuring
  another command, direction or floor under the objective's name would leave a record
  that disagrees with its own objective. `report` prints the
  objective id when one is configured. A multi-leg objective requires
  `--objective-leg`, and a leg at its floor is refused rather than resolved. In the
  integration tier a single-leg objective drives a real replay whose ledger validates.
  _Verify:_ `tests/unit/test_engine_objective.py` (AC-OBJ-013, AC-OBJ-016),
  `tests/integration/test_objective_record_replay.py` (AC-OBJ-201).
- **SC-rec-1 — A closed run leaves a comparable record.** `report --record` writes
  `record.json` and `record.md` into the run's state directory: the objective id, the
  parent and close commits, the per-leg baseline (`commit`, `value`, and the pinned
  `declared/credited/uncovered` trio when the objective declares one), the keeps
  (`commit`, `round`, `leg`), `review{means, previous, weights, reason}`, the floors,
  the state directory **as a label** (repo-relative, else its basename — a record
  travels with the harness and must not carry host layout), the provenance block of
  the last decision, and the legs declared but not measured by this run. Every count
  in the record and its prose derives from the ledger.
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-001, AC-REC-002).
- **SC-rec-2 — A verdict is required, closed, and defined by cause.** Every reading row
  carries `name, unit, lower_is_better, before, after, command, raw, verdict, note`, and
  the repeat series (`values`) whenever the reading was reduced from more than one
  measurement. `verdict` is one of `improved | held | displaced`, each with the KB
  definition printed beside it; a `held` or `displaced` reading with no note is a
  failure, because the note is where the cause is named.
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-003, AC-REC-009).
- **SC-rec-3 — The record is written beside the run and re-renders byte-identically.**
  `--record` writes both artefacts under `--state-dir` when it is set; `--check`
  re-renders from the ledger and exits 0 only on byte identity, exits 2 on any drift,
  and exits 2 when either artefact is missing or the run has not stopped (a pending
  record is a guess).
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-004, AC-REC-005, AC-REC-006),
  `tests/integration/test_objective_record_replay.py` (AC-REC-201).
- **SC-rec-4 — The honest-verdict gate refuses the mechanically detectable lies.**
  `--record` refuses to write, and `--check` fails, when baseline commits differ across
  legs, when a keep's commit is not an ancestor of the close commit, when a
  `held`/`displaced` reading carries no note, when a reading has no `raw` line, when a
  `raw` line does not reproduce the recorded value, when the
  `declared/credited/uncovered` trio is partial, is not three numbers (a `'1,027'` is a
  label, not a zero), or does not add up, or when a pinned baseline commit is not the
  commit the run measured. The rest of the checklist needs a reader and is stated below
  as the human list.
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-007, AC-REC-008, AC-REC-010,
  AC-REC-011).
- **SC-rec-5 — The record keeps the evaluator's own line.** A measurement records the
  exact stdout line the metric was parsed from (`raw`), not a paraphrase, in both the
  baseline and trial events; with repeats>1 it is the line of the **median repeat**, so
  a verify printing 6, 6, 7 records `after 6.0` beside the line that printed 6 and the
  reading carries the series it was reduced from. The record carries it forward, and a
  ledger written before this field existed fails `--record` with a message naming the
  missing line rather than rendering a hole.
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-002, AC-REC-010),
  `tests/unit/test_engine_measure.py` (AC-ENG-005).
- **SC-rec-6 — A run without an objective is unchanged.** Without `--objective`,
  `run.json` gains four null fields and `report` gains no line; without `--record`,
  `report.md` and `results.tsv` are byte-for-byte what PRD 17 records, and an old
  `run.json` still loads.
  _Verify:_ `tests/unit/test_engine_record.py` (AC-REC-012),
  `tests/unit/test_engine_objective.py` (AC-OBJ-016).

## The human half of the honest-verdict checklist

The four checks above are the ones a machine can settle. The other six need a reader,
and a reviewer who skips them has only a number (see
[run-record-contract](../../kb/concepts/run-record-contract.md)):

1. Was the unit actually served (void rows excluded, not zeroed)?
2. Did the guard run **before** the bank, and does the revert name its commit?
3. Is landing proved by **patch-id**, not ancestry? (Our engine commits its keeps on the
   run's own branch, so ancestry is a valid proof *here* — the note is for a port that
   cherry-picks.)
4. Is the artefact of the loss kept, with its hash, and explicitly not promoted?
5. Is the **operator** scored (voids, unreadable readings, rounds where nothing moved)?
6. Is every count in the prose re-derived and proved by a re-render that fails on drift?

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-tpr-1 | AC-TPR-001, 002, 003, 004, 005, 014 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-1 | AC-TPR-202 | `tests/integration/test_target_profile_engine.py` | integration |
| SC-tpr-2 | AC-TPR-006, 013 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-2 | AC-TPR-201, 202 | `tests/integration/test_target_profile_engine.py` | integration |
| SC-tpr-3 | AC-TPR-005, 007 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-4 | AC-TPR-008, 014 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-5 | AC-TPR-010, 011, 012, 016 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-6 | AC-TPR-009, 014, 015 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-6 | AC-TPR-201 | `tests/integration/test_target_profile_engine.py` | integration |
| SC-tpr-7 | AC-TPR-013 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-8 | AC-ENG-046 | `tests/unit/test_engine_config.py` | unit |
| SC-tpr-8 | AC-TPR-015 | `tests/unit/test_target_profile.py` | unit |
| SC-tpr-8 | AC-TPR-203 | `tests/integration/test_target_profile_engine.py` | integration |
| SC-obj-1 | AC-OBJ-001, 014 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-2 | AC-OBJ-002, 003, 004 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-3 | AC-OBJ-005, 006 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-4 | AC-OBJ-007, 008 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-5 | AC-OBJ-009, 015 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-6 | AC-OBJ-010, 011 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-7 | AC-OBJ-012, 014 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-8 | AC-OBJ-013, 016 | `tests/unit/test_engine_objective.py` | unit |
| SC-obj-8 | AC-OBJ-201 | `tests/integration/test_objective_record_replay.py` | integration |
| SC-rec-1 | AC-REC-001, 002 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-2 | AC-REC-003, 009 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-3 | AC-REC-004, 005, 006 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-3 | AC-REC-201 | `tests/integration/test_objective_record_replay.py` | integration |
| SC-rec-4 | AC-REC-007, 008, 010, 011 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-5 | AC-REC-002, 010 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-6 | AC-REC-012 | `tests/unit/test_engine_record.py` | unit |
| SC-rec-6 | AC-OBJ-016 | `tests/unit/test_engine_objective.py` | unit |

## CI/CD Gate

- The unit ACs run in the existing `unit` job (`pytest tests/unit`); the integration
  ACs run in the existing `integration` job — both tests are hermetic (throwaway git
  repos, a copied harness, a scripted replay, no model, no network). No new job.
- `scripts/audit_pyramid.py` holds the new modules to the comment budget and the banned
  pattern list; `no shell=True` and bounded subprocesses are already the engine's rule.
  The one new subprocess (`git merge-base --is-ancestor`) carries `timeout=30`.
- The `doctrine` job's tracked roots are unchanged: `autoresearch/target/`,
  `autoresearch/targets/` and the new `autoresearch/objective/` nest under the existing
  `autoresearch/` root, so this is not a new tracked root and funnel rule 11 does not
  apply.
- `kb/raw/` gains one capture; `.github/workflows/sources-readonly.yml` requires the
  `ingest` label on that PR — the branch is merged with the label, not without it.

## Assumptions

- [ASSUMPTION] **The schema is one list, and two keys are this repo's addition.**
  Downstream carries `PROFILE_KEYS` (11) in `arena.py` and `REQUIRED_KEYS` (8) in
  `referee.py` with no shared validator; this port ships one `PROFILE_KEYS` and one
  validator. `metric_name` and `direction` are new, declarative keys: the template
  engine takes one metric per `init`, where downstream prices several legs, so a plan
  needs to name the metric it measures. The relativity rule is unaffected — they are
  neither harness nor target paths.
- [ASSUMPTION] **A target is a name, not a path.** Downstream accepts
  `--target-profile PATH`; this port refuses a path-shaped name deliberately. A
  profile is part of the evaluator surface, hashed each round, so it should be a
  tracked, reviewable file under `autoresearch/targets/`, not an arbitrary path a
  caller can swap in. An absolute `referee` inside a profile is still honoured — the
  adopter may keep their evaluator outside this repo's tree.
- [ASSUMPTION] **`--verify` is derived, not declared.** The profile names the referee
  and the guard template; the reading is `python3 <referee> --target-repo <target>`.
  That is the one convention this port adds to the evaluator protocol, and it is stated
  in `target.py` and the example's `$comment`. A referee that does not accept
  `--target-repo` needs the template changed in one place.
- [ASSUMPTION] **Leg scopes are unioned for one `init`.** The profile keeps the
  downstream leg map (`better`, `cheaper`, …) because it is the honest description of
  what a round may edit, but a single-metric engine receives the union, deduplicated in
  declaration order. A harness that prices legs per metric can read `scopes` directly.
- [ASSUMPTION] **Two hashes are not proof against a same-user writer.** They detect a
  change between start and settle, not a write-then-restore. The downstream record says
  so; this PRD repeats it in `kb/concepts/target-profile-contract.md`. A read-only
  mount or a distinct OS user is future work, and until then the void record is the
  strongest claim the contract can make.
- [ASSUMPTION] **`$AUTORESEARCH_TARGET_PROFILE` is a name here, a path downstream.**
  The downstream league reads the same variable as a filesystem path; this port accepts
  it only as a declared name, so a path-shaped value is refused with the reason. A
  copied downstream invocation therefore fails loudly instead of silently scoring
  through whatever file the path names.
- [ASSUMPTION] **`guard_steps`, `fresh_script`/`fresh_instruction` and `context_dir` are
  resolved-but-inert schema.** They are validated and resolved like every other key so
  a profile that declares them is honest, but this engine's `init` takes one `--guard`
  and knows no fresh-pin or context-budget step; they are carried for the consumer that
  will read them (a multi-step guard, a pin check, a context metric), and no SC claims
  they run.
- [ASSUMPTION] **The example profile's evaluator is a stub path.** It names
  `autoresearch/target/referee.py`, which this repo does not ship: PRD 20 deliberately
  excludes a scoring layer. The path must exist at round time — `profile example` prints
  a well-formed plan and `RoundGuard.start` refuses the round as missing — and the
  integration tier proves the contract with its own demo profile and evaluator instead
  of pretending the stub is runnable.
- [ASSUMPTION] **The economy is not ported; the weights are.** Downstream's band-gated
  pay (`metric_profit = 100 · weight · relative_improvement`, a leg whose measured band
  is at least its improvement paying `0.0`) and its `rules.jackpot_keys` are SPECIFIC to
  the tournament and stay there. This port keeps weights because they are data about
  what is optimised — a fork's opening priorities — but nothing here prices a round,
  pays a pot or settles a seat. `objective resolve` reads one leg; a harness that prices
  several reads the record directly.
- [ASSUMPTION] **`dry_streak` is declared but never computed downstream, and is not
  ported.** `games.json` carries `0` in all three games and no code writes or reads it
  beyond one prompt display — a schema field with no writer is a slot a hand-editor
  fills by guess. This port refuses to ship a field it cannot compute.
- [ASSUMPTION] **Period ownership (`seasons`/`rounds`) is hand-maintained and
  validated, not written — one step above `dry_streak`.** No code writes the list and no
  code derives it from the ledger; it is kept because the validator constrains the edit
  (integers only, and one period cannot be claimed by two objectives), which is exactly
  the property `dry_streak` lacks. An adopter told that a played period was never listed
  gets nothing but a human checklist item; cut the key of a port that never forks
  objectives, since a single objective owns everything it plays.
- [ASSUMPTION] **The close-attribution error cannot repeat, but the unlisted-period
  half can.** Downstream played seasons 20–22 on `g1` without listing them, so a close
  attributed them to `g0`; `g1.notes` records the retroactive listing and `g2.notes`
  records season 23 attributed the same way. Here the objective id is written into
  `run.json` at `init` and copied into the close record, so a close cannot re-derive a
  different owner. What remains hand-maintained is the objective record's own
  `seasons`/`rounds` list: validation refuses a period two objectives claim, but cannot
  know a period that was played and never listed. Listing a period at close stays a
  human step, stated in the human checklist rather than implied by the validator.
- [ASSUMPTION] **`weights_after` is machine-written, not copied.** Downstream's close
  record carries `weights_after`, which the next fork's case adopts by hand. This
  record writes `review.previous` and `review.weights` from the run config and the
  resolved leg, so the next reader reads a record instead of a transcript. The engine
  does not reprice (there is no economy), so `weights` equals the declared weight and
  `review.reason` says so in words derived from the ledger; a run with no objective
  record carries the identity weight `1.0` and says that too.
- [ASSUMPTION] **Some record fields are carried for fidelity, not enforced.** The
  shapes are downstream's, so they are kept; `--check` does not judge them:
  `review.previous` is the declared weight and is identical to `review.weights` by
  construction (nothing reprices between records); `floor_before` and `floor_after` are
  the same config value, because the engine never re-measures its own floor mid-run; and
  the `provenance` block is written to `record.json` but not rendered in `record.md`
  (it is a reference to a decision, and `status --require-provenance` is its gate). An
  adopter reading `--check` as "clean" should read these three as *informational*: they
  are copied, not verified. `record.md` says so for the floor line.
- [ASSUMPTION] **A leg's floor is only known after a measurement.** `best` and `floor`
  are optional per leg: a record is written before the first round, and an at-floor
  check with only one half present would be a guess. Validation reports a half-declared
  pair and stays silent on an unmeasured leg; the rotation is then all declared legs.
- [ASSUMPTION] **`displaced` is expressible but not machine-detected.** `verify` and the
  protected files are fixed for the life of a run, so the instrument cannot move under
  it; the mechanical builder therefore emits `improved` or `held`. A record that knows
  the cost moved elsewhere — a shorter test tier, an upstream commit — supplies
  `displaced` and its note, which the gate requires. `improved` printed over a
  relocation is the failure mode human checklist item 4 exists to catch.
- [ASSUMPTION] **`report --check` is the record's check surface.** There is no separate
  `record` subcommand: the record is a view of the same ledger `report` reads, and two
  commands over one source drift. `--record` writes, `--check` re-renders; missing,
  pending, drifted and gate-failing records all exit 2, and the two flags are mutually
  exclusive.
- [ASSUMPTION] **A pre-existing ledger fails `--record`.** The `raw` line arrives with
  this change, and a record owes the evaluator's own line. It is deliberately not
  back-filled from `values` — that would be a paraphrase of evidence. `report` without
  `--record` is byte-for-byte unchanged, so an old run still reports; it cannot claim a
  comparable record until it has been re-run.
- [ASSUMPTION] **The objective module is ~400 lines against the ~200 the port planned.**
  Every refusal carries its own message (the one-pass list is the point), and the
  at-floor and rotation rules are new. The shape is the port: raise on unreadable input,
  return every contradiction on an inconsistent record, and look up by name.
- [ASSUMPTION] **The shipped registry is an example an adopter edits.** It names this
  repo's own contract (`val_bpb`, `python3 train.py`, `python3 prepare.py`) as one leg at
  weight 1.0. `objective validate` is the check that keeps it honest; a fork adds an
  objective with a `parent` and a reason, and `init --objective-leg` selects which leg a
  run measures.

## Confidence

**High for the resolution, relativity, refusal and import behaviour** — each is a
hermetic unit test on pure functions plus one integration test that runs the printed
plan end to end against a scratch checkout. **Medium for the guard as a *sufficiency*
claim**: it provably detects a change between its two reads (AC-TPR-010..012), and it
provably writes nothing, but it cannot see a write-then-restore, and the KB page says
so. The schema itself is a judgement call: one validator and two extra declarative keys
are a deliberate divergence from downstream, recorded here rather than hidden.

**High for the objective validator and the record shape** — the validator is a pure
function tested rule by rule, the record is a pure function of the ledger re-rendered
byte-for-byte, and one integration test drives a single-leg objective through a real
replay whose ledger validates and whose close record passes `--check`. **Medium for the
honest gate as a sufficiency claim**: four of the ten questions are mechanically
settled and red-proofed one by one, the other six need a reader and are stated as such.
**Medium for `displaced`**: the enum is required and the note is enforced, but the
single-instrument engine cannot produce the verdict itself. **High for backward
compatibility**: without `--objective` and `--record` the run config and both report
artefacts are what PRD 17 records.
