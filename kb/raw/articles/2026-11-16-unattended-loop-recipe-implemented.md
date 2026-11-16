---
source_url: https://github.com/bachkukkik/template-autoresearch-ready-repo
ingested: 2026-11-16
sha256: e4924cc19ef48893454568f9d2db13dd9f2361540ff9b3e168cf6c3874786f59
source_type: code-capture
kind: article
title: "Unattended loop recipe — installer, guard ladder and round marker, implemented (code capture)"
---

# Unattended loop recipe — a code capture of the port

## Provenance

**What.** The generic half of the downstream league's overnight supervisor, read from
the downstream checkout and then re-expressed in this repo: `autoresearch/supervisor/`
— `install.py`, `control.py`, `schema.py`, `guards.py`, `hermes_binding.py`,
`README.md` — and the template-owned recipe `autoresearch/supervisor/overnight/`
(`recipe.json`, `config.example.json`, `install.sh`, `launch.py`, `prompt.tmpl.txt`,
`charter.md`), plus `autoresearch/engine/autoresearch/marker.py` and the one line in
`cli.py` that holds it. The `sha256` above is this body's digest, per the KB convention; the captured files
concatenated in that order hash to `f284c6f38715`.

**What it is not.** The downstream league's prompt template, its verbatim charter, its
season/referee/captain vocabulary, its lineage probes and its `DEFAULTS` are not
carried. The recipe here is `overnight-loop`: one metric per run, one record, one
charter paragraph the adopter writes.

**Labels.** `[M]` read in the code at the path cited; `[S]` stated by the downstream PR
body or its own record; `[I]` inference. Downstream line references are to the files
the distillation read on 2026-11-16.

**Why this repo cares.** Two PRDs promise an overnight run and the engine ships the
budget to survive one; nothing starts it. This capture is the mechanism, not the
argument for it.

## The recipe, and what makes it a recipe

A directory that a scheduler can be pointed at, carrying its own job definition
`[M]` (`overnight/recipe.json`): `name`, `schedule`, `script` (the *installed* name),
`no_agent`, `deliver`, `timezone`, a `files` map of source → installed name,
`config_renames`, and a `note` that records why the schedule is an interval `[M]`.

The schema is a closed field list with a validator that returns every problem at once
`[M]` (`schema.py`): a missing required key, a `files` value that is not a bare
filename, a `script` that is not one of the installed files, a listed source that is
absent on disk, a `config_renames` that is not an old→new string map. The point is
that an adopter's second recipe is validated before it can install anything.

`install.sh` is eight lines and `exec`s `../install.py "$(dirname "$0")" "$@"` `[M]` —
the wrapper pattern, and the reason a recipe directory is self-describing.

## The install, as four rules

1. **The copy is the bytes.** `shutil.copy2` per file pair; a test compares
   `read_bytes()`, because a re-rendered copy drifts silently `[M]` (`install.py`).
2. **The config merges in one order.** `config.example.json` ← the installed config ←
   `--set` (JSON-coerced), and `config_renames` is folded into the installed config
   **before** the merge `[M]` (`merge_config`, `apply_renames`). Folding first is what
   lets an operator's value move to the new key instead of being replaced by the
   example's default; the old name is dropped either way so a stale key cannot look
   configured `[M]`.
