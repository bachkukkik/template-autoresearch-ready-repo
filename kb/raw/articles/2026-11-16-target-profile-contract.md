---
source_url: https://github.com/vanilla-republic/vanilla-open-design-autoresearch
ingested: 2026-11-16
sha256: 02ef66d85bbbafa6f231e6b18c42c59bb136758efeaae83a3e7426d01ff035de
source_type: code-capture
kind: article
title: "Target-profile contract — relativity, refusal-by-name and the evaluator guard (code capture)"
---

# Target-profile contract — a code capture

## Provenance

**What.** The contract half of the downstream league's "target as a parameter" work,
captured from the code rather than from prose: `autoresearch/league/arena.py:222-539`
read in full (the parameter block, `league_tool`, `resolve_target`, `load_profile`,
`apply_profile`, `set_target`, `EVALUATOR_FILES`, `evaluator_digest`, `evaluator_tamper`)
and `autoresearch/league/referee.py:30-179` (the mirrored block, plus the second key
list). The profile example `autoresearch/league/targets/vanilla-open-design.json`
(all 88 lines) and `autoresearch/league/tools/import-runs.py` (all 124 lines) were read
in full. Read-only, 2026-11-16, at the downstream checkout the distillation records at
`92b7674`.

**What it is not.** The 4,980-line `arena.py` and 2,580-line `referee.py` are not
captured — only the ~300 lines that carry the idea. Nothing here is a tournament
mechanic; seasons, the captain economy, media and the corpus stay downstream.

**Labels.** `[M]` read directly in the code at the line cited; `[S]` stated by the
downstream PR body or its own season record (quoted with its number); `[I]` inference.

**Why this repo cares.** The template's engine has `--repo` per run but no
evaluator-side profile and no second competitor: every adopter meets "where does the
harness live relative to the repo it measures?" first, and the default answer (inside
it) is wrong.

## The split: two halves, one profile

The league is played *against* a checkout, never against the code it ships with
`[M]` (`arena.py:222-230`). Both halves live in one JSON profile, and the split is by
**what each key is relative to**, stated in the profile's own `$comment` so a reader
cannot mis-guess it `[M]` (`targets/vanilla-open-design.json:2-15`):

| Half | Keys | Resolved against |
|------|------|------------------|
| harness-owned | `engine`, `referee`, `guard_command`, `runs_dir` | `LEAGUE_REPO = LEAGUE_DIR.parents[1]` |
| target-relative | `program`, `scopes`, `protected`, `docker_free_tier`, `e2e_dir`, `context_dir`, `dockerfile`, `fresh_script`, `guard_steps`, `fresh_instruction`, `arena_test_files` | the checkout a round names |

`program` is target-relative **on purpose**: it is the seat contract *of the measured
checkout*, and the engine refuses a `--protect` path outside the worktree it protects,
so the program must be inside it `[M]` (`arena.py:435-439`). `guard_command` is a
template — `python3 {referee} --target-repo {target} guard` — and `{referee}` is the
harness's evaluator, `{target}` the worktree being measured `[M]` (`arena.py:431-441`,
`targets/vanilla-open-design.json:20`).

Resolution is **pure and first**: flag → `$AUTORESEARCH_TARGET_REPO` →
`cwd` `[M]` (`arena.py:364-377`, mirrored `referee.py:121-130`). `league_tool(rel)`
resolves a harness key against `LEAGUE_REPO`, an absolute path honoured as given, so
tool paths do not move when another `--target-repo` is named `[M]` (`arena.py:276-284`).

## Refusal by name, before any state is read

`load_profile` refuses a profile that is unreadable, is not a JSON object, or is
missing a key the module reads — naming the path and every missing key `[M]`
(`arena.py:380-406`). The referee mirrors it but raises `SystemExit` where the arena
raises `ArenaError` `[M]` (`referee.py:140-161`).

Two independent key lists exist and disagree: `PROFILE_KEYS` has 11 entries including
`name` `[M]` (`arena.py:241-253`), `REQUIRED_KEYS` has 8 and omits `name`, `program`,
`referee` `[M]` (`referee.py:46-55`). There is no shared validator — PR #20's
keep-the-empty-key workaround exists because of that split `[S]`. The template port
ships **one** schema and **one** validator for this reason.

