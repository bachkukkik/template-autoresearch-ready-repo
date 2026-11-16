#!/usr/bin/env python3
"""The one command registry: every user-facing command, declared once.

A command is a ``(group, verb)`` pair plus what it takes and what it costs: a
one-line help, a typed argument schema, ``mutates`` and ``executes_target_code``,
and the argv mapping that reaches the real tool. ``autoresearch commands list``,
``commands describe``, ``--help`` and the argv a command runs are all generated
from the declarations below, so a command cannot exist on one surface and not
another, and no prompt or doc needs to restate a tool's flags.

Three rules hold every entry:

* an executor runs a real tool as a **subprocess with a list argv and a timeout**
  — nothing here is a shell, and a hostile value stays one argv element;
* the argv mapping is declared, never concatenated from caller text, and every
  choice is validated before a child starts;
* a target is a **declared profile name**, never a free filesystem path: the
  shape is refused here and the declaration is refused by the target CLI, so a
  caller cannot aim the engine at a checkout of its choosing.

Surfaces follow the cost flags: a command that writes, executes the target's code
or reads the **host** rather than this repo's state can never be exposed over
REST or MCP. Those two surfaces are not built yet (PRD 23, *Out of Scope*), so
``GENERATED_SURFACES`` is ``('cli',)`` and the catalog says so; the derivation is
already in place, so the day a route lands it exposes only what ``exposeable()``
allows.

The module is loaded by absolute file path (``autoresearch/bin/autoresearch``)
and is stdlib-only: the engine's own package is also called ``autoresearch``, so
an importable package here would collide with it in either direction.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

#: The repository this registry drives (an installed copy names its checkout).
REPO_ROOT = Path(
    os.environ.get("AUTORESEARCH_REPO_ROOT") or Path(__file__).resolve().parents[2]
)
ENGINE_WRAPPER = "autoresearch/engine/bin/autoresearch"
TARGET_CLI = "autoresearch/target/cli.py"
TARGET_IMPORT = "autoresearch/target/import_runs.py"
SUPERVISOR_INSTALL = "autoresearch/supervisor/install.py"
SUPERVISOR_CONTROL = "autoresearch/supervisor/control.py"
SUPERVISOR_LAUNCH = "autoresearch/supervisor/overnight/launch.py"
DEFAULT_RECIPE = "autoresearch/supervisor/overnight"

#: One target profile name: a file stem under ``autoresearch/targets/``, never a path.
PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

#: The surfaces this repo generates today. REST and MCP are a later wave; a
#: read-only command is CLI/agent only until then, and the catalog says `cli`.
GENERATED_SURFACES = ("cli",)


def _literal_names(module: str, name: str) -> list[str]:
    """The strings a module-level binding in *module* declares, or ``[]``.

    Read with ``ast`` rather than imported: importing the engine package from here
    is the shadowing this module is written to avoid, and a second hardcoded list
    is how a surface keeps refusing a value the tool already accepts. A binding
    may be a literal, a name bound above it, or a ``+`` of either (``AGENTS`` is
    ``HARNESSES + ("command", "replay")``).
    """
    path = REPO_ROOT / module
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    bindings = {
        target.id: node.value
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }

    def resolve(value, depth: int = 0) -> list[str]:
        if depth > 4 or value is None:
            return []
        if isinstance(value, (ast.Tuple, ast.List)):
            return [
                item.value for item in value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
        if isinstance(value, ast.Name):
            return resolve(bindings.get(value.id), depth + 1)
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            return resolve(value.left, depth + 1) + resolve(value.right, depth + 1)
        return []

    return resolve(bindings.get(name))


def agent_names() -> list[str]:
    """The agent names the engine's adapter table declares, in its own order."""
    return _literal_names("autoresearch/engine/autoresearch/adapters.py", "AGENTS")


def direction_names() -> list[str]:
    """The metric directions the engine's config declares, in its own order."""
    return _literal_names("autoresearch/engine/autoresearch/config.py", "DIRECTIONS")


class CommandError(RuntimeError):
    """A command that could not be run, or an argument refused before it starts."""


class UnknownCommand(CommandError):
    """A name that is not in the catalog."""


class CommandTimeout(CommandError):
    """A child that outlived its declared bound."""


# -- argument schema helpers --------------------------------------------------


