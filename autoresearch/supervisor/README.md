# supervisor — the unattended loop as a tracked, installable recipe

A schedule that starts research is **code**. This directory holds the loop's job
definition, the exact files the scheduler runs and the knobs they read, so the layer
that wakes the engine is diffed, reviewed and tested like everything else — instead of
living only inside a harness profile, where it has no history and no second machine.

```
autoresearch/supervisor/
├── install.py            one generic installer, one idempotent install
├── control.py            status | pause | resume over the same job lookup
├── schema.py             recipe.json's fields and validator
├── guards.py             the guard ladder, as pure functions
├── hermes_binding.py     the one scheduler binding this repo ships
└── overnight/            this repo's recipe: the engine, one bounded run a night
    ├── recipe.json       name, schedule, installed script, files map
    ├── config.example.json   every operator knob, no secrets
    ├── install.sh        8 lines: exec ../install.py "$(dirname "$0")" "$@"
    ├── launch.py         render from repo state, run the guard ladder, fire one session
    ├── prompt.tmpl.txt   the brief the fired session reads
    └── charter.md        ADOPTER-SUPPLIED: the one paragraph a recipe cannot write
```

The installed copy under `<profile>/scripts/` is **build output**. Edit the recipe
here, reinstall, never the other way round: `shutil.copy2` keeps the pair byte-equal
and a test proves it with `cmp`.

## Install

```bash
# 1. plan — prints every copy, config write and command; writes nothing
bash autoresearch/supervisor/overnight/install.sh --profile default --root /srv/agent-harness --dry-run

# 2. install (create or edit — never a second job)
bash autoresearch/supervisor/overnight/install.sh --profile default --root /srv/agent-harness \
  --set repo="$(pwd)"

# 3. read the job back, then render the prompt it would send
python3 autoresearch/supervisor/control.py status autoresearch/supervisor/overnight --profile default --root /srv/agent-harness
python3 <profile>/scripts/autoresearch-overnight-launch.py --dry-run

# 4. resume only when you mean to — installing never unpauses a paused job
python3 autoresearch/supervisor/control.py resume autoresearch/supervisor/overnight --profile default --root /srv/agent-harness
```

Flags: `--profile` (default `default`), `--root` / `--scheduler-root`, `--bin`, `--binding`
(default `hermes`), `--set KEY=VALUE` (repeatable, JSON-coerced), `--dry-run`.

**The root never comes from `$HOME`.** Resolution is `--root` → the binding's root env
(`HERMES_ROOT`) → its scope-home env (`HERMES_HOME`, whose root is its parent's parent
when the parent is `profiles`) → the current directory; the source is printed, and a
directory without the scheduler's profile marker is refused (exit 2) before anything is
copied or called. Inside a scheduler-spawned process `$HOME` is a per-profile home: a
plausible empty tree there reads as "no jobs", and that is exactly how a duplicate job
is minted.

## Config

`install.py` writes `<script stem>.config.json` beside the installed script, merged
`config.example.json` ← the installed config ← `--set`. The stem rule lets several
recipes share one `scripts/` directory. `config_renames` in `recipe.json` folds a
retired key into its replacement **before** the merge, so an operator's value moves —
the new key always wins and the old name never lingers.

The run reads its values in the same shape: `DEFAULTS` ← `<launch stem>.config.json` ←
`config.json`, plus one environment value — the WebUI URL, under the env name the binding
declares in `URL_ENV` (the name lives only in the binding module; set it there or set
`webui_url` in the config). The URL is not in the launcher's defaults and no recipe holds
a credential.

## The guard ladder

Every guard answers one question — may this tick start a session? — and every guard
fails **closed**: skip a tick rather than write twice.

1. `--dry-run` returns before the first guard.
2. Outside `[start, end)` in the configured zone → exit 0, no output, no log line.
3. An unreadable session API → `api-error … not firing blind`, exit 0.
4. A session still working (streaming, or touched inside `idle_minutes`) → skip. Every
   session is read, not only the last one fired: a worker between tool calls reports
   `agent_running=false`.
