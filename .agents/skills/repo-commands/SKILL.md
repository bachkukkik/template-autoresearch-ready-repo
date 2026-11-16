---
name: repo-commands
description: Use when a request in this repo names work to do. Resolve it to a catalog command first; a missing command is added by PR before the work.
---

# Repo Commands — every request resolves to the catalog

**Triggers:** every request in this repo (`AGENTS.md` standing order 8). A
request is a command, or it becomes one. It is never a one-off script and never
an argv pasted into a scheduler or a prompt.

## Procedure

1. **Read the catalog.** `autoresearch/bin/autoresearch commands list` — one row
   per command: name, surfaces, `mutates`, `executes_target_code`, `local_only`,
   help. `--format json` gives the same rows for a script.
2. **Read the schema.** `autoresearch/bin/autoresearch commands describe <group> <verb>`
   — the argument types, the required ones, the choices, the timeout.
3. **Pick and run on your surface.** CLI and agent mode can run every command:
   `autoresearch <group> <verb> [--flag value]`. `autoresearch <group> <verb> --help`
   is generated from the same schema, so it cannot disagree with the catalog.
   `autoresearch engine <args...>` is the engine's own CLI, passed through
   unchanged, for the few things the declared verbs do not cover.
4. **Nothing fits: add the command, by PR, before the work.**
   - One `_command(...)` in `autoresearch/commands/registry.py`: `group`, `verb`,
     one-line `help`, `tool` (the real file), `prefix`, the `args` schema,
     `mutates`, `executes_target_code`, `local_only`, `timeout`.
   - One test in `tests/unit/test_commands_registry.py` for the new entry.
   - Then the CLI and the generated help exist — there is no second surface to
     wire, and no prose to keep in sync.

## Safety

`mutates`, `executes_target_code` and `local_only` are stated from what the code
does, never guessed from a flag name: `--dry-run` can still stamp state, and a
`--check` can still run the target's code. Any of the three makes a command
**CLI/agent only** — it has no REST or MCP surface, now or when those routes
land. Do not widen that gate.

## Crons and prompts

The catalog is the source for both. A recipe or a prompt names a catalog command
and never restates a tool's flags; a schedule is a command plus a time. An entry
point with no catalog command fails `tests/unit/test_commands_rule.py`
(AC-CMD-010), which names the path and this remedy.