def _flag(name: str, kind: str, help: str, **extra) -> dict:
    """One declared argument: its JSON type, the flag it becomes, its help."""
    field = {"type": kind, "flag": name, "help": help}
    field.update(extra)
    return field


#: A profile *name* positional: validated here, declared-and-loaded by the target CLI.
TARGET_NAME = _flag("name", "name", "declared profile name under autoresearch/targets/",
                    positional=True, required=True)
RECIPE_DIR = _flag("recipe_dir", "str", "the recipe directory (holds recipe.json)",
                   positional=True)
SCHEDULER = {
    "profile": _flag("--profile", "str", "profile name"),
    "root": _flag("--root", "str", "scheduler root"),
    "bin": _flag("--bin", "str", "the scheduler executable"),
    "binding": _flag("--binding", "str", "which scheduler binding to use", default="hermes"),
}


def _command(
    group: str,
    verb: str | None,
    help: str,
    *,
    tool: str | None = None,
    runner: str = "python",
    prefix: tuple[str, ...] = (),
    args: dict[str, dict] | None = None,
    mutates: bool,
    executes_target_code: bool,
    timeout: int = 120,
    local_only: bool = False,
    internal: str | None = None,
    probe: tuple[str, ...] | None = ("--help",),
) -> dict:
    """One declared command. Safety flags are stated, never inferred from help."""
    return {
        "group": group,
        "verb": verb,
        "help": help,
        "tool": tool,
        "runner": runner,
        "prefix": list(prefix),
        "args": args or {},
        "mutates": mutates,
        "executes_target_code": executes_target_code,
        "local_only": local_only,
        "timeout": timeout,
        "internal": internal,
        #: argv suffix that makes the tool print its own flags; ``None`` means the
        #: tool has no parser and the test checks the flags against its source.
        "probe": None if probe is None else list(probe),
    }


