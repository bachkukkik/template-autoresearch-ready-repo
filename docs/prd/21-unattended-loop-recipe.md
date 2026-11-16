# PRD 21 — The Unattended Loop Recipe: a Schedule That Is Code

> Intent: ship the **unattended trigger** the engine has always needed and never
> had. A recipe is a directory in this repo — the job definition, the exact
> files the scheduler runs, the knobs they read — installed into a harness
> profile by one generic idempotent installer, and fired only through a guard
> ladder that fails closed. The loop that follows the fire is the engine this
> repo already has: the schedule wakes it, the recipe is how it is woken.
> **Domain:** `urc` — unattended recipe. **Canonical tests:**
> `tests/unit/test_supervisor_recipe.py` (`AC-URC-001..024`),
> `tests/integration/test_supervisor_install.py` (`AC-URC-201..203`).
> **Grounding:**
> [unattended-loop-recipe](../../kb/concepts/unattended-loop-recipe.md),
> [loop-stop-conditions](../../kb/concepts/loop-stop-conditions.md),
> [headless-harness-invocation](../../kb/concepts/headless-harness-invocation.md),
> [harness-portability](../../kb/concepts/harness-portability.md),
> [run-record-contract](../../kb/concepts/run-record-contract.md); raw source
> [2026-11-16 unattended loop, implemented](../../kb/raw/articles/2026-11-16-unattended-loop-recipe-implemented.md).
> **Builds on:** PRD 17 (the engine) and PRD 22 (the objective and the run
> record). It adds no engine subcommand: the recipe renders a prompt and the
> fired session drives `init` / `run` / `status` / `report` exactly as a human
> would. The one additive engine change is the round marker — a file a run
> writes and removes, so a schedule can see a detached run it did not start.
> **Stage 6:** `docs/25-unattended-loop-recipe.md` — **pending**; it is written
> from a live install, not from this plan. (`docs/21` is the agent-evals record:
> downstream numbering fixes PRD 20's record at 21, so this PRD's record takes
> the next free number.)

## Context

Two of this repo's PRDs promise overnight research — `docs/prd/02` ("run the
loop unattended") and `docs/prd/17` ("an overnight loop on their own repo") —
and the engine ships `--max-iterations` and `--max-wall` to run bounded. Nothing
starts it, and nothing stops it starting twice. Every adopter therefore
re-invents the same fragile layer: a script dropped into a harness profile where
it has no diff, no review, no test and no second machine. The downstream fork
paid for that layer twice:

1. **An install with no explicit root minted a duplicate job.** `~/.hermes`
resolved through `$HOME`, which inside a harness-spawned process is a
*per-profile* home; its `profiles/<p>/` existed and its job store did not, so
the listing read as empty and a create ran beside the live job. → SC-urc-5.
2. **A liveness guard failed open mid-round.** The process guard matched the
literal `"arena.py round"`, but global flags sat between the script and the
subcommand, so a live round was invisible and a second writer was fired into
it. → SC-urc-6, which replaces a fragile scan-first guard with a marker the
run itself writes.
3. **An installer that also resumed hid a state change.** `cron edit` cannot
unpause, so a recipe shipped paused stayed paused — and "install then run"
became two hand-typed commands outside the declared surface. → SC-urc-8:
install is not resume.

**Users.** (a) An adopter who wants their measured repo improved overnight and
needs to trust a result they did not watch happen; (b) a reviewer who must
decide whether a recorded reading came from a run that was actually started
once.

**Constraints.** Stdlib only; no `shell=True`; every child bounded by a timeout;
no credential anywhere in a recipe or a printed plan (the WebUI URL is
configuration or environment, never code); the schedule stores no state the repo
does not track.

## Scope

**In.** `autoresearch/supervisor/` — `install.py` (the generic installer),
`control.py` (status / pause / resume), `schema.py` (`recipe.json`'s fields and
validator), `guards.py` (the ladder as pure functions), `hermes_binding.py` (the
one scheduler binding, with the interface for a second documented in its
docstring), `README.md` (the runbook), and `overnight/` — `recipe.json`,
`config.example.json`, `install.sh`, `launch.py`, `prompt.tmpl.txt`,
`charter.md`. The engine gains `autoresearch/engine/autoresearch/marker.py` and
one line in `cmd_run` that holds the marker for the run's lifetime.

**Out — stays downstream.** The league's season vocabulary (bounties, jackpot,
paid legs, seats, captains), its prompt template and verbatim charter, its
lineage and `DEFAULTS`, `referee`/`arena.py`, the command registry's
`local_only` wiring, and the 870-line stage-6 record. This repo has no league;
what it has is one metric per run and a record of it, so the recipe is
`overnight-loop`, not `arena-overnight`. A scheduler other than Hermes is out of
scope **as shipped** — see SC-urc-4 and *Assumptions*.

