# PRD 22 — Target Profile: the Measured Checkout as a Parameter

> Intent: ship the **contract** by which a harness scores a repository it does not
> live in. One JSON profile declares, key by key, what is resolved in the harness and
> what is resolved in the measured checkout; a target is a declared name, never a
> path; and a round hashes its evaluator surface at both ends, voiding itself when the
> evaluator moved. The tournament that motivated the contract (a 4,980-line arena, a
> captain economy, seasons of media) is **not** ported.
> **Domain:** `tpr` — target profile.
> **Canonical tests:** `tests/unit/test_target_profile.py` (`AC-TPR-001..016`),
> `tests/integration/test_target_profile_engine.py` (`AC-TPR-201..203`).
> **Grounding:**
> [target-profile-contract](../../kb/concepts/target-profile-contract.md),
> [reward-hacking-countermeasures](../../kb/concepts/reward-hacking-countermeasures.md),
> [evaluator-legitimacy](../../kb/concepts/evaluator-legitimacy.md),
> [verify-guard-contract](../../kb/concepts/verify-guard-contract.md); raw source
> [2026-11-16 target-profile contract](../../kb/raw/articles/2026-11-16-target-profile-contract.md).
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

## CI/CD Gate

- The unit ACs run in the existing `unit` job (`pytest tests/unit`); the integration
  ACs run in the existing `integration` job — both tests are hermetic (throwaway git
  repos, a copied harness, a scripted replay, no model, no network). No new job.
- `scripts/audit_pyramid.py` holds the new modules to the comment budget and the banned
  pattern list; `no shell=True` and bounded subprocesses are already the engine's rule.
- The `doctrine` job's tracked roots are unchanged: `autoresearch/target/` and
  `autoresearch/targets/` nest under the existing `autoresearch/` root, so this is not a
  new tracked root and funnel rule 11 does not apply.
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

## Confidence

**High for the resolution, relativity, refusal and import behaviour** — each is a
hermetic unit test on pure functions plus one integration test that runs the printed
plan end to end against a scratch checkout. **Medium for the guard as a *sufficiency*
claim**: it provably detects a change between its two reads (AC-TPR-010..012), and it
provably writes nothing, but it cannot see a write-then-restore, and the KB page says
so. The schema itself is a judgement call: one validator and two extra declarative keys
are a deliberate divergence from downstream, recorded here rather than hidden.
