# PRD 23 — Command Registry: One Definition, One Generated Surface

> Intent: give this repo **one** declaration of every user-facing command —
> `autoresearch <group> <verb>` — and generate the catalog, the help and the
> argv from it. A request resolves to a catalog command; a command that does not
> exist yet is added by PR with a test, before the work. The surfaces that would
> make a command reachable from outside the process (REST, MCP) are **not**
> built in this cycle: the registry declares the cost flags that will decide
> them, and generates the CLI today. **Domain:** `cmd` — the command surface of
> this repo. **Canonical tests:** `tests/unit/test_commands_registry.py`
> (`AC-CMD-001..008`), `tests/unit/test_commands_rule.py` (`AC-CMD-009..012`),
> `tests/integration/test_commands_cli.py` (`AC-CMD-201`). **Grounding:**
> [command-registry](../../kb/concepts/command-registry.md),
> [harness-portability](../../kb/concepts/harness-portability.md) (one canonical
> source, a binding per surface, never a fork),
> [rest-vs-mcp-dual-exposure](../../kb/comparisons/rest-vs-mcp-dual-exposure.md)
> (one core, two adapters — and never an omnibus code-execution tool on the
> injected surface); raw source
> [command-registry-raw](../../kb/raw/articles/2026-11-16-command-registry.md).
> **Builds on:** PRD 17 (the engine CLI this cannot change), PRD 21 (the
> supervisor recipe whose installer it names), PRD 22 (the target CLI and the
> declared profile name). It changes none of those contracts. **Provenance:**
> the downstream league (`vanilla-open-design-autoresearch`) built this surface
> over two PRs (#16, #17) against a 30-command catalog; its generic core (~350
> of 1,090 lines) and the enforcement shape are ported here, its league, media
> and economy entries are not. **Stage 6:** `docs/23-command-registry.md` —
> **pending**; it is written from a verification run, not from this plan.

## Context

The repo already has a surface; it just cannot be enumerated:

1. **The entry points are real, and nothing lists them.**

   ```text
   autoresearch/engine/bin/autoresearch init|run|status|report|doctor|objective …
   autoresearch/target/cli.py profile <name>
   autoresearch/target/import_runs.py --from …
   autoresearch/supervisor/install.py <recipe_dir> --profile …
   autoresearch/supervisor/control.py status|pause|resume
   autoresearch/supervisor/overnight/launch.py --dry-run
   ```

   Each is real, each has its own flags, and the way in is `--help` on a path
   an adopter has to already know.
2. **The prose restates the argv.**
`.agents/commands/ar-{init,run,status,report}.md` and a supervisor prompt
each spell engine flags in sentences. Prose drifts from argparse silently,
and nothing fails when it does.
3. **Cost is implicit.** `init` writes, `run` writes *and* runs the target's
code, `status` does neither, `doctor` reports the **host's** binaries.
Nothing in the code says which is which, so "expose the surface over HTTP" is
one careless decorator away from an omnibus execution tool — which the kb
verdict forbids for the injected surface.
4. **The rule is prose.** *Every request is a repo command* needs three things
to be operational: a catalog to resolve against, a procedure an agent is
handed, and a check that fails when a runnable file has no command. This repo
has none of them yet; `AGENTS.md`'s standing orders stop at 7.
5. **A name collision is waiting.** The engine's Python package is
`autoresearch`. A registry at `autoresearch/commands/registry.py` imported
*by name* could shadow it — or be shadowed by it — depending on `sys.path`
order, failing in one ordering on one machine and not another.

**Users.** (a) An adopter who wants to run something and must choose between
reading argparse and guessing. (b) A coding agent that gets a request and needs
one stable way in. (c) The maintainer, who needs a check — not a convention —
that keeps the tools and the catalog the same set.

## Scope

**In.** One stdlib-only module `autoresearch/commands/registry.py`; one shell
wrapper `autoresearch/bin/autoresearch`; the kind `profile` on `target.profile`;
the standing order 8 text in `AGENTS.md`, measured against the existing
`AC-CTX-003` headroom floor; one repo skill
`.agents/skills/repo-commands/SKILL.md` (reachable as
`.claude/skills/repo-commands/`); the no-orphan check with a one-entry
allowlist; PRD 23 and its index rows.

**Out.** REST and MCP routes and their service half; the slash commands
retargeted onto the catalog; league, media, economy and season vocabulary; a
scheduler for commands; per-caller authorization; plugin discovery at runtime.

