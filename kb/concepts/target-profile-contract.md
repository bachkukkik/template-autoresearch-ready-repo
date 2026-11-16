---
title: Target-Profile Contract
created: 2026-11-16
updated: 2026-11-16
type: concept
tags: [autoresearch, architecture, data-model]
sources: [raw/articles/2026-11-16-target-profile-contract.md]
confidence: medium
---

# Target-Profile Contract

A harness that scores another repository has to answer one question before any round
runs: **which paths belong to the harness and which to the repository it measures?**
Get it wrong and a round executes the measured repo's own evaluator and writes its
state — the measured becomes the measurer, and every number after that is a reading the
subject produced about itself.

The contract answers it with one JSON profile whose keys are **typed by relativity**,
plus a resolution order and a refusal rule that run before any state is read.

## The split

| Half | Keys | Resolves against |
|------|------|------------------|
| harness-owned | `engine`, `referee`, `guard_command`, `runs_dir` | the repo that ships the profile |
| target-relative | `program`, `scopes`, `protected`, `docker_free_tier`, `e2e_dir`, `context_dir`, `dockerfile`, `fresh_script`, `guard_steps`, `fresh_instruction`, `arena_test_files` | the checkout a round names |

`program` is target-relative deliberately: it is the seat contract *of the measured
checkout*, and the engine refuses a protected path outside the worktree it protects. A
harness-owned `program` would either be the wrong instructions or an unprotectable
path. `guard_command` is a template — `{referee}` is the harness evaluator, `{target}`
the measured checkout — so one command string serves every target. ^[raw/articles/2026-11-16-target-profile-contract.md]

The rule is stated **in the profile itself** (`$comment`), not only in a README: a
reader who opens the file cannot mis-guess which side a key is on, and a reviewer can
diff the claim against the key list.

## Resolution: pure, ordered, loud

- **Order** — flag → `$AUTORESEARCH_TARGET_REPO` → `cwd`. Resolution is pure: no git,
  no state, so the order is testable without a repository.
- **Names, not paths** — a target is a declared profile
  (`autoresearch/targets/<name>.json`). A traversal-shaped name, an absolute path or a
  `*.json` filename is refused with the reason; an undeclared name is refused **naming
  what is declared**.
- **Refusal by name** — a profile that is unreadable, is not an object, or is missing
  a key is refused before a round starts, listing the path and every missing key. The
  downstream code carries two key lists with different lengths and two exception types
  for the same refusal; a port should carry one schema and one validator.
- **Per-key reasons, not one exception** — a target-relative key that is absolute, or
  contains `..`, or escapes the checkout is returned as a reason beside every other
  bad key, so a caller can report the whole misdescription once.

## The evaluator guard: a diff bound is not a write bound

Moving the evaluator out of the worktree bounds what a candidate's **diff** can reach.
It does not stop a **write**: a seat runs as the same OS user and can open
`.../league/arena.py` by absolute path, and the worktree diff never sees it. That is
[[reward-hacking-countermeasures]] path 1 in practice.

The contract hashes the evaluator surface at both ends of a round — the referee, the
profile, the runner and every engine module — and on any difference **voids the round**
with the reason, charging both competitors the event that already means "a protected
file moved". Nothing is settled, and the tampered files stay as evidence. Deleting an
evaluator is a change like any other: a missing file hashes to `null`, never to an
omission.

**The limit, stated rather than hidden:** two hash reads cannot see a write-then-restore.
The honest close is a read-only mount or a separate user; until then the record must say
which reads it took. See [[evaluator-legitimacy]] and [[verify-guard-contract]].

## State is the harness's, and it migrates by one command

Rounds write into the harness's runs directory, never into the measured checkout; the
directory is ignored except a `.gitkeep`. The engine is told where that is: `init` (and
`run`/`status`/`report`) take `--state-dir PATH`, the profile's plan passes
`--state-dir <runs_dir>/state`, and the absolute path is recorded in `run.json` for every
later command. Without the flag the engine keeps `<repo>/.autoresearch`, so an existing
ledger replays unchanged. Moving an older season's record in is a
**copy command**: `--dry-run` writes nothing, runtime residue (`*.lock`, `__pycache__`)
is never carried, and an existing state file refuses without `--force`. Recording
`status` against the wrong tree — because the state lived in the subject — was a live
defect, not a hypothetical. ^[raw/articles/2026-11-16-target-profile-contract.md]

## Four failures the contract answers

1. **A profile pointing at the target's evaluator** — rounds ran the measured repo's
   referee and wrote its state; deleting that arena from the target would have broken
   every round.
2. **The evaluator outside the protected list** — `--protect` only accepts paths inside
   the worktree, so moving the evaluator out removed the only check on it; the hash
   guard replaces it.
3. **A coverage claim that was not re-run** — "one test carries 43 cases" carried the
   happy path. A mapping is a claim to be re-run, not restated.
4. **A key naming the subject's artifacts went stale** — when the target deleted its
   test files, the honest value was empty. A key present-but-empty (`[]`) is information;
   a deleted key is indistinguishable from a typo, so it is refused by name.

Failure 4 is the general lesson for any schema in this domain: **ship the empty value**.

## In this repo

PRD 22 ports the contract only — `autoresearch/target/` (`target.py`, `guard.py`,
`cli.py`, `import_runs.py`), the declared profiles under `autoresearch/targets/`
(`example.json`) and `autoresearch profile <name> [--repo PATH] [--json]`, a dry command
that prints the resolved engine plan. The tournament itself (a 4,980-line arena, the
captain economy, media) stays downstream. The template adds two declarative keys the
downstream profile did not need — `metric_name` and `direction` — because its engine
takes one metric per run rather than a priced leg table; the divergence is stated in the
PRD.

## Related

- [[reward-hacking-countermeasures]] — why an evaluator outside the diff still needs a hash.
- [[evaluator-legitimacy]] — the structural integrity problem this contract operates inside.
- [[harness-portability]] — the same relativity idea, applied to instruction files.
- [[verify-guard-contract]] — the measurement interface a profile points at.
- [[run-record-contract]] — the record a round leaves once state is the harness's.