## Success Criteria

- **SC-urc-1 — A schedule is a tracked recipe, and the installed copy is build
output.** A recipe directory carries `recipe.json` (name, schedule, installed
script, delivery, timezone, `files`, `config_renames`, `note`),
`config.example.json` and the files it names. The schema validates in one pass
and reports every defect: a missing required key, a `files` value that is not
a bare filename, a `script` that is not one of the installed files, a listed
source that does not exist, a `config_renames` that is not an old→new name
map. The installer copies with `copy2`, so the installed file is the recipe's
bytes and a test compares them. _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-001, AC-URC-001b, AC-URC-002).
- **SC-urc-2 — The install is idempotent, non-destructive, and inert on a dry
run.** The scheduler's own listing decides create-versus-edit (one match →
edit, none → create, two → exit 2 naming both ids, an unreadable listing →
exit 2, never an empty match list). The scheduler's state file is a
cross-check, never the decider — and when it names a job the listing cannot
see, the installer refuses (exit 2, naming the stored id and pointing at
`control.py status`) instead of creating a second job beside it. `--dry-run`
prints every copy, config write, command and the recipe's own `note`, and
writes nothing at all. After a real install the script must exist and a
re-list must show exactly one job; a create that minted a second job is a
failed install (exit 1). _Verify:_ `tests/unit/test_supervisor_recipe.py`
(AC-URC-005, AC-URC-008, AC-URC-009, AC-URC-009b, AC-URC-010, AC-URC-012),
`tests/integration/test_supervisor_install.py` (AC-URC-201, AC-URC-201b).
- **SC-urc-3 — Machine values are configuration, merged in one stated order.**
The installed config is `config.example.json` ← the installed config ← `--set`
(JSON-coerced); a config file that is not a JSON object, on either side, is a
clean exit 2 rather than a traceback. `config_renames` is folded into the
installed config **before** the merge, so a retired key's value moves to its
replacement, the new key wins when both exist, and the old name never lingers
looking configured. The launcher reads `DEFAULTS` ← `<stem>.config.json` ←
`config.json`, plus one environment value: the WebUI URL, under the env name
the *binding* declares (`URL_ENV`), so the launcher's source spells no
scheduler env name. The URL is in no default and no recipe holds a credential.
_Verify:_ `tests/unit/test_supervisor_recipe.py` (AC-URC-003, AC-URC-003b,
AC-URC-004).
- **SC-urc-4 — The scheduler is a binding, not a dependency — where the seam
is.** The installer and the controller name no scheduler: the
`cron list --all` parser, the `create|edit|pause|resume` argv, the
profile-home layout, the profile marker and the session calls live in one
module, and the two callers reach them only through the binding they are
handed. The launcher names no scheduler either, with one honest exception: it
resolves the binding module by the documented filename
(`<binding>_binding.py`) and reads the single URL env name from it (`URL_ENV`)
rather than spelling it. That module's docstring is the interface — fifteen
names plus the filename convention. A second scheduler is a second module of
that shape plus one registry entry. The suite runs the whole install against a
binding that is not the shipped one, loads the real launcher's helper
resolution unpatched, and asserts that `install.py`, `control.py` and
`launch.py` carry no scheduler command text, env name or `--hermes-*` alias
(the binding module is exempt — it is the scheduler). _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-024, AC-URC-024b).
- **SC-urc-5 — The root never comes from `$HOME`, and a non-profile is
refused.** The order is `--root` → the binding's explicit root env → its
scope-home env (whose root is the parent's parent when the parent is the
profiles directory) → the current directory; the source is printed. A
directory without the scheduler's profile marker exits 2 before anything is
copied or called — the duplicate-job incident rebuilt as a test. _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-006, AC-URC-007).
- **SC-urc-6 — Every fire is gated by a ladder that fails closed.** Order is
contract: `--dry-run` returns before the first guard; outside `[start, end)`
in the configured zone (wrap and equal-hours defined) the tick ends with no
output and no log line; an unreadable session API logs
`api-error … not firing blind`; a session still working — read from **every**
session, with an idle floor, so a worker between tool calls is not mistaken
for idle — skips; a live round marker skips; the process scan is a second,
independent signal. The marker is written by `autoresearch run` at start and
removed at exit; a marker whose pid is gone is a finished run, a marker that
cannot be read blocks, and a marker whose pid is alive blocks for as long as
that pid lives — there is no unblocking timeout, because a reused pid can
belong to an unrelated long-lived process and a wrong fire writes twice into
one ledger. The reason names the age, and the recovery is manual and
documented: `ps -p <pid>` to prove it is not a run, then
`rm <state_dir>/round.marker`. The process pattern matches the argv actually
used — flags may sit between the program and `run` — behind a deliberately
broad prefilter, and the suite pins that the naive literal guard **fails** on
that shape. _Verify:_ `tests/unit/test_supervisor_recipe.py` (AC-URC-014,
AC-URC-015, AC-URC-016, AC-URC-017, AC-URC-021, AC-URC-022, AC-URC-022b,
AC-URC-022c, AC-URC-022d, AC-URC-022e, AC-URC-023).
- **SC-urc-7 — The prompt is rendered from repo state and names only real
commands.** The overnight prompt carries the active objective's first priced
leg (read from `autoresearch/objective/registry.json`), the engine's own
`status` and `doctor` output, its `--help` catalog, the last close record's
verdict, the budget, and the adopter-supplied charter. Every probe degrades to
a labelled string and never raises; no `${` survives; the charter falls back
to a clearly marked `[ADOPTER-SUPPLIED …]` block. Every engine verb the prompt
names exists in the CLI's parser or the wrapper's `profile` dispatch, with an
invented verb as the negative control. _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-019, AC-URC-019b, AC-URC-020),
`tests/integration/test_supervisor_install.py` (AC-URC-202).
- **SC-urc-8 — Install is not resume; the operator loop shares one lookup.**
`status` is read-only; `pause` / `resume` issue the scheduler's command, then
**re-read** and exit 1 when the state did not move; no job or two jobs exit 2
with the ids and a remedy. An install never pauses or resumes, so a paused job
stays paused across a reinstall, and the runbook order — dry-run → install →
status → render → resume — is the only place the state changes. _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-011, AC-URC-013, AC-URC-013b),
`tests/integration/test_supervisor_install.py` (AC-URC-203).
- **SC-urc-9 — No shell, and no unbounded child.** The new modules never pass
`shell=True` and every `subprocess.run` carries a timeout; the check parses
the AST and is proved non-vacuous by a negative control. _Verify:_
`tests/unit/test_supervisor_recipe.py` (AC-URC-018).