## Success Criteria

- **SC-cmd-1 — One definition per command.** Every user-facing command is
declared exactly once in `autoresearch/commands/registry.py`: a
`(group, verb)` name, one-line help, a typed argument schema (types, required,
choices, defaults), `mutates`, `executes_target_code`, `local_only`, a
timeout, and the argv mapping that reaches the real tool. No second table, no
hand-maintained help text, no tool-specific code path. The seventeen entries
are
`engine.init|run|status|report|doctor|objective-validate|objective-resolve`,
`target.profile|import`, `supervisor.render|install|status|pause|resume`,
`commands.list|describe`, plus the engine passthrough. _Verify:_
`tests/unit/test_commands_registry.py` (AC-CMD-001, AC-CMD-003).

- **SC-cmd-2 — The catalog, the help and the argv are generated from the
schema.** `autoresearch commands list` prints the catalog (`--format json` for
a script), `commands describe <group> [<verb>]` prints one row, and
`autoresearch <group> <verb> --help` is built by `build_parser(spec)` — so a
declared flag that the help omits, or a flag the help invents, is a test
failure. Every declared flag is also checked against the **tool's own**
`--help`, so a renamed flag fails here rather than in an overnight run.
_Verify:_ `tests/unit/test_commands_registry.py` (AC-CMD-003, AC-CMD-008),
`tests/integration/test_commands_cli.py` (AC-CMD-201).

- **SC-cmd-3 — Cost is stated, and exposure is derived from it.** The three
flags are marked from what the code does, never from a flag name:
`engine.report --check` writes nothing but the command *may* write (so it is
mutating); `engine.run` runs the target's code; `engine.doctor` and the three
`supervisor` job commands read the **host**. `exposeable(spec)` is one pure
function over those flags, and `surfaces(spec)` returns only the surfaces this
cycle generates — `('cli',)` — so the catalog says `cli` for every row and a
read-only command is not claimed to be reachable somewhere it is not. A test
flips the generated-surface tuple and proves a mutating command still cannot
reach it. _Verify:_ `tests/unit/test_commands_registry.py` (AC-CMD-001,
AC-CMD-007).

- **SC-cmd-4 — A target is a declared name, never a path.** `target.profile`'s
one positional is a profile name: a path, a traversal-shaped name, `~…`,
`…json` or a NUL byte is refused **by the registry** before a child starts,
and the target CLI refuses the same values again by name (undeclared, a file,
a path) — two independent guards on one rule, so neither a future surface nor
a future caller can aim the measurement at a checkout of its choosing. The
checkout stays deployment configuration (`--repo`,
`$AUTORESEARCH_TARGET_REPO`), as PRD 22 records. _Verify:_
`tests/unit/test_commands_registry.py` (AC-CMD-006).

- **SC-cmd-5 — No shell, every child bounded and declared.** Executors run a
list argv with one `subprocess.run(…, timeout=…)` call site in the module and
`cwd` the repo root; the argv is built field by field from the schema, so an
unknown argument, a bad choice, a NUL byte or a non-integer is refused before
a child starts, and a shell-shaped value arrives as one argv element that no
shell reads. Every command declares an integer timeout in `(0, 3600]`.
_Verify:_ `tests/unit/test_commands_registry.py` (AC-CMD-002, AC-CMD-007).

- **SC-cmd-6 — The engine keeps its own CLI, and the two names cannot collide.**
`autoresearch engine <args…>` — and `autoresearch engine <verb> --help` —
hands the argv to `autoresearch/engine/bin/autoresearch` unchanged, so the
engine's version string, exit codes and flags are the engine's. A declared
engine verb goes through the registry's validation instead; anything else is a
passthrough. The wrapper runs `python3 -P` on the registry's absolute path, so
a decoy `autoresearch.py` in the working directory cannot capture it, and a
probe imports the engine's package and this module side by side under their
own names. _Verify:_ `tests/unit/test_commands_registry.py` (AC-CMD-004),
`tests/integration/test_commands_cli.py` (AC-CMD-201).