COMMANDS: list[dict] = [
    # -- engine: the two-stage loop (PRD 17, 20) ------------------------------
    _command(
        "engine", "init",
        "validate the measured repo and write its run.json",
        tool=ENGINE_WRAPPER, runner="script", prefix=("init",),
        args={
            "repo": _flag("--repo", "str", "the measured repo (default: the cwd)"),
            "state": _flag("--state-dir", "str",
                           "where run.json and the ledger live (default: <repo>/.autoresearch)"),
            "verify": _flag("--verify", "str", "command that prints the metric"),
            "metric_name": _flag("--metric-name", "str", "the metric the verify command prints"),
            "direction": _flag("--direction", "choice", "which way the metric improves",
                               choices=direction_names() or ["lower", "higher"]),
            "objective": _flag("--objective", "str", "the tracked objective record"),
            "objective_leg": _flag("--objective-leg", "str", "which leg of that record"),
            "scope": _flag("--scope", "list", "a path a candidate may edit (repeatable)",
                           required=True, metavar="PATH"),
            "guard": _flag("--guard", "str", "command that must exit 0"),
            "target": _flag("--target", "float", "the goal value"),
            "noise_floor": _flag("--noise-floor", "float", "the least real improvement"),
            "repeats": _flag("--repeats", "int", "readings per measurement"),
            "verify_timeout": _flag("--verify-timeout", "float", "seconds for the verify command"),
            "guard_timeout": _flag("--guard-timeout", "float", "seconds for the guard"),
            "protect": _flag("--protect", "list", "a path no candidate may touch (repeatable)",
                             metavar="PATH"),
            "program": _flag("--program", "str", "program file of standing instructions"),
            "goal": _flag("--goal", "str", "the goal in one line"),
            "force": _flag("--force", "bool", "archive the previous run and start again"),
        },
        mutates=True, executes_target_code=False, timeout=300,
    ),
    _command(
        "engine", "run",
        "run the keep/discard loop; the exit code is the run's own",
        tool=ENGINE_WRAPPER, runner="script", prefix=("run",),
        args={
            "repo": _flag("--repo", "str", "the measured repo (default: the cwd)"),
            "state": _flag("--state-dir", "str", "the run's state directory"),
            "agent": _flag("--agent", "choice", "which harness proposes the edits",
                           choices=agent_names() or ["claude", "command", "replay"],
                           required=True),
            "model": _flag("--model", "str", "the model the adapter is told about"),
            "agent_cmd": _flag("--agent-cmd", "str", "the harness binary, when not on PATH"),
            "agent_arg": _flag("--agent-arg", "list", "one extra argv element for the harness",
                               metavar="ARG"),
            "replay": _flag("--replay", "str", "JSONL record file for --agent replay"),
            "record": _flag("--record", "str", "append each candidate patch to this JSONL"),
            "max_iterations": _flag("--max-iterations", "int", "most rounds to run"),
            "plateau": _flag("--plateau", "int", "stop after this many non-keeps"),
            "max_wall": _flag("--max-wall", "float", "wall-clock ceiling in seconds (0 = none)"),
            "agent_timeout": _flag("--agent-timeout", "float", "seconds one harness call gets"),
            "max_crashes": _flag("--max-crashes", "int", "stop after this many crashes"),
            "dry_run": _flag("--dry-run", "bool", "print the plan, run nothing"),
            "json_output": _flag("--json", "bool", "emit the summary as JSON"),
        },
        mutates=True, executes_target_code=True, timeout=3600,
    ),
    _command(
        "engine", "status",
        "replay-validate the ledger and summarise the run",
        tool=ENGINE_WRAPPER, runner="script", prefix=("status",),
        args={
            "repo": _flag("--repo", "str", "the measured repo (default: the cwd)"),
            "state": _flag("--state-dir", "str", "the run's state directory"),
            "json_output": _flag("--json", "bool", "emit the summary as JSON"),
            "require_provenance": _flag("--require-provenance", "bool",
                                        "fail (exit 3) when a decision carries no provenance"),
        },
        mutates=False, executes_target_code=False, timeout=120,
    ),
    _command(
        "engine", "report",
        "write report.md and results.tsv (or the close record)",
        tool=ENGINE_WRAPPER, runner="script", prefix=("report",),
        args={
            "repo": _flag("--repo", "str", "the measured repo (default: the cwd)"),
            "state": _flag("--state-dir", "str", "the run's state directory"),
            "out": _flag("--out", "str", "where to write the report"),
            "record": _flag("--record", "bool", "write record.json + record.md beside it"),
            "check": _flag("--check", "bool",
                           "re-render the record and exit 0 only on byte identity"),
        },
        mutates=True, executes_target_code=False, timeout=300,
    ),
    _command(
        "engine", "doctor",
        "report the harness binaries this host has, and their versions",
        tool=ENGINE_WRAPPER, runner="script", prefix=("doctor",),
        mutates=False, executes_target_code=False, local_only=True, timeout=60,
    ),
    _command(
        "engine", "objective-validate",
        "list every problem in a tracked objective record (exit 1 invalid, 2 unreadable)",
        tool=ENGINE_WRAPPER, runner="script", prefix=("objective", "validate"),
        args={"file": _flag("--file", "str", "the record (default: autoresearch/objective/registry.json)")},
        mutates=False, executes_target_code=False, timeout=60,
    ),
    _command(
        "engine", "objective-resolve",
        "print the init arguments one leg of an objective record implies",
        tool=ENGINE_WRAPPER, runner="script", prefix=("objective", "resolve"),
        args={
            "file": _flag("--file", "str", "the record (default: autoresearch/objective/registry.json)"),
            "leg": _flag("--leg", "str", "the leg to resolve"),
            "json_output": _flag("--json", "bool", "emit JSON"),
        },
        mutates=False, executes_target_code=False, timeout=60,
    ),
    # -- target: what is measured, and its state (PRD 22) ----------------------
    _command(
        "target", "profile",
        "validate a declared profile and print the engine plan (dry — runs nothing)",
        tool=TARGET_CLI,
        args={"name": TARGET_NAME,
              "repo": _flag("--repo", "str", "the checkout measured (default: the cwd)"),
              "json_output": _flag("--json", "bool", "emit {name, profile, target, argv}")},
        mutates=False, executes_target_code=False, timeout=60,
    ),
    _command(
        "target", "import",
        "copy an external run ledger into a declared profile's runs directory",
        tool=TARGET_IMPORT,
        args={
            "source": _flag("--from", "str", "the runs directory to copy (read only)",
                            required=True),
            "profile": _flag("--profile", "str", "the declared profile it belongs to",
                             default="example"),
            "to": _flag("--to", "str", "destination runs directory"),
            "dry_run": _flag("--dry-run", "bool", "print what would be copied"),
            "force": _flag("--force", "bool", "overwrite an existing state.json"),
        },
        mutates=True, executes_target_code=False, timeout=300,
    ),
    # -- supervisor: the cron recipe (PRD 21) ---------------------------------
    _command(
        "supervisor", "render",
        "render the overnight prompt without touching the API or the state",
        tool=SUPERVISOR_LAUNCH, prefix=("--dry-run",),
        mutates=False, executes_target_code=False, timeout=300,
    ),
    _command(
        "supervisor", "install",
        "install this recipe into a scheduler profile (idempotent)",
        tool=SUPERVISOR_INSTALL,
        args={"recipe_dir": {**RECIPE_DIR, "default": DEFAULT_RECIPE},
              "profile": SCHEDULER["profile"],
              "root": SCHEDULER["root"],
              "bin": SCHEDULER["bin"],
              "binding": SCHEDULER["binding"],
              "set": _flag("--set", "list", "override one config value, repeatable",
                           metavar="KEY=VALUE"),
              "dry_run": _flag("--dry-run", "bool", "print every planned write, perform none")},
        mutates=True, executes_target_code=False, local_only=True, timeout=300,
    ),
    _command(
        "supervisor", "status",
        "print the recipe's job as the scheduler reports it: id, state, schedule, next run",
        tool=SUPERVISOR_CONTROL, prefix=("status",),
        args={"recipe_dir": {**RECIPE_DIR, "default": DEFAULT_RECIPE}, **SCHEDULER},
        mutates=False, executes_target_code=False, local_only=True, timeout=60,
    ),
    _command(
        "supervisor", "pause",
        "pause the recipe's job (found by the recipe name; refuses 0 or 2+ matches)",
        tool=SUPERVISOR_CONTROL, prefix=("pause",),
        args={"recipe_dir": {**RECIPE_DIR, "default": DEFAULT_RECIPE}, **SCHEDULER},
        mutates=True, executes_target_code=False, local_only=True, timeout=120,
    ),
    _command(
        "supervisor", "resume",
        "resume the recipe's paused job and re-read its state",
        tool=SUPERVISOR_CONTROL, prefix=("resume",),
        args={"recipe_dir": {**RECIPE_DIR, "default": DEFAULT_RECIPE}, **SCHEDULER},
        mutates=True, executes_target_code=False, local_only=True, timeout=120,
    ),
    # -- the catalog itself ---------------------------------------------------
    _command(
        "commands", "list",
        "print the command catalog every surface is generated from",
        internal="list",
        args={"format": _flag("--format", "choice", "output format",
                              choices=["table", "json"], default="table")},
        mutates=False, executes_target_code=False, timeout=30, probe=None,
    ),
    _command(
        "commands", "describe",
        "print one command's schema and safety flags as JSON",
        internal="describe",
        args={
            "group": _flag("group", "str", "command group", positional=True, required=True),
            "verb": _flag("verb", "str", "command verb (omit for a group-level command)",
                          positional=True),
        },
        mutates=False, executes_target_code=False, timeout=30, probe=None,
    ),
    # -- the engine, passed through -------------------------------------------
    _command(
        "engine", None,
        "the engine's own CLI, passed through unchanged for anything the verbs above "
        "do not cover (CLI only)",
        tool=ENGINE_WRAPPER, runner="script",
        args={"args": _flag("args", "argv", "argv passed to the engine wrapper")},
        mutates=True, executes_target_code=True, timeout=3600, probe=None,
    ),
]


