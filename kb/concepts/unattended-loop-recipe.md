---
title: Unattended Loop Recipe
created: 2026-11-15
updated: 2026-11-16
type: concept
tags: [autoresearch, agentic, ops]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md, raw/articles/2026-11-16-unattended-loop-recipe-implemented.md, raw/articles/2026-11-16-process-scan-correction.md]
confidence: medium
---

# Unattended Loop Recipe

A schedule that starts research is **code**, and code that exists only inside a harness
profile — a launcher in `~/.hermes/profiles/<profile>/scripts/`, a prompt template, a charter —
is untested, unreviewable and unrecoverable on a second machine. The downstream fork learned
this the hard way: its overnight supervisor had profile, target repo, WebUI URL and UTC
offset hardcoded *in the file the scheduler executes*, so it had no diff, no review, no
test.

> **Evidence and scope.** `[S]` marks a figure **self-reported by the downstream repo** (PR
> body or committed record). The scheduler names below are **one harness's** — Hermes cron
> (jobs, `cron list --all`, `cron edit`, paused jobs) — because that is the harness the fork
> ran. Substitute your own scheduler's equivalents: the recipe shape, the guard ladder and
> the root rule are harness-neutral; the command spelling is not.

## The recipe shape

Illustrative layout — the field list is what one recipe's `recipe.json` carried, not a schema:

```
supervisor/<recipe>/
├── recipe.json           # name, schedule, script, no_agent, deliver, timezone,
│                         # files[], config_renames{}, note
├── config.example.json   # every operator knob, no secrets
├── install.sh            # 8 lines: exec ../install.py "$(dirname "$0")" "$@"
└── <the files it names>  # launcher, prompt template, charter
```

One **generic idempotent installer** serves every recipe: `copy2` so the installed copy is
byte-equal (proved with `cmp`, not assumed), a config merge with `config_renames` applied
*before* the merge so a retired key moves instead of being replaced, create-or-edit decided by
the scheduler's own listing, and `--dry-run` that renders the plan and returns **before any
guard**. Values resolve `DEFAULTS ← <script stem>.config.json ← config.json ← env`; the stem
rule lets N recipes share one `scripts/` dir.

The schema is closed and reported in one pass: a missing required key, a `files` value that is
not a bare filename, a `script` that is not one of the installed files, a listed source that is
absent, a `config_renames` that is not an old→new string map. A recipe that would install
nothing is refused before anything is copied.

## Root resolution — never `$HOME`

Inside a harness-spawned process `$HOME` is a *per-profile* home, so a plausible empty tree
passes an existence check and reads as "no jobs". The measured incident `[S]`: an install
without an explicit root resolved `~/.hermes` to `.../profiles/<profile>/home/.hermes`, whose
`profiles/<profile>/` existed but whose `cron/jobs.json` did not — so `cron create` ran
beside a live job and minted a duplicate that kept firing.

Resolve `--flag → explicit env → derived env → the account home from the password database`,
**print the source**, and refuse a scope dir without its own `config.yaml` (exit 2, nothing
copied, nothing called). Then: the scheduler's **listing** decides create-vs-edit (one match →
edit, none → create, two → exit 2 naming both, unreadable → exit 2), the state file is a hint
only, the resolved root is pinned into every child env, and the listing is re-read after any
mutation — a command that exits 0 without changing state is a failure.

## Guard ladder — every guard fails closed

Skip a tick rather than write twice, in this order:

1. `--dry-run` returns before every guard (it starts nothing, so it can duplicate nothing).
2. Outside `[start, end)` in the configured **zone** → exit 0, no output, no log line. Wrap
   (`22 → 6`) and equal hours are defined, and an unknown zone raises instead of falling back
   to UTC: a window that silently moves fires at the wrong hour.
3. An unreadable session API → log `api-error … not firing blind`, exit 0.
4. **Session liveness** — a streaming or recently-touched session of the *target* profile
   blocks. Check **all** sessions plus an idle floor: a worker between tool calls reports
   `agent_running=false`, so checking only the last recorded session id fires a duplicate
   session into a live one.
5. **Live-run marker** — the run writes it, the guard reads it, and this is the first
   detached-run signal. A dedicated marker beats a process scan on every axis: the process may
   be detached and invisible to the session API, its argv may carry flags the pattern did not
   anticipate, and `pgrep` may be absent. The reader is **broad-then-specific**: does a marker
   exist at all, then is its pid alive? A pid that is gone is a finished run and does not
   block; a marker that cannot be parsed blocks, because a guard that cannot read its signal
   must not read it as clear.
