---
source_url: https://github.com/bachkukkik/template-autoresearch-ready-repo
ingested: 2026-11-16
sha256: 1fae574883304b02cc82f317917deee997e6206d1c24f4d10a3857e081887350
source_type: code-capture
kind: article
title: "Command registry — one declaration, generated surfaces, and the no-orphan rule (code capture)"
---

# Command registry — a code capture of the port

## Provenance

**What.** The generic half of the downstream league's command registry
(`vanilla-open-design-autoresearch`), read from the downstream checkout and then
re-expressed in this repo: `autoresearch/commands/registry.py` (17 entries),
`autoresearch/bin/autoresearch` (the wrapper), and the enforcement shape —
`tests/unit/test_commands_rule.py`. Downstream's file is 1,090 lines of which
roughly 350 are the generic core (four error classes, `_flag`/`_command`, the two
scalar validators, `schema()`, `name_of`/`tool_name`, `surfaces()`/`refusal()`,
`catalog(only=)`, `get`/`get_by_name`, `build_argv` + `_field_argv` +
`_normalise`, `run_command`, `_table`, `build_parser`, `usage`, dispatch); the rest
is its 30 league/media/supervisor entries and their derived season and strategy
lists.

**What it is not.** The league's entries (`league.*`, `referee.*`, `runs.*`,
`media.*`), its process-group `run_child`, its season derivation, its 30-row
catalog text and its AC ids are not carried. The template's catalog covers what
this repo actually ships: the engine, the target profile, the supervisor recipe
and the catalog itself.

**Labels.** `[M]` read in the code at the path cited; `[S]` stated by the
downstream PR body or its own record; `[I]` inference.

**Why this repo cares.** The template promises "autoresearch in your repo", but its
entry surface was four slash commands that restate the engine's argv in prose plus
an engine CLI an adopter had to read argparse to use. The registry turns the first
hour into `commands list` → `commands describe engine run` → run, and keeps it true
with a check that fails the day an adopter adds an uncatalogued entry point.
`[M]` (`docs/prd/23-command-registry.md`; `tests/unit/test_commands_rule.py`)

## The declaration

One `_command(...)` per command, all fields explicit `[M]` (`registry.py`):