# -- the catalog --------------------------------------------------------------


def name_of(spec: dict) -> str:
    """``engine.run`` — the stable id; the CLI spells it ``engine run``."""
    return spec["group"] if spec["verb"] is None else f"{spec['group']}.{spec['verb']}"


def exposeable(spec: dict) -> bool:
    """Whether a command may ever reach HTTP: it must write nothing and run none."""
    return not (spec["mutates"] or spec["executes_target_code"] or spec["local_only"])


def refusal(spec: dict) -> str:
    """Why HTTP/MCP may never run this command — the reason a caller is told."""
    reasons = []
    if spec["mutates"]:
        reasons.append("it mutates state")
    if spec["executes_target_code"]:
        reasons.append("it executes the target's code")
    if spec["local_only"]:
        reasons.append("it reads the host, not this repo's state")
    return " and ".join(reasons)


def surfaces(spec: dict) -> list[str]:
    """Where a command is reachable: the generated surfaces, if its cost allows."""
    if not exposeable(spec):
        return ["cli"]
    return list(GENERATED_SURFACES)


def schema(spec: dict) -> dict:
    """The argument schema as JSON Schema — the one shape help, docs and routes use."""
    properties = {}
    required = []
    for field_name, field in spec["args"].items():
        entry: dict = {"description": field["help"]}
        kind = field["type"]
        if kind == "int":
            entry["type"] = "integer"
        elif kind == "float":
            entry["type"] = "number"
        elif kind == "bool":
            entry["type"] = "boolean"
        elif kind in ("list", "argv"):
            entry.update({"type": "array", "items": {"type": "string"}})
        else:
            entry["type"] = "string"
        if "choices" in field:
            entry["enum"] = list(field["choices"])
        if "default" in field:
            entry["default"] = field["default"]
        properties[field_name] = entry
        if field.get("required"):
            required.append(field_name)
    document = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        document["required"] = required
    return document


