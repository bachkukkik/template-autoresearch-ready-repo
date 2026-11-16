"""The command registry: one definition, a declared argv, a generated catalog.

IDs: AC-CMD-001..008 (unit tier; the hundreds digit is the tier). PRD 23.

The registry is the only place a command is defined: help, a typed argument
schema, ``mutates``/``executes_target_code``/``local_only``, and the argv that
reaches the real tool. These tests pin the properties that make the surface
trustworthy — the catalog cannot name a tool that does not exist, the argv
mapping is exact and shell-free, the generated help is the declared schema, and
the engine's package and this module coexist.

Hermetic: subprocesses run against ``tmp_path`` values, and every check that
would execute target code reads help output or the tool's source instead. No
docker, no network, no agent, no round.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "autoresearch" / "bin" / "autoresearch"
REGISTRY_FILE = ROOT / "autoresearch" / "commands" / "registry.py"
ENGINE_WRAPPER = ROOT / "autoresearch" / "engine" / "bin" / "autoresearch"


def load_registry(name="command_registry_under_test"):
    """The registry module, loaded by absolute path (never by package name)."""
    spec = importlib.util.spec_from_file_location(name, REGISTRY_FILE)
    assert spec is not None and spec.loader is not None, REGISTRY_FILE
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def run(argv, **kwargs):
    """Run one child under the repo, bounded, no shell."""
    kwargs.setdefault("cwd", str(ROOT))
    return subprocess.run(argv, capture_output=True, text=True, timeout=180, **kwargs)


def probe_argv(registry, spec):
    """The argv that makes one command's tool print its own flags."""
    tool = str(registry.tool_path(spec))
    head = [tool] if spec["runner"] == "script" else [sys.executable, tool]
    return [*head, *spec["prefix"], *spec["probe"]]


# --- AC-CMD-001 -------------------------------------------------------------


def test_every_command_is_declared_once_with_help_schema_and_cost(registry):
    """AC-CMD-001: each catalog entry carries one-line help, a typed schema and
    the three cost flags; its surfaces are derived from those flags, and the
    cost is stated rather than inferred from a flag name."""
    rows = registry.catalog()
    assert len(rows) >= 15, f"the catalog shrank to {len(rows)} commands"
    names = [row["name"] for row in rows]
    assert len(names) == len(set(names)), f"duplicate command names: {names}"

    for row in rows:
        assert row["name"] and row["help"], row
        assert "\n" not in row["help"], f"{row['name']}: help must be one line"
        for flag in ("mutates", "executes_target_code", "local_only", "exposeable"):
            assert isinstance(row[flag], bool), (row["name"], flag)
        assert row["schema"]["type"] == "object"
        assert row["schema"]["additionalProperties"] is False
        for field_name, field in row["schema"]["properties"].items():
            assert field["type"] in (
                "string", "integer", "number", "boolean", "array",
            ), (row["name"], field_name)
        if row["name"] not in ("commands.list", "commands.describe"):
            assert row["tool"], f"{row['name']} drives no tool"
            assert (ROOT / row["tool"]).is_file(), f"{row['name']} drives missing {row['tool']}"

    # The cost flags are stated, not guessed: the loop writes and runs the
    # target's code, the two reads do neither, the doctor reads the host.
    by_name = {row["name"]: row for row in rows}
    assert by_name["engine.run"]["mutates"] is True
    assert by_name["engine.run"]["executes_target_code"] is True
    assert by_name["engine.status"]["mutates"] is False
    assert by_name["engine.status"]["executes_target_code"] is False
    assert by_name["engine.doctor"]["local_only"] is True
    assert by_name["supervisor.status"]["local_only"] is True
    assert by_name["supervisor.status"]["mutates"] is False
    assert "host" in by_name["supervisor.status"]["refusal"]

    # A command that costs anything can never be exposed; a read-only one could
    # be, but this cycle generates no HTTP surface at all, so the catalog says cli.
    for row in rows:
        if row["mutates"] or row["executes_target_code"] or row["local_only"]:
            assert row["exposeable"] is False, row["name"]
            assert row["refusal"], f"{row['name']} refuses nothing, so it explains nothing"
        assert row["surfaces"] == ["cli"], row["name"]
    assert registry.GENERATED_SURFACES == ("cli",), (
        "a surface was added to the catalog that this repo does not generate"
    )


