---
source_url: https://github.com/bachkukkik/template-autoresearch-ready-repo
ingested: 2026-11-16
sha256: a7bf7b56e24655c400bbb457b7abe6bceeb560769f7de056fdaa0ffa19d5d9dd
source_type: correction
kind: article
title: "Process-scan doctrine — correcting the downstream regex and the dry-run-as-in-flight rule"
---

# Process-scan doctrine — correction to the 2026-11-15 distillation

## Provenance

**What.** A correction to one sentence of
`raw/articles/2026-11-15-downstream-frontier-distillation.md` (guard ladder, item 5). That
capture recorded the downstream fork's own `ROUND_MARKER` regex and its
"dry-run counts as in-flight" rule as the doctrine. Both are one harness's spelling of the
*lesson*, not the lesson, and this repo implemented a different pattern — so a layer-2 page
citing the old sentence would describe code that does not exist here.

**Why the file is not edited.** `kb/raw/` is add-only (funnel rule 3). The earlier capture
stays as it was read on 2026-11-15; this one records what supersedes it.

## What the earlier capture said

> (`ROUND_MARKER = (?:arena\.py|registry\.py\s+league)\b.*\sround(?:\s|$)` behind a broad
> `pgrep` prefilter, dry-run counts as in-flight) (#40)

## What this repo implements

`autoresearch/supervisor/guards.py`:

- `ROUND_PATTERN = (?:^|[\s/])autoresearch(?:\.py)?\b(?:\s+[^\s]+)*\s+run(?:\s|$)` — the
  program is `autoresearch` (or `autoresearch.py`), the subcommand is `run`, and the `*`
  between them is what lets global flags sit there.
- `ROUND_PREFILTER = "autoresearch"` — `pgrep -af` is a prefilter that decides nothing.
- A **dry run is not a round in flight.** `run --dry-run` returns immediately and leaves no
  marker behind, so neither the marker guard nor the scan should treat it as a writer; the
  downstream rule that counted it as in-flight is a different policy, not a safer one.

The marker remains the first detached-run signal (`<state_dir>/round.marker`, written by
`marker.py` inside `cli.cmd_run`); the scan is the second, independent one.

## How it is verified

`tests/unit/test_supervisor_recipe.py` — `AC-URC-017` asserts `process_in_flight` matches the
python-module argv and the flagged argv, returns None for `status` / `objective resolve` /
an editor / a `doctor` call, and that the naive literal `re.compile(r"autoresearch run")`
**fails** on the flagged shape. That red-proof is the part of the downstream lesson that
travels: prove the naive form fails before shipping the clever one.

## Scope

`[M]` measured in this repo (source read and test run); `[S]` self-reported by the
downstream fork. The lesson is harness-neutral; the regex, the program name and the
dry-run policy are not.

## Also corrected — the binding interface count

The same day's code capture (`raw/articles/2026-11-16-unattended-loop-recipe-implemented.md`)
says the binding docstring "lists the fourteen names a second binding must implement". The
implemented interface is **fifteen** names (`NAME`, `ROOT_ENV`, `BIN_ENV`, `PROFILE_ENV`,
`URL_ENV`, `root_from_home`, `profile_home`, `is_profile`, `cli_env`, `list_jobs`,
`job_argv`, `state_argv`, `sessions`, `fire`, `read_hint`) plus one requirement that is a
filename rather than a name: the launcher resolves the module as
`autoresearch/supervisor/<NAME>_binding.py`. `URL_ENV` exists so the launcher reads the
WebUI URL's variable name from its binding instead of spelling a scheduler's env name; the
earlier count was off by one because `root_from_home` was documented in prose only.