def catalog(only: str | None = None) -> list[dict]:
    """Every command (or only those reachable on one surface), as plain dicts."""
    rows = []
    for spec in COMMANDS:
        reachable = surfaces(spec)
        if only is not None and only not in reachable:
            continue
        rows.append(
            {
                "name": name_of(spec),
                "group": spec["group"],
                "verb": spec["verb"],
                "help": spec["help"],
                "mutates": spec["mutates"],
                "executes_target_code": spec["executes_target_code"],
                "local_only": spec["local_only"],
                "surfaces": reachable,
                "exposeable": exposeable(spec),
                "refusal": refusal(spec),
                "tool": spec["tool"],
                "timeout": spec["timeout"],
                "schema": schema(spec),
            }
        )
    return rows


def get(group: str, verb: str | None) -> dict:
    """One command by its CLI spelling; unknown names raise ``UnknownCommand``."""
    wanted = group if verb is None else f"{group}.{verb}"
    for spec in COMMANDS:
        if name_of(spec) == wanted:
            return spec
    raise UnknownCommand(f"unknown command {wanted!r} — run 'autoresearch commands list'")


def get_by_name(name: str) -> dict:
    """One command by its dotted catalog name (``engine.run``)."""
    group, _, verb = name.partition(".")
    return get(group, verb or None)


def _declares(group: str, verb: str | None) -> bool:
    """Whether ``(group, verb)`` is a catalog entry, without raising."""
    try:
        get(group, verb)
    except CommandError:
        return False
    return True


def tool_path(spec: dict) -> Path:
    """The real tool file this command drives, as an absolute path."""
    tool = spec["tool"]
    if tool is None:
        raise CommandError(f"{name_of(spec)} runs inside the registry, not as a tool")
    return REPO_ROOT / tool


# -- argument validation and the declared argv mapping ------------------------


def _text(value, field_name: str) -> str:
    """A scalar argument as one argv element: text, never a shell fragment."""
    if not isinstance(value, str):
        raise CommandError(f"{field_name} must be a string")
    if "\x00" in value:
        raise CommandError(f"{field_name} contains a NUL byte")
    return value


def _number(value, field_name: str, integer: bool):
    """A number as the type the tool's parser accepts; a bool is never one."""
    if isinstance(value, bool):
        raise CommandError(f"{field_name} must be a number, not a boolean")
    try:
        return int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        kind = "an integer" if integer else "a number"
        raise CommandError(f"{field_name} must be {kind}") from exc


def _profile_name(value, field_name: str) -> str:
    """A declared profile *name*: the shape a path or a file name never has."""
    text = _text(value, field_name)
    if text in (".", "..") or text.startswith("~") or "/" in text or "\\" in text:
        raise CommandError(
            f"{field_name} must be a declared profile name (letters, digits, '.', '_', '-'), "
            "never a filesystem path"
        )
    if text.endswith(".json"):
        raise CommandError(
            f"{field_name} must be a declared profile name, not the file {text!r}: "
            f"pass {text[:-5]!r}"
        )
    if not PROFILE_NAME.match(text):
        raise CommandError(f"{field_name} {text!r} is not a declared profile name")
    return text