5. A **live-round marker** → skip. `autoresearch run` writes `<state_dir>/round.marker`
   (or `$AUTORESEARCH_ROUND_MARKER`) at start and removes it at exit; a marker whose pid
   is gone is a finished run and does not block, a marker that cannot be read blocks.
   The process scan (`guards.live_process`) is the second, independent signal, matched
   against the argv shape actually used — global flags sit between the program and
   `run`, so a literal `"autoresearch run"` misses a live round.

   **A marker with a live pid blocks indefinitely — that is the design.** There is no
   timeout that unblocks: a stale *pid* is the only case that clears itself, and a
   reused pid can belong to an unrelated long-lived process, so the guard keeps skipping
   and names the age in the reason (`running for N h (pid reuse? check by hand)`).
   Recovery, when the reason says that, is two commands: prove the pid is not a run
   (`ps -p <pid> -o pid,args`) and then remove the marker —
   `rm <state_dir>/round.marker`. Skipping costs one interval; a wrong fire writes
   twice into one ledger, which is why the manual step is the only way out.

## What is adopter-supplied

The recipe is a template in exactly three places, marked in the files themselves:

- `overnight/charter.md` — the intent paragraph. The launcher substitutes a labelled
  `[ADOPTER-SUPPLIED …]` placeholder when the file is absent, so a fresh install says
  so in the prompt instead of pretending it has a charter.
- `config.example.json` — `repo`, `target_profile`, `timezone`, the window and the
  budget. `repo` defaults to `.`, which is the profile home; the launcher's helper load
  needs `autoresearch/supervisor/guards.py` and `<binding>_binding.py` in the configured
  repo and skips with a reason when either file is missing — so a misconfigured install
  logs a skip rather than starting an unguarded session at nothing. It checks those two
  files exist; it does not prove the repo is a checkout of this harness.
- `webui_url` — a URL, never a credential.

Nothing else is a hole: the prompt's state lines, the engine commands and the charter
section are all rendered at fire time from the repo and the config.

## The scheduler binding

`install.py` and `control.py` name no scheduler beyond `--binding`; the launcher names
`autoresearch/supervisor/`'s guard helpers and asks its binding for the one URL env name
it reads (`URL_ENV`) — it carries that name nowhere itself. Everything else
scheduler-shaped lives in `hermes_binding.py`: the `cron list --all` parser, the
`create|edit|pause|resume` argv, where a profile home sits, which file proves a
directory is a profile, and the loopback call that starts a session. Its module
docstring is the **interface**: fifteen names — `NAME`, `ROOT_ENV`, `BIN_ENV`,
`PROFILE_ENV`, `URL_ENV`, `root_from_home`, `profile_home`, `is_profile`, `cli_env`,
`list_jobs`, `job_argv`, `state_argv`, `sessions`, `fire`, `read_hint` — plus a
sixteenth requirement the launcher enforces by filename: the module must be
`<NAME>_binding.py`. A second scheduler is that module plus one `BINDINGS` entry in
`install.py`; no caller changes.

This repository ships exactly one binding. `[ASSUMPTION]` an adopter's ticker parses
the interval token `every 60m`; a cron expression needs `croniter`, which some tickers
lack — the job then stores `next_run_at: null` and errors after the first fire. The
window lives in `launch.py` for that reason, where it is a tested pure function.

## Add a recipe

1. `mkdir autoresearch/supervisor/<recipe>/`, copy `overnight/recipe.json` and change
   `name`, `schedule`, `script`, `files`, `note`.
2. Add `config.example.json`, `install.sh` (the same 8 lines) and the files `files` names.
3. `bash autoresearch/supervisor/<recipe>/install.sh --dry-run` — the schema refuses a
   missing key, a missing file, a `script` that is not in `files`, or a non-bare
   installed filename.
4. Install, `status`, and only then `resume`.
