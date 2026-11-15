---
title: Unattended Loop Recipe
created: 2026-11-15
updated: 2026-11-15
type: concept
tags: [autoresearch, agentic, ops]
sources: [raw/articles/2026-11-15-downstream-frontier-distillation.md]
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

Skip a tick rather than write twice:

1. `--dry-run` returns before every guard.
2. Outside `[start, end)` on the configured offset → exit 0, no log line.
3. An unreadable session API → log `api-error … not firing blind`, exit 0.
4. **Session liveness** — a streaming or recently-touched session of the *target* profile
   blocks. Check **all** sessions plus an idle floor: a worker between tool calls reports
   `agent_running=false`, so checking only the last recorded session id fires a duplicate
   session into a live one.
5. **Detached-process marker** — a live round blocks. A round is a detached tree invisible to
   the session API, so this guard is the only bar to a second writer; and it must match the
   **argv shape actually used**, because global flags sit between script and subcommand:
   `(?:arena\.py|registry\.py\s+league)\b.*\sround(?:\s|$)` behind a deliberately broad
   `pgrep` prefilter, with `--dry-run` counted as in flight. The naive
   `pgrep -af "arena.py round"` returned nothing during a real round — it failed open `[S]`.

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

## Related

- [[loop-stop-conditions]] — the bounded stop policy a fired run must honour.
- [[headless-harness-invocation]] — the exact argv a recipe's launcher executes.
- [[harness-portability]] — why a file living in one harness's profile is not portable.
- [[run-record-contract]] — what the fired run must leave behind.
- [[fair-competition-invariants]] — the live-round guard protects one writer per period.