## The tamper guard: outside the worktree is not outside the process

Moving the evaluator out of the measured worktree bounds what a seat's **diff** can
reach; it does not detect a **write**. A seat runs as the same OS user and can open
`.../league/arena.py` by absolute path, and the engine's diff of its own worktree never
sees it `[S]` (PR #12; downstream `docs/23-league-home.md:120-156`).

The round therefore hashes its evaluator surface at both ends `[M]`
(`arena.py:482-517`):

- `evaluator_digest(paths)` — a sha256 per file, `None` for one that is gone, so a
  deletion is a change like any other and a comparison never guesses why an entry
  vanished.
- `evaluator_tamper(before, after)` — the record a round leaves when the surface moved:
  `{"evaluator_tampered": [absolute paths], "penalty": {"A": "protected_violation",
  "B": "protected_violation"}}`; both seats are charged, nothing is settled, and the
  tampered files are kept as evidence rather than restored.
- `EVALUATOR_FILES` is bound by `apply_profile`: the referee, `arena.py`, the profile
  file itself, the seat wrapper `tools/arena-agent.py`, and every engine file
  (`bin/autoresearch` + `autoresearch/*.py`) `[M]` (`arena.py:409-462`).
- Exit code **4** marks the tampered round `[S]` (PR #12).

**The honest limit, stated downstream:** two hash reads cannot see a write-then-restore;
the close is a read-only mount or a separate user, and until then the record must say
which reads it took `[S]` (PR #12; `docs/23:120-156`).

## State migrates by one command

`tools/import-runs.py` — 124 lines, stdlib only, no shell — copies a season's record
(`state.json`, `scoreboard.md`, `season-*`, `round-*`) into the harness's runs
directory: a copy, never a move; `*.lock` and `__pycache__` never carried; `--dry-run`
writes nothing; an existing `state.json` refuses (exit 1) without `--force` `[M]`
(`import-runs.py:1-124`). The league's own `.gitignore` ignores `runs/*` and keeps
`runs/.gitkeep` `[S]`.

## Four failures the contract answers

1. **A profile that pointed at the target's own evaluator.** Wave 1 copied the files
   but `referee`, `guard_command` and `runs_dir` still named the target's
   `autoresearch/arena/`, so a round executed the target's referee and wrote the
   target's state; the next wave was scheduled to delete that arena, which would have
   broken every round `[S]` (PR #11). AC-LGE-002 (profile completeness), AC-LGE-007
   (tool paths here, target paths there), AC-LGE-008 (runs dir, nothing written in the
   target).
2. **The evaluator left the protected list when it left the worktree.** `--protect`
   only accepts a path inside the worktree a seat owns, so `referee.py` and `arena.py`
   could not stay on it — and a marker-scan bug then had the harness scoring its own
   code `[S]` (PR #12). AC-LGE-012 (tamper guard), AC-LGE-015 (the protected surface
   the in-worktree diff cannot see).
3. **A coverage claim that was not re-run.** The archive commit claimed AC-LGE-017
   carried all 43 AC-EVL-013 drift cases; it carried the happy path, and no collected
   test exercised the rest `[S]` (PR #15). AC-LGE-025 (archive coverage gate). A test
   mapping is a claim to be re-run, not restated.
4. **A required key naming the subject's own artifacts went stale.** `arena_test_files`
   named the target's test files; PR #20 removed the two removed suites from the
   target and the key had to stay, present and empty (`[]`), because the failure mode
   of deleting it is "missing file", not "engine behaved badly" `[S]` (PR #20).
   AC-LGE-002 again: present-but-empty is honest; deleted is refused by name.

## What the capture establishes, and what it does not

**Establishes.** The exact key lists and their relativity `[M]`; the resolution order
and its purity `[M]`; refusal by name and the two-schema defect `[M]`; the digest/tamper
shape and what it can and cannot see `[M]`/`[S]`; the import command's behaviour `[M]`.

**Does not establish.** That two hashes are sufficient against a same-user writer —
they are not `[S]`; any tournament number; that the downstream schema is stable. The
template port adapts the schema (one validator, named profiles instead of paths, an
explicit `metric_name`/`direction`) and states the divergence where it happens.