def test_the_exposure_rule_is_one_pure_function(registry):
    """AC-CMD-001: the rule is the derivation, not a second allowlist — reading
    only commands are what a future route would expose, and adding a surface to
    the tuple exposes exactly those."""
    read_only = registry.get("engine", "status")
    writing = registry.get("engine", "report")
    assert registry.exposeable(read_only) is True
    assert registry.exposeable(writing) is False

    saved = registry.GENERATED_SURFACES
    registry.GENERATED_SURFACES = ("cli", "api")
    try:
        assert registry.surfaces(read_only) == ["cli", "api"]
        assert registry.surfaces(writing) == ["cli"], (
            "a mutating command reached a generated HTTP surface")
        exposed = [row["name"] for row in registry.catalog(only="api")]
        assert "engine.status" in exposed and "engine.report" not in exposed, exposed
    finally:
        registry.GENERATED_SURFACES = saved


# --- AC-CMD-002 -------------------------------------------------------------


def test_the_declared_argv_mapping_is_exact_and_shell_free(registry, tmp_path):
    """AC-CMD-002: schema -> argv is the declared mapping, in the declared order,
    and an unknown argument, a bad choice, a NUL byte or a path where a name
    belongs is refused before a child starts."""
    python = sys.executable
    engine = str(ENGINE_WRAPPER)

    assert registry.build_argv(
        registry.get("engine", "status"), {"json_output": True}
    ) == [engine, "status", "--json"]

    built = registry.build_argv(
        registry.get("engine", "run"),
        {"agent": "replay", "replay": "r.jsonl", "max_iterations": 3, "dry_run": True},
    )
    assert built == [engine, "run", "--agent", "replay", "--replay", "r.jsonl",
                     "--max-iterations", "3", "--dry-run"], built

    assert registry.build_argv(
        registry.get("engine", "init"), {"scope": ["src", "tests"], "repeats": 3}
    ) == [engine, "init", "--scope", "src", "--scope", "tests", "--repeats", "3"]

    # The profile name is one positional element; --repo stays deployment config.
    assert registry.build_argv(
        registry.get("target", "profile"), {"name": "example", "repo": "/tmp/r"}
    ) == [python, str(ROOT / "autoresearch/target/cli.py"), "example", "--repo", "/tmp/r"]

    # A declared default is emitted, so the tool never guesses which one it got.
    assert registry.build_argv(
        registry.get("supervisor", "status"), {"recipe_dir": registry.DEFAULT_RECIPE}
    ) == [python, str(ROOT / "autoresearch/supervisor/control.py"), "status",
          registry.DEFAULT_RECIPE, "--binding", "hermes"]

    with pytest.raises(registry.CommandError, match="does not take nope"):
        registry.build_argv(registry.get("engine", "status"), {"nope": 1})
    with pytest.raises(registry.CommandError, match="agent must be one of"):
        registry.build_argv(registry.get("engine", "run"), {"agent": "gpt"})
    with pytest.raises(registry.CommandError, match="NUL byte"):
        registry.build_argv(registry.get("engine", "status"), {"repo": "a\x00b"})
    with pytest.raises(registry.CommandError, match="no arguments"):
        registry.build_argv(registry.get("engine", "doctor"), {"repo": "."})

    # A shell-shaped value is one argv element, and no shell ever reads it.
    marker = tmp_path / "pwned"
    hostile = f"{tmp_path}/nope; touch {marker}"
    built = registry.build_argv(registry.get("target", "import"), {"source": hostile})
    assert hostile in built, built
    assert built.count(hostile) == 1, built
    ran = registry.run_command("target.import", {"source": hostile})
    assert ran["returncode"] == 2, ran
    assert hostile in ran["stderr"], ran["stderr"]
    assert not marker.exists(), "an argument was interpreted by a shell"


# --- AC-CMD-003 -------------------------------------------------------------