def _field_argv(field_name: str, field: dict, value) -> list[str]:
    """One declared field as argv elements — validated, never concatenated."""
    kind = field["type"]
    if kind == "bool":
        return [field["flag"]] if value else []
    if value is None:
        if "default" in field:
            value = field["default"]
        elif field.get("required"):
            raise CommandError(f"{field_name} is required")
        else:
            return []
    if kind == "argv":
        if not isinstance(value, (list, tuple)):
            raise CommandError(f"{field_name} must be a list of strings")
        return [_text(item, field_name) for item in value]
    if kind == "list":
        if not isinstance(value, (list, tuple)):
            raise CommandError(f"{field_name} must be a list")
        argv = []
        for item in value:
            argv.extend([field["flag"], _text(item, field_name)])
        return argv
    if kind == "name":
        value = _profile_name(value, field_name)
    elif kind == "choice":
        value = _text(value, field_name)
        if value not in field["choices"]:
            raise CommandError(f"{field_name} must be one of {', '.join(field['choices'])}")
    elif kind == "int":
        value = str(_number(value, field_name, integer=True))
    elif kind == "float":
        value = str(_number(value, field_name, integer=False))
    else:
        value = _text(value, field_name)
    return [value] if field.get("positional") else [field["flag"], value]


def build_argv(spec: dict, args: dict) -> list[str]:
    """The one declared mapping: validated args in, a list argv out. No shell.

    The order is the contract: the runner, the tool's sub-argv, then every field in
    declaration order — which is the order each tool's own parser accepts.
    """
    unknown = sorted(set(args or {}) - set(spec["args"]))
    if unknown:
        raise CommandError(
            f"{name_of(spec)} does not take {', '.join(unknown)}; "
            f"accepts: {', '.join(spec['args']) or 'no arguments'}"
        )
    if spec["internal"] is not None:
        raise CommandError(f"{name_of(spec)} runs inside the registry, not as a tool")
    if spec["runner"] == "script":
        argv = [str(tool_path(spec))]
    else:
        argv = [sys.executable, str(tool_path(spec))]
    argv.extend(spec["prefix"])
    for field_name, field in spec["args"].items():
        argv.extend(_field_argv(field_name, field, (args or {}).get(field_name)))
    return argv


# -- executing ----------------------------------------------------------------


def run_command(name: str, args: dict | None = None) -> dict:
    """Run one command; return ``{command, argv, returncode, stdout, stderr, duration_s}``.

    The child is always a list argv with a hard ``timeout`` and the repo root as
    cwd; nothing here is a shell. A command that cannot start raises
    ``CommandError``; one that outlives its bound raises ``CommandTimeout``.
    """
    spec = get_by_name(name)
    args = dict(args or {})
    started = time.monotonic()
    stderr = ""
    if spec["internal"] is not None:
        stdout = _run_internal(spec, args)
        argv: list[str] = []
        code = 0
    else:
        argv = build_argv(spec, args)
        try:
            done = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=float(spec["timeout"]),
                cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandTimeout(f"{name_of(spec)} timed out after {spec['timeout']}s") from exc
        except OSError as exc:
            raise CommandError(f"cannot start {name_of(spec)}: {exc}") from exc
        stdout, stderr, code = done.stdout, done.stderr, done.returncode
    return {
        "command": name_of(spec),
        "argv": argv,
        "returncode": code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_s": round(time.monotonic() - started, 3),
    }


def _run_internal(spec: dict, args: dict) -> str:
    """The two catalog commands: the registry answering about itself."""
    unknown = sorted(set(args) - set(spec["args"]))
    if unknown:
        raise CommandError(f"{name_of(spec)} does not take {', '.join(unknown)}")
    if spec["internal"] == "list":
        wanted = args.get("format") or "table"
        if wanted not in ("table", "json"):
            raise CommandError("format must be one of table, json")
        rows = catalog()
        if wanted == "json":
            return json.dumps({"commands": rows}, indent=2) + "\n"
        return _table(rows)
    group = args.get("group")
    verb = args.get("verb")
    if not isinstance(group, str):
        raise CommandError("describe needs a group")
    spec = get(group, verb if isinstance(verb, str) else None)
    return json.dumps(catalog_row(spec), indent=2) + "\n"


def catalog_row(spec: dict) -> dict:
    """One catalog row — the same shape ``catalog()`` emits."""
    for row in catalog():
        if row["name"] == name_of(spec):
            return row
    raise CommandError(f"{name_of(spec)} is not in the catalog")