6. **Process scan** — a second, independent signal, never the first. `pgrep -af autoresearch`
   is a prefilter only; the pattern that decides must match the **argv shape actually
   used**, because global flags sit between the program and `run`. This repo's pattern is
   `ROUND_PATTERN = (?:^|[\s/])autoresearch(?:\.py)?\b(?:\s+[^\s]+)*\s+run(?:\s|$)`, and a
   **dry run is not a round in flight**: it returns at once and leaves no marker, so
   nothing counts it. The naive literal `pgrep -af "autoresearch run"` still fails on a
   flagged argv — that was the downstream failure `[S]` (PR #40), and a test pins the
   literal's failure before the clever pattern ships.

   Downstream's own spelling (`arena\.py|registry\.py\s+league`, with `--dry-run` counted
   as in flight) is one harness's, not the doctrine.
   ^[raw/articles/2026-11-16-process-scan-correction.md]

The doctrine that survives the port: never let a scan-first guard be the only bar, and prove the
naive form fails *before* shipping the clever one. A test that pins "the literal pattern does not
match this argv" is the red-proof; without it the guard can only be reviewed, not known.

## Prompt rendered at fire time

Render from tracked repo state, never from a template that hardcodes layout: newest record on
the main line (fallback labelled), the state line from **one declared command** (argv, timeout,
line cap), lineage from tracked JSON. Every probe degrades to a labelled string
(`(unavailable — <why>)`) and never raises; no `${` may survive; every command the prompt names
must exist in the command catalog, with a negative control using an invented verb. A prompt
that names a repo the work has left sends a session to the wrong place; a stale prompt is
worse than none.

## Schedule and operations

- **Interval tick + in-script window** beats a cron expression the ticker may not parse (no
  `croniter` on py3.12 → `next_run_at` null, errors after the first fire), and the window
  stays testable as a pure function at its boundaries.
- **Install is not resume.** Runbook order: `install --dry-run → install → status → render →
  resume`; a job is found by recipe **name**, never a remembered id; `status` is read-only;
  `pause`/`resume` re-list and exit 1 if the state did not move.
- **Say `partial` until it has fired live.** The recipe's own record flipped to `works` only
  on evidence `[S]`: installed files byte-identical, three idle ticks firing at 18:12 / 20:14
  / 22:16 UTC, and a fourth firing nothing because a session was still live. This is the
  stage-6 habit of the template: a claim with no run behind it is not a claim.

## In this repo

Two PRDs promise overnight runs; the scheduler available to the service is in-process only, so
the recipe is the missing half. The stop conditions a fired run must respect are on
[[loop-stop-conditions]]; the guards are only as good as the session/process facts they read,
which is a [[harness-portability]] question; the invoked agent entry point is
[[headless-harness-invocation]].

^[raw/articles/2026-11-15-downstream-frontier-distillation.md]

## Implemented in this repo

PRD 21 ships the mechanism, not only the pattern (code capture:
[2026-11-16-unattended-loop-recipe-implemented](../raw/articles/2026-11-16-unattended-loop-recipe-implemented.md)).

| Piece | Home | Rule it carries |
|-------|------|-----------------|
| recipe | `autoresearch/supervisor/overnight/` | job definition + the exact files the scheduler runs + an adopter charter |
| schema | `autoresearch/supervisor/schema.py` | closed field list; every defect in one pass |
| installer | `autoresearch/supervisor/install.py` | `copy2`, merge order, renames first, listing decides, dry run inert |
| operator loop | `autoresearch/supervisor/control.py` | `status` read-only; `pause`/`resume` re-read and fail if the state did not move |
| ladder | `autoresearch/supervisor/guards.py` | window, busy session, marker, process scan — each pure and fail-closed |
| binding | `autoresearch/supervisor/hermes_binding.py` | the one scheduler: listing parser, argv, profile layout, session calls |
| prompt | `autoresearch/supervisor/overnight/prompt.tmpl.txt` + `launch.py` | rendered from the objective's active leg, the engine's status/doctor/catalog, the last verdict, the charter |
| marker | `autoresearch/engine/autoresearch/marker.py` | a run announces itself at start and removes the marker at exit |

Three divergences from the downstream shape, each deliberate:

1. **`overnight-loop`, not `arena-overnight`.** This repo has no league: the prompt names the
   objective's active leg and the engine's own commands, and the charter is a template section
   the adopter fills rather than a verbatim user message. Nothing about seasons, referees or
   the captain economy travels.
2. **The marker replaces the pgrep guard's role.** Downstream's own record calls the scan
   "brittle by nature — exactly how PR #40 happened"; the documented fix (a pidfile the run
   writes) is now the first signal, and the scan is the fallback.
3. **`zoneinfo`, not a fixed UTC offset.** A fixed offset is exact for one city and an hour
   wrong for a DST zone part of the year; adopters are worldwide.

What is still not claimed: no live scheduler has fired this recipe here. The ladder is proved
against a stubbed session API and the marker against the real engine, so the record reads
`pending`, not `works` — the same habit the downstream record needed a day to earn.

## Related

- [[loop-stop-conditions]] — the bounded stop policy a fired run must honour.
- [[headless-harness-invocation]] — the exact argv a recipe's launcher executes.
- [[harness-portability]] — why a file living in one harness's profile is not portable.
- [[run-record-contract]] — what the fired run must leave behind.
- [[fair-competition-invariants]] — the live-round guard protects one writer per period.