def test_every_catalog_tool_exists_and_declares_real_flags(registry):
    """AC-CMD-003: every command drives a file that exists, and each flag it
    declares appears in that tool's own ``--help`` — a renamed flag fails here,
    not in an overnight run."""
    for spec in registry.COMMANDS:
        if spec["tool"] is None:
            continue
        tool = registry.tool_path(spec)
        assert tool.is_file(), f"{registry.name_of(spec)} drives missing {tool}"

        fields = [
            (field_name, field)
            for field_name, field in spec["args"].items()
            if not field.get("positional") and field["type"] != "argv"
        ]
        if spec["probe"] is None:
            text = tool.read_text(encoding="utf-8")
            for _, field in fields:
                assert field["flag"] in text, (
                    f"{registry.name_of(spec)}: {field['flag']} is not in the tool")
            continue

        done = run(probe_argv(registry, spec))
        assert done.returncode == 0, (
            f"{' '.join(probe_argv(registry, spec))}: {done.stderr}")
        assert "usage:" in done.stdout, f"{tool.name} printed no help: {done.stdout!r}"
        for _, field in fields:
            assert field["flag"] in done.stdout, (
                f"{registry.name_of(spec)}: {field['flag']} is not a flag of {tool.name}")


# --- AC-CMD-004 -------------------------------------------------------------


def test_the_engine_package_and_the_registry_cannot_shadow_each_other(registry, tmp_path):
    """AC-CMD-004: the engine's `autoresearch` package imports beside this module
    under its own name, `autoresearch engine <args...>` reaches the engine's own
    wrapper unchanged, and the CLI never resolves the working directory — it works
    from a directory holding a decoy `autoresearch.py`, because the wrapper runs
    `python3 -P` on the registry's absolute path."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        f"root = Path({str(ROOT)!r})\n"
        "sys.path.insert(0, str(root / 'autoresearch' / 'engine'))\n"
        "import autoresearch\n"
        "engine_dir = str(root / 'autoresearch' / 'engine')\n"
        "assert autoresearch.__file__.startswith(engine_dir), autoresearch.__file__\n"
        "spec = importlib.util.spec_from_file_location(\n"
        "    'command_registry_probe', root / 'autoresearch' / 'commands' / 'registry.py')\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "assert module.__name__ == 'command_registry_probe'\n"
        "assert module.catalog()\n"
        "print(module.name_of(module.get('engine', 'status')), autoresearch.__name__)\n",
        encoding="utf-8",
    )
    done = run([sys.executable, "-P", str(probe)])
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["engine.status", "autoresearch"]

    # The passthrough hands the engine's own argv to its own wrapper, unchanged.
    passthrough = registry.get("engine", None)
    assert registry.name_of(passthrough) == "engine"
    assert passthrough["runner"] == "script"
    assert registry.build_argv(passthrough, {"args": ["status", "--json"]}) == [
        str(ENGINE_WRAPPER), "status", "--json"]
    real = run([str(BIN), "engine", "--version"])
    assert real.returncode == 0, real.stderr
    assert real.stdout.strip(), "the engine's --version printed nothing"

    # The mechanism, pinned: absolute path plus -P is the whole anti-shadowing trick,
    # so a wrapper edited to `python3 commands/registry.py` fails here.
    wrapper = BIN.read_text(encoding="utf-8")
    assert "python3 -P" in wrapper, "the wrapper dropped -P (the cwd would be on sys.path)"
    assert '"$COMMANDS_DIR/commands/registry.py"' in wrapper, (
        "the wrapper no longer loads the registry by absolute path")

    # A decoy module in the working directory is not on the wrapper's sys.path.
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "autoresearch.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    done = run([str(BIN), "commands", "list"], cwd=str(decoy))
    assert done.returncode == 0, done.stderr
    assert "engine.status" in done.stdout


# --- AC-CMD-005 -------------------------------------------------------------


def test_cli_lists_the_catalog_describes_one_and_passes_the_exit_code(registry):
    """AC-CMD-005: `commands list` prints every row, `--format json` parses to the
    same rows, `commands describe` prints one schema, `--help` is generated from
    that schema, and the CLI returns the tool's own exit code."""
    listed = run([str(BIN), "commands", "list"])
    assert listed.returncode == 0, listed.stderr
    for row in registry.catalog():
        assert row["name"] in listed.stdout, f"the table omits {row['name']}"

    as_json = run([str(BIN), "commands", "list", "--format", "json"])
    assert as_json.returncode == 0, as_json.stderr
    assert len(json.loads(as_json.stdout)["commands"]) == len(registry.catalog())

    described = run([str(BIN), "commands", "describe", "engine", "run"])
    assert described.returncode == 0, described.stderr
    body = json.loads(described.stdout)
    assert body["name"] == "engine.run"
    assert body["mutates"] is True and body["exposeable"] is False
    assert body["schema"]["required"] == ["agent"], body["schema"]
    assert body["schema"]["properties"]["agent"]["enum"] == registry.agent_names()

    help_text = run([str(BIN), "engine", "run", "--help"])
    assert help_text.returncode == 0, help_text.stderr
    assert "--agent" in help_text.stdout and "--max-iterations" in help_text.stdout

    # The CLI is a pass-through of the tool's exit code, never a rewrite of it.
    refused = run([str(BIN), "target", "profile", "../etc"])
    assert refused.returncode == 2, refused.stderr
    assert "never a filesystem path" in refused.stderr

    unknown = run([str(BIN), "engine", "nope"])
    assert unknown.returncode == 2, unknown.stderr