3. **The listing decides create-versus-edit.** One match → edit that id; none → create;
   two → exit 2 naming both; an unreadable listing → exit 2 `[M]` (`jobs_named`). The
   state file (`cron/jobs.json` in the shipped binding) is a warning only `[M]`
   (`read_hint`), because a state file says nothing when the root is wrong `[S]`
   (downstream PR #10).
4. **`--dry-run` returns before the writes.** It prints every copy, the config write
   and the command, and performs none; it does read the listing, because the plan must
   say create or edit `[M]` (`run`). A tree snapshot in the suite proves the claim.

## Root resolution, and the gate

`--root` → the binding's explicit root env → its scope-home env → the current
directory, with the source printed `[M]` (`resolve_root`). `$HOME` is never read: in a
scheduler-spawned process it is a per-profile home, and that is the exact shape of the
downstream duplicate-job incident `[S]` (PR #10). A scope-home value is treated as a
profile home when its parent is the profiles directory, so its root is the parent's
parent `[M]`. A directory without the binding's profile marker exits 2 before a single
copy or child call `[M]`.

## The guard ladder, in order

`--dry-run` (before every guard) → window → api-error → busy session → live marker →
process scan `[M]` (`overnight/launch.py`, `guards.py`).

- **Window**: `[start, end)` local hours in a named zone, wrap-around supported,
  `start == end` a full day, an unknown zone raising rather than falling back to UTC
  `[M]` (`in_window`). Out of window is silent: no output and no log line `[M]`.
- **api-error**: an unreadable session API logs `api-error <Type> — not firing blind`
  and exits 0 `[M]`. A dead API must never read as "idle".
- **Busy session**: every listed session, not the last one fired, with an idle floor —
  a worker between LLM turns reports `agent_running=false`, which is how a duplicate
  session was fired into a live one downstream `[S]`.
- **Marker**: the run writes `<state_dir>/round.marker` (or
  `$AUTORESEARCH_ROUND_MARKER`) at start and removes it at exit `[M]` (`marker.py`,
  `cli.cmd_run`). The reader is broad-then-specific: does a marker exist, then is its
  pid alive `[M]` (`marker_state`). A dead pid is a finished run and does not block; a
  marker that cannot be parsed blocks, because a guard that cannot read its signal must
  not read it as clear `[M]`.
- **Process scan**: a second, independent signal. `pgrep` is only a prefilter; the
  pattern allows tokens between the program and `run`, because global flags sit there —
  the literal `"arena.py round"` missed every flagged round downstream `[S]` (PR #40).
  The suite pins that the naive literal fails on the real argv shape `[M]`.

## The prompt, rendered at fire time

Placeholders are filled from repo state, never from constants `[M]`
(`gather_context`): the active objective's first priced leg from
`autoresearch/objective/registry.json`, the engine's own `status` (first eight lines,
with the "no initialised run" case named), `doctor`, the `--help` catalog, and the last
close record's verdict with its first reading `[M]`. A dead probe is a labelled string
`(unavailable — …)` and never raises `[M]`; a missing charter renders a marked
`[ADOPTER-SUPPLIED …]` block rather than a fabricated intent `[M]`.

The prompt names only engine commands that exist: `init`, `run`, `status`, `report`,
`doctor`, `objective`, `profile` (`profile` is the wrapper's dispatch, not a parser
subcommand) `[M]`, and the test derives the set from the CLI parser so an invented verb
fails `[M]`.

## Install is not resume

`status` is read-only; `pause` and `resume` run the scheduler's command and then
re-list, exiting 1 when the state did not move `[M]` (`control.set_state`). Zero or two
matching jobs exit 2 with the ids `[M]`. The installer never issues pause or resume, so
a paused job stays paused across a reinstall `[M]` — the downstream fact that `cron
edit` cannot unpause `[S]` turned into a property instead of a workaround.

## The binding, and what "generic" means here

Everything scheduler-shaped is in `hermes_binding.py` `[M]`: the `cron list --all`
text parser, the `create|edit|pause|resume` argv, `profile_home` / `is_profile`, the
root-pinned child env, and the loopback session calls. Its docstring lists the fourteen
names a second binding must implement `[M]`. `install.py` carries the names `hermes`
once, in a registry entry `[M]`, and the suite runs a whole install against a
non-Hermes binding to prove it `[M]`.

That is the honest reading of "generic": generic across **recipes**, with one shipped
binding and a documented interface for a second. `[I]` A second scheduler that lacks a
text listing would implement `list_jobs` against its own state and pass the same
suite; a scheduler whose sessions cannot be listed cannot satisfy the busy guard and
must say so rather than degrade to a marker-only ladder.