## Test Mapping

| AC | Test | Tier | What it pins |
|----|------|------|--------------|
| AC-URC-001 / 001b | `test_shipped_recipe_validates_and_documents_its_keys`, `test_schema_refuses_a_recipe_that_would_install_nothing` | unit | schema covers every shipped key; each defect reported |
| AC-URC-002 | `test_install_copies_byte_equal_files` | unit | `copy2`, byte equality |
| AC-URC-003 | `test_config_merge_order_keeps_operator_edits_and_set_wins` | unit | example ← installed ← `--set` |
| AC-URC-003b | `test_malformed_configs_are_refused_cleanly` | unit | non-object / unparseable config → exit 2, no traceback |
| AC-URC-004 | `test_config_renames_fold_before_the_merge` | unit | retired key moves, new key wins |
| AC-URC-005 | `test_dry_run_writes_nothing_and_issues_only_reads` | unit | tree snapshot + argv log |
| AC-URC-006 | `test_root_resolution_order_never_reads_home` | unit | flag → env → derived env → cwd |
| AC-URC-007 | `test_root_gate_refuses_a_directory_that_is_not_a_profile` | unit | exit 2, nothing written, nothing called |
| AC-URC-008 | `test_second_install_edits_the_same_job` | unit | one job, second command is an edit |
| AC-URC-009 | `test_duplicate_job_is_refused_with_both_ids` | unit | exit 2 naming both, no copy |
| AC-URC-009b | `test_state_hint_with_no_listed_job_refuses_to_create` | unit | hint + empty listing → exit 2, naming the stored id, nothing created |
| AC-URC-010 | `test_unreadable_listing_is_never_an_empty_match_list` | unit | exit 2, create not guessed |
| AC-URC-011 | `test_install_never_resumes_a_paused_job` | unit | state unchanged, no pause/resume |
| AC-URC-012 | `test_post_install_verify_fails_when_the_listing_shows_two` | unit | post-install verification |
| AC-URC-013 / 013b | `test_control_status_pause_resume`, `test_control_fails_closed_…` | unit | re-read after mutate; fail closed |
| AC-URC-014 | `test_window_boundaries_and_zones` | unit | `[start, end)`, wrap, zone |
| AC-URC-015 | `test_busy_session_reads_every_session_and_the_idle_floor` | unit | all sessions + idle floor |
| AC-URC-016 | `test_marker_state_fails_closed` | unit | absent/live/dead/unreadable |
| AC-URC-017 | `test_round_marker_matches_the_argv_shape_actually_used` | unit | broad prefilter, specific pattern, naive-literal red-proof |
| AC-URC-018 | `test_no_shell_true_and_every_child_is_timed` | unit | AST scan + negative control |
| AC-URC-019 / 019b | `test_prompt_renders_the_active_leg_record_and_charter`, `test_prompt_objective_line_degrades_without_raising` | unit | render from state, degrade |
| AC-URC-020 | `test_prompt_names_only_commands_the_engine_has` | unit | catalog membership + invented verb |
| AC-URC-021 | `test_launcher_dry_run_touches_nothing_and_consults_no_guard` | unit | dry-run before every guard |
| AC-URC-022 / b / c / d | `test_launcher_api_error…`, `…outside_the_window…`, `…busy_session_and_live_marker…`, `…fires_once…` | unit | ladder order and the fire |
| AC-URC-022e | `test_launcher_state_write_failure_does_not_fail_the_tick` | unit | fired session survives an unwritable state file (exit 0, logged) |
| AC-URC-023 | `test_engine_run_writes_and_clears_the_round_marker` | unit | marker written during, gone after |
| AC-URC-024 | `test_install_runs_against_a_binding_that_is_not_hermes` | unit | scheduler-agnostic installer |
| AC-URC-024b | `test_launcher_helpers_resolve_from_the_real_repo` | unit | importlib on the real `guards.py` + `hermes_binding.py`, unpatched |
| AC-URC-201 / 201b | `test_install_through_the_script_lands_one_job`, `test_dry_run_through_the_shell_wrapper_writes_nothing` | integration | real child, store, wrapper |
| AC-URC-202 | `test_installed_launcher_renders_from_repo_state` | integration | installed names resolve; prompt from the real repo |
| AC-URC-203 | `test_install_never_resumes_a_paused_job_end_to_end` | integration | paused across a reinstall |