# --- AC-CMD-006 -------------------------------------------------------------


def test_a_target_is_a_declared_name_never_a_path(registry):
    """AC-CMD-006: the shape is refused before a child starts, and the target CLI
    refuses the same values again by name — two independent guards on one rule."""
    for value in ("../etc", "a/b", "~root", ".", "x.json"):
        with pytest.raises(registry.CommandError, match="declared profile name|not the file"):
            registry.build_argv(registry.get("target", "profile"), {"name": value})
    with pytest.raises(registry.CommandError, match="NUL byte"):
        registry.build_argv(registry.get("target", "profile"), {"name": "a\x00b"})

    cli = str(ROOT / "autoresearch" / "target" / "cli.py")
    for value in ("../etc", "a/b", "x.json"):
        done = run([sys.executable, cli, value])
        assert done.returncode == 2, (value, done.stdout, done.stderr)
        assert "declared" in done.stderr, (value, done.stderr)

    # A well-shaped but undeclared name is refused by the tool, naming the declared set.
    done = run([sys.executable, cli, "absent-profile"])
    assert done.returncode == 2, done.stderr
    assert "is not declared" in done.stderr, done.stderr


# --- AC-CMD-007 -------------------------------------------------------------


def test_executors_are_bounded_and_never_use_a_shell(registry):
    """AC-CMD-007: one subprocess call site in the registry, a timeout on it, no
    shell anywhere, and every declared bound is a positive timeout."""
    source = REGISTRY_FILE.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "os.system" not in source and "os.popen" not in source
    assert source.count("subprocess.run(") == 1, "a second call site bypasses the bound"
    assert 'timeout=float(spec["timeout"])' in source

    for spec in registry.COMMANDS:
        assert isinstance(spec["timeout"], int) and 0 < spec["timeout"] <= 3600, (
            registry.name_of(spec))
        if spec["tool"] is not None:
            assert spec["runner"] in ("python", "script"), registry.name_of(spec)
            assert registry.tool_path(spec).is_file(), registry.name_of(spec)


# --- AC-CMD-008 -------------------------------------------------------------


def test_the_generated_help_is_the_declared_schema(registry):
    """AC-CMD-008: `--help` is built from the schema and nothing else — every
    declared flag appears in it, and every flag it prints is declared."""
    for spec in registry.COMMANDS:
        if spec["internal"] is not None:
            continue
        text = registry.build_parser(spec).format_help()
        for field_name, field in spec["args"].items():
            if field["type"] == "argv":
                continue
            needle = field_name if field.get("positional") else field["flag"]
            assert needle in text, (registry.name_of(spec), needle)
        for token in text.replace("(", " ").replace(")", " ").split():
            if token.startswith("--") and token not in ("--help",):
                declared = {
                    field["flag"] for field in spec["args"].values()
                    if not field.get("positional")
                }
                assert token in declared, (
                    f"{registry.name_of(spec)} prints undeclared flag {token}")