| Field | Meaning |
|---|---|
| `group`, `verb` | the name; `verb=None` makes a group-level command (`engine`) |
| `help` | one line — the catalog row's help, the parser's description, one string |
| `tool` | the real file the command drives, repo-relative |
| `runner` | `python` (interpreter + file) or `script` (the file itself: the engine's bash wrapper) |
| `prefix` | the sub-argv the tool needs before any declared flag (`init`, `objective validate`, `status`) |
| `args` | the typed schema: `str`, `int`, `float`, `bool`, `list`, `choice`, `argv`, `name` |
| `mutates`, `executes_target_code`, `local_only` | the cost, stated |
| `timeout` | the hard bound on the child |
| `internal` | the two catalog commands, which answer inside the registry |
| `probe` | the argv that makes the tool print its own flags; `None` when it has no parser |

Safety flags are marked from the implementation, never from a flag name `[S]`
(downstream `docs/24:123-140`): `league.round` mutated even under `--dry-run` and
`media.dashboard-check` executed the target's code from inside a `--check`. The
template's two instances of the same trap: `engine.report` is mutating because the
command *may* write even when `--check` does not, and `engine.doctor` is
`local_only` because it reports the **host's** installed harness binaries.

## The argv mapping

`build_argv(spec, args)` is the only place caller input becomes a child's argv `[M]`:

1. unknown argument names are refused by name, with the accepted set;
2. a `script` runner starts with the tool file, a `python` runner with the
   interpreter and the file;
3. `scope="global"` fields first, then `prefix`, then every other field in
   declaration order — the order the tools' own parsers accept;
4. each field is validated and rendered by type: `bool` → its flag or nothing,
   `list` → flag/value repeated, `argv` → raw elements, `choice` → membership,
   `int`/`float` → a number (a bool is refused), `name` → the profile-name shape,
   and a declared default is emitted rather than left to the tool.

`run_command` is one `subprocess.run(argv, …, timeout=float(spec["timeout"]), cwd=REPO_ROOT)`
`[M]`: no shell, one call site, and the tool's own exit code is the answer.

A target is a **declared name** `[S]`: the shape (letters, digits, `.`, `_`, `-`) is
refused in the registry, and the target CLI refuses the same values again — a path,
a traversal-shaped name, `~…`, `…json`, an undeclared stem — before any state is
read. Two guards, one rule: a caller cannot aim the measurement at a checkout of
its choosing.

## Surfaces follow cost

`exposeable(spec)` is one pure function — not mutating, not executing the target's
code, not reading the host — and `surfaces(spec)` returns the generated surfaces if
it allows, `['cli']` otherwise `[M]`. Downstream generated three surfaces plus the
CLI and its REST route answered 403 naming the command and the reason; here no
route exists yet, so the generated tuple is `('cli',)` and every catalog row says
`cli`. The difference matters: the honest claim is "no HTTP surface exists", not
"the HTTP surface refuses". A test flips the tuple and proves a mutating command
still cannot reach the new surface.

## No orphans

Three parts make the rule operational, and all three are needed `[M]`
(`AGENTS.md` standing order 8, `.agents/skills/repo-commands/SKILL.md`,
`tests/unit/test_commands_rule.py`):

* the **order** names the catalog and the PRD;
* the **procedure** an agent is handed: catalog → describe → run on your surface;
  nothing fits → registry entry + test, by PR, first; mutating commands CLI only;
* the **check**: every *runnable* file under `autoresearch/engine/bin`,
  `autoresearch/target` and `autoresearch/supervisor` is reached by some command's
  `tool`, or is on a one-entry allowlist with a stated reason. A stale allowlist
  entry fails, and the detector's boundary is itself pinned — a `__main__` module
  and a `.sh` are entry points, a library module is not.

The definition of "entry point" is the template's divergence from downstream, which
scanned every `.py` and therefore allowlisted pure libraries. A file you cannot run
cannot be an ad-hoc script, so it cannot be an orphan; scanning by runnability keeps
the exception list at one entry and keeps the rule meaningful.

## What the template does differently

| # | Downstream | Here | Why |
|---|---|---|---|
| 1 | one free-argv `engine` passthrough entry | seven declared engine verbs **and** the passthrough | the declared verbs get a typed schema and generated `--help`; the passthrough stays for anything else |
| 2 | `league.*`/`referee.*`/`media.*` = 30 rows | `engine`, `target`, `supervisor`, `commands` = 17 rows | no league, no media, no economy in this repo |
| 3 | four surfaces (CLI, agent, REST, MCP) | CLI + agent; REST and MCP deferred | the service is job-shaped and policy-bounded (PRD 20/24); a second execution path is a design decision, not a port |
| 4 | `--target` emitted `--target-profile` + `--target-repo` from a sibling-directory convention | the name is a positional; the checkout stays `--repo`/`$AUTORESEARCH_TARGET_REPO` | PRD 22 chose the env/flag override; there is no sibling checkout convention here |
| 5 | `_number` truncated a float season (upstream issue #23) | `int` refuses a non-integer, `float` is its own type | no season arithmetic to truncate |
| 6 | entry points = every `.py` under `tools/` | entry points = runnable files | see *No orphans* above |

## Open questions

* Whether the declared engine verbs earn their lines: the passthrough would carry
  them, and the schema's value is the generated `--help` and the refusal messages
  `[I]`.
* Whether `target.profile`'s `--repo` should also be derivable from the profile
  name — a sibling-checkout convention would remove one deployment flag, at the
  cost of one more assumption about where a checkout lives `[I]`.