## CI/CD Gate

`unit` runs `tests/unit` (the whole `AC-URC-0NN` set) and `integration` runs
`tests/integration` (`AC-URC-2NN`); both are in `bash tests/run.sh`, so a PR
that reddens either cannot merge. The tier split is the repo's: the unit tier
drives the installer in-process against a fake scheduler CLI, the integration
tier runs the real `install.py`, `install.sh` and the *installed* launcher as
children. No test reaches a real scheduler, a real profile or the network — the
fake's store is JSON under `tmp_path`, and the launcher's session calls are
stubbed. `act -j unit` and `act -j integration` are the pre-PR commands
(AGENTS.md §6).

## Assumptions

- `[ASSUMPTION]` **The interval token is portable; a cron expression is not.**
The downstream measurement: with no `croniter` on the py3.12 interpreter, a
cron expression stores `next_run_at: null` and errors after the first fire,
while `every 60m` keeps ticking. This repo has measured that on one gateway,
not on every ticker, so the recipe's schedule is an interval and the overnight
window is an in-script pure function — which is also what makes the window
testable at its boundaries. Upstream claim, labelled, not promoted.
- `[ASSUMPTION]` **Hermes cron is the shipped scheduler, and the only one
wired.** The binding interface and the fake-binding test are the evidence that
a second scheduler is additive; no second binding is implemented here. An
adopter reading "generic" must read it as *generic across recipes, plus one
documented binding* — not "works on my harness out of the box".
- `[ASSUMPTION]` **The fired session reaches the engine through its declared
CLI.** The prompt names
`init`/`run`/`status`/`report`/`doctor`/`objective`/`profile`; the guard
ladder assumes the session honours them. A session that runs something else is
outside what a launcher can enforce — the record contract (PRD 22) is what
makes it visible afterwards.
- `[ASSUMPTION]` **The marker's pid is meaningful on the host that reads it.** A
marker read from a shared filesystem by another host would consult a foreign
pid, and the guard then blocks — **indefinitely, by design**: there is no
unblocking timeout, so the safe default costs skipped ticks rather than a
second writer. The skip reason carries the marker's age
(`running for N h (pid reuse? check by hand)`), and the documented recovery is
to prove the pid is not a run (`ps -p <pid>`) and then remove
`<state_dir>/round.marker` by hand. A marker whose pid is gone clears itself.
- **Adopter-supplied, by design:** `charter.md` (the intent paragraph), `repo`,
`target_profile`, `timezone`, the window and the budget in
`config.example.json`, and `webui_url` (configuration, or the env var the
binding names in `URL_ENV`). The launcher marks an absent charter in the
prompt rather than inventing one, and skips with a logged reason when the
configured repo does not carry the guard helpers.

## Confidence

**High** for the installer, the config merge, the root rule, the control loop
and the pure guards: each is a stated rule with a test, and five red-proofs (the
dry-run guard removed, `copy2` replaced by a re-rendered write, the marker guard
forced clear, the control re-read ignored, the merge compared against the
renamed dict instead of the config on disk) each turn the suite red. **Medium**
for the end-to-end fire: the ladder is proved against a stubbed session API and
a fake scheduler, and the marker against the real engine, but no live scheduler
has fired this recipe in this repo yet — which is why the stage-6 record is
`pending` and this PRD does not claim `works`. **Low** for any claim about a
scheduler this repo has not bound.