- **SC-cmd-7 — Every request resolves to a catalog command, and the rule is
checked.** `AGENTS.md` standing order 8 names `autoresearch commands list` and
this PRD; `.agents/skills/repo-commands/SKILL.md` (the same file through
`.claude/skills`) hands an agent the procedure — read the catalog, read the
schema, run it on your surface, and when nothing fits, add the registry entry
plus its test by PR before doing the work. The check is code: every
**runnable** file under `autoresearch/engine/bin/`, `autoresearch/target/` and
`autoresearch/supervisor/` is reachable through a catalog command or is on a
one-entry allowlist with a stated reason; a stale allowlist entry fails, and
the detector's own boundary (a `__main__` module and a `.sh` are entry points,
a library module is not) is pinned, so the exception list cannot grow by
definition. The four commands that named previously uncatalogued tools
(`target.import`, `supervisor status|pause|resume`) declare exactly their
tools' flags — checked against each tool's own `--help`, not against the
registry's memory of it. _Verify:_ `tests/unit/test_commands_rule.py`
(AC-CMD-009, AC-CMD-010, AC-CMD-011, AC-CMD-012).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-cmd-1 | AC-CMD-001, AC-CMD-003 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-2 | AC-CMD-003, AC-CMD-008 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-2 | AC-CMD-201 | `tests/integration/test_commands_cli.py` | integration |
| SC-cmd-3 | AC-CMD-001, AC-CMD-007 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-4 | AC-CMD-006 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-5 | AC-CMD-002, AC-CMD-007 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-6 | AC-CMD-004 | `tests/unit/test_commands_registry.py` | unit |
| SC-cmd-6 | AC-CMD-201 | `tests/integration/test_commands_cli.py` | integration |
| SC-cmd-7 | AC-CMD-009, AC-CMD-010, AC-CMD-011, AC-CMD-012 | `tests/unit/test_commands_rule.py` | unit |

## CI/CD Gate

- The unit ACs run in the existing `unit` job (`pytest tests/unit`); AC-CMD-201
runs in the existing `integration` job. No new job, no new dependency: the
registry is stdlib-only and its tests spawn only `--help` and read-only
commands.
- No PR merges with a red test, and `bash tests/run.sh` is the local pre-PR run
(`AGENTS.md` §6) — the command surface adds no service and no container, so
there is nothing for the `e2e` tier to cover in this cycle.
- The registry is a normal tracked file: changed by PR, never by a run. It is on
no protected list, and no `.gitignore` entry hides `autoresearch/commands/` or
`autoresearch/bin/` (funnel rule 10) — the `doctrine` job's tracked-root check
covers `autoresearch/` already.
- `AGENTS.md` is under the `AC-CTX-001..003` budget: the file was 19,357 chars
against a 19,500-char working budget (500-char headroom floor) before this
PRD, so standing order 8 could not be appended. It is **compressed first** —
three redundant clauses, each a fact already published elsewhere
(`docs/prd/18` for the PR-Agent wiring and its tuning file, the *Harness
Adapter* table for the skills paths, `docs/13` for the non-visual-engine
rationale) — and the order is added inside the freed space. Both are measured
by the budget test, not by review.

## Assumptions

- `[ASSUMPTION]` A declared engine verb is worth validating even though the
passthrough could carry it: the typed schema is what makes `--help`, the
catalog and the refusal messages agree, and the passthrough stays for
everything else. If this proves noisy in practice, the verbs can go back to
the passthrough without touching the rule.
- `[ASSUMPTION]` Two verbs (`objective-validate`, `objective-resolve`) instead
of one `objective` with a mode argument: the two subcommands take different
flags, and one union schema would accept `--leg` on `validate`, which the
engine refuses. The duplication is one line each and buys an exact schema.
- `[ASSUMPTION]` "Runnable" is the right definition of an entry point
(`__main__` guard, `.sh`, or a shebang) rather than "every `.py`": flagging a
library module would grow the allowlist with names that cannot be run, and a
long allowlist is how this check stops meaning anything.
- `[ASSUMPTION]` `.agents/commands/ar-*.md` keep their prose this cycle. They
are the next drift to remove, but retargeting them is a separate change with
its own review, and doing it here would put a doc rewrite and a new check in
one PR.

## Confidence

**High** that the registry, the catalog and the no-orphan rule behave as
recorded: every AC is a hermetic test, and the red-proofs (a planted orphan, a
decoy module, a path where a name belongs, a shell-shaped argument) were run
against the check itself, not against the code it inspects. **Medium** on the
closed-surface claim: `surfaces()` already derives exposure from cost, but
nothing generates REST or MCP yet, so the refusal is a `False` in the catalog
rather than a 403 on a route — the honest statement is "no HTTP surface exists",
not "the HTTP surface refuses".