def _table(rows: list[dict]) -> str:
    """The catalog as a fixed-width table: name, surfaces, cost flags, help."""
    width = max(len(row["name"]) for row in rows)
    lines = [f"{'NAME'.ljust(width)}  SURFACES  MUTATES  EXEC  LOCAL  HELP"]
    for row in rows:
        lines.append(
            row["name"].ljust(width)
            + "  "
            + ", ".join(row["surfaces"]).ljust(8)
            + ("yes" if row["mutates"] else "no").ljust(9)
            + ("yes" if row["executes_target_code"] else "no").ljust(7)
            + ("yes" if row["local_only"] else "no").ljust(7)
            + row["help"]
        )
    return "\n".join(lines) + "\n"


# -- the CLI ------------------------------------------------------------------


def build_parser(spec: dict) -> argparse.ArgumentParser:
    """``autoresearch <group> <verb> --help``, generated from the declared schema."""
    prog = " ".join(part for part in ("autoresearch", spec["group"], spec["verb"]) if part)
    parser = argparse.ArgumentParser(prog=prog, description=spec["help"])
    for field_name, field in spec["args"].items():
        kwargs: dict = {"help": field["help"]}
        if field["type"] == "argv":
            # A passthrough takes raw argv elements, so help shows one remainder
            # positional and no flag is invented for it.
            parser.add_argument(field_name, nargs=argparse.REMAINDER, **kwargs)
            continue
        if field["type"] == "bool":
            kwargs["action"] = "store_true"
        elif field["type"] == "list":
            kwargs["action"] = "append"
            kwargs["metavar"] = field.get("metavar", "VALUE")
        elif field["type"] == "choice":
            kwargs["choices"] = field["choices"]
        elif field["type"] == "int":
            kwargs["type"] = int
        elif field["type"] == "float":
            kwargs["type"] = float
        if "default" in field:
            kwargs["default"] = field["default"]
        if field.get("positional"):
            if not field.get("required"):
                kwargs["nargs"] = "?"
            parser.add_argument(field_name, **kwargs)
        else:
            if field.get("required"):
                kwargs["required"] = True
            parser.add_argument(field["flag"], dest=field_name, **kwargs)
    return parser


def usage() -> str:
    """The one-screen map of the surface."""
    lines = ["usage: autoresearch <group> <verb> [--flag value ...]", "", "groups:"]
    groups: dict[str, list[str]] = {}
    for spec in COMMANDS:
        groups.setdefault(spec["group"], []).append(spec["verb"] or "<args...>")
    width = max(len(group) for group in groups)
    for group, verbs in groups.items():
        lines.append(f"  {group.ljust(width)}  {' '.join(verbs)}")
    lines += [
        "",
        "  autoresearch commands list             the catalog (name, surfaces, cost)",
        "  autoresearch commands describe G [V]   one command's schema, as JSON",
        "  autoresearch <group> <verb> --help     the flags that command takes",
        "  autoresearch engine <args...>           the engine's own CLI, passed through",
        "",
        "A command that mutates state, executes the target's code or reads the host is",
        "CLI/agent only, and this cycle generates no REST or MCP surface at all",
        "(docs/prd/23-command-registry.md). A target is a declared profile name.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Dispatch one command; the exit code is the tool's own."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(usage())
        return 0

    group = argv[0]
    if group == "engine" and not _declares(group, argv[1] if len(argv) > 1 else None):
        return _passthrough(argv[1:])
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.stdout.write(usage())
        return 0
    try:
        spec = get(group, argv[1])
    except CommandError as exc:
        print(f"autoresearch: error: {exc}", file=sys.stderr)
        return 2

    parsed = build_parser(spec).parse_args(argv[2:])
    args = {field: value for field, value in vars(parsed).items() if value is not None}
    try:
        result = run_command(name_of(spec), args)
    except CommandTimeout as exc:
        print(f"autoresearch: error: {exc}", file=sys.stderr)
        return 124
    except CommandError as exc:
        print(f"autoresearch: error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(result["stdout"])
    sys.stderr.write(result["stderr"])
    return result["returncode"]


def _passthrough(argv: list[str]) -> int:
    """``autoresearch engine <args...>``: hand off to the engine's own wrapper."""
    wrapper = REPO_ROOT / ENGINE_WRAPPER
    if not wrapper.is_file():
        print(f"autoresearch: error: no engine wrapper at {wrapper}", file=sys.stderr)
        return 2
    os.execv(str(wrapper), [str(wrapper), *argv])
    return 2  # unreachable: execv replaces this process or raises


if __name__ == "__main__":
    sys.exit(main())
