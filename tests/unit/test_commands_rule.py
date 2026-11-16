"""Standing order 8, enforced (unit tier). IDs: AC-CMD-009..012. PRD 23.

The order — *every request is a repo command* — was prose plus a catalog nothing
required anyone to use: an agent got no procedure, and a tool could sit under the
repo with no command reaching it. Three checks make the rule operational:

* AC-CMD-009 — the order is in `AGENTS.md`, the PRD carries its success
  criterion and test mapping, and `.agents/skills/repo-commands/SKILL.md` (and so
  `.claude/skills/repo-commands/`, the same tree through a symlink) states the
  procedure with valid frontmatter.
* AC-CMD-010 — every entry point under the engine's `bin/`, `target/` and
  `supervisor/` is reachable through a registry command, or is allowlisted with
  the reason it is not one. An orphan fails naming its path and the remedy.
* AC-CMD-011 — the commands that named previously uncatalogued tools
  (`target.import`, `supervisor status|pause|resume`) declare exactly the flags
  their tools take and build the argv those parsers accept.
* AC-CMD-012 — the entry-point detector's own boundary: it finds a `__main__`
  module and a shell script, and does not flag a library module.

`AGENTS.md` and the skill are read, never written here: the rule is the
operator's, and a test that could rewrite it would not be a check.

Hermetic: file reads, stdlib parsing, and one bounded `--help` subprocess per
command under test. No docker, no state, no target code.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = ROOT / "AGENTS.md"
PRD_23 = ROOT / "docs" / "prd" / "23-command-registry.md"
REGISTRY_FILE = ROOT / "autoresearch" / "commands" / "registry.py"
SKILL_DIR = ROOT / ".agents" / "skills" / "repo-commands"
SKILL_MD = SKILL_DIR / "SKILL.md"
CLAUDE_SKILL_MD = ROOT / ".claude" / "skills" / "repo-commands" / "SKILL.md"

ORDER_HEADING = "### 8. Every Request Is a Repo Command"

#: Directories whose runnable files are entry points by default.
SCAN_DIRS = (
    "autoresearch/engine/bin",
    "autoresearch/target",
    "autoresearch/supervisor",
)

#: The complete exception list, with the reason each is not a command of its own.
#: Anything else that runs is an orphan, and AC-CMD-010 fails naming it.
ALLOWED = {
    "autoresearch/supervisor/overnight/install.sh":
        "a thin wrapper that execs supervisor/install.py with this recipe's directory; "
        "`supervisor install` is the command",
}

#: The entry points the scan must find, named here so a broken scan cannot pass by
#: finding nothing. A file that is not on this list is found by the walk, not by it.
REQUIRED = {
    "autoresearch/engine/bin/autoresearch",
    "autoresearch/target/cli.py",
    "autoresearch/target/import_runs.py",
    "autoresearch/supervisor/install.py",
    "autoresearch/supervisor/control.py",
    "autoresearch/supervisor/overnight/launch.py",
}


# -- loading -----------------------------------------------------------------


def load_registry():
    """The registry module, loaded by absolute path (never by package name)."""
    spec = importlib.util.spec_from_file_location("repo_commands_rule_registry", REGISTRY_FILE)
    assert spec is not None and spec.loader is not None, REGISTRY_FILE
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frontmatter(text):
    """`{key: value}` from a SKILL.md's `---` block; a missing fence is a failure."""
    assert text.startswith("---\n"), "SKILL.md does not open with a '---' fence"
    block = text.split("---", 2)[1]
    fields = {}
    for line in block.strip().splitlines():
        key, separator, value = line.partition(":")
        assert separator, f"frontmatter line is not 'key: value': {line!r}"
        fields[key.strip()] = value.strip()
    return fields


# -- the entry points, and what reaches them ---------------------------------


def is_entry_point(path: Path) -> bool:
    """Whether a file is something an operator or a scheduler can run.

    A `.sh` always is. A `.py` is one when it carries a `__main__` guard — a
    library module is not an entry point, and flagging it would only grow the
    allowlist. A file with no suffix is one when it opens with a shebang (the
    engine's wrapper is bash).
    """
    try:
        if path.suffix == ".sh":
            return True
        head = path.read_bytes()[:2]
        if path.suffix == ".py":
            text = path.read_text(encoding="utf-8", errors="replace")
            return '"__main__"' in text or "'__main__'" in text
        return head == b"#!"
    except OSError:
        return False


def entry_points(root: Path = ROOT) -> set:
    """Repo-relative paths of every runnable entry point in the scanned scope."""
    found = set()
    for rel in SCAN_DIRS:
        base = root / rel
        assert base.is_dir(), f"the scanned directory is gone: {rel}"
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if is_entry_point(path):
                found.add(path.relative_to(root).as_posix())
    return found


def reachable_paths(registry):
    """Every tool path a registry command drives."""
    covered = set()
    for spec in registry.COMMANDS:
        tool = spec["tool"]
        if tool is None:
            continue
        values = tool.values() if isinstance(tool, dict) else [tool]
        covered.update(Path(value).as_posix() for value in values)
    return covered


def orphan_findings(points, covered, allowed=ALLOWED):
    """One finding per entry point no command reaches — empty means none."""
    findings = []
    for rel in sorted(points):
        if rel in covered or rel in allowed:
            continue
        findings.append(
            f"{rel}: no registry command reaches it — add a registry command "
            "(a _command(...) with this tool) in autoresearch/commands/registry.py, "
            "or add it to ALLOWED in tests/unit/test_commands_rule.py with the "
            "reason it is not one"
        )
    return findings


def help_text(registry, spec):
    """One command's real help, from the tool itself, bounded and shell-free."""
    tool = str(registry.tool_path(spec))
    head = [tool] if spec["runner"] == "script" else [sys.executable, tool]
    argv = [*head, *spec["prefix"], *spec["probe"]]
    done = subprocess.run(
        argv, capture_output=True, text=True, timeout=120, cwd=str(ROOT)
    )
    assert done.returncode == 0, f"{' '.join(argv)}: {done.stderr}"
    assert "usage:" in done.stdout, f"{argv[-1]} printed no help: {done.stdout!r}"
    return done.stdout


# --- AC-CMD-009 -------------------------------------------------------------


def test_standing_order_8_and_the_repo_skill_say_the_same_thing():
    """AC-CMD-009: `AGENTS.md` carries the order naming the catalog and PRD 23,
    the PRD carries its success criterion and test mapping, and the repo skill
    states the procedure with valid frontmatter — present through
    `.claude/skills` too."""
    agents = AGENTS_MD.read_text(encoding="utf-8")
    assert ORDER_HEADING in agents, f"AGENTS.md lost the standing order heading: {ORDER_HEADING}"
    order = agents.split(ORDER_HEADING, 1)[1].split("\n### ", 1)[0]
    assert "autoresearch commands list" in order, order
    assert "docs/prd/23-command-registry.md" in order, order
    assert "no ad-hoc scripts" in order, order

    prd = PRD_23.read_text(encoding="utf-8")
    assert "SC-cmd-7" in prd, "PRD 23 does not carry the rule's success criterion"
    for ac in ("AC-CMD-009", "AC-CMD-010", "AC-CMD-011"):
        assert ac in prd, f"PRD 23's test mapping omits {ac}"

    assert SKILL_MD.is_file(), f"the repo skill is missing: {SKILL_MD}"
    body = SKILL_MD.read_text(encoding="utf-8")
    fields = frontmatter(body)
    assert fields.get("name") == "repo-commands", fields
    assert fields.get("description"), "the skill has no description"
    assert "autoresearch/bin/autoresearch commands list" in body, body
    assert "registry.py" in body and "PR" in body, body
    assert "CLI/agent only" in body, "the skill never states the surface safety rule"
    assert "AC-CMD-010" in body, "the skill never names the check that fails an orphan"

    # `.claude/skills` is a symlink to `.agents/skills`, so the skill travels.
    assert os.path.islink(ROOT / ".claude" / "skills"), ".claude/skills is not a symlink"
    assert CLAUDE_SKILL_MD.resolve() == SKILL_MD.resolve(), (
        f"{CLAUDE_SKILL_MD} does not resolve to {SKILL_MD}")


# --- AC-CMD-010 -------------------------------------------------------------


def test_every_entry_point_is_reachable_through_a_registry_command():
    """AC-CMD-010: no orphan entry points. Every runnable file under the engine's
    `bin/`, `target/` and `supervisor/` is driven by a catalog command, or is on
    the reasoned allowlist; a synthetic orphan is reported with its path and the
    remedy, so the check cannot pass vacuously."""
    registry = load_registry()
    points = entry_points()
    assert len(points) >= len(REQUIRED), f"the entry-point scan found only {sorted(points)}"
    assert REQUIRED <= points, f"the scan missed: {sorted(REQUIRED - points)}"

    covered = reachable_paths(registry)
    findings = orphan_findings(points, covered)
    assert findings == [], "\n".join(findings)

    # The allowlist is load-bearing and current: every entry exists, says why, and
    # is NOT reached — an exception that a command now covers is stale, not harmless.
    for rel, reason in ALLOWED.items():
        assert (ROOT / rel).is_file(), f"allowlisted {rel} is gone — drop the entry"
        assert reason.strip(), f"{rel} is allowlisted with no reason"
        assert rel not in covered, f"{rel} is allowlisted but a command reaches it now"

    # Negative control: an uncatalogued tool is reported, so a green run means
    # something.
    ghost = {"autoresearch/target/ghost-tool.py"}
    reported = orphan_findings(ghost, covered)
    assert reported and "ghost-tool.py" in reported[0], reported
    assert "add a registry command" in reported[0], reported
    assert "ALLOWED" in reported[0], reported


# --- AC-CMD-011 -------------------------------------------------------------


def test_the_new_commands_declare_the_flags_their_tools_take():
    """AC-CMD-011: `target.import` and `supervisor status|pause|resume` — the
    commands added for tools nothing could reach — build the argv their parsers
    accept, and every flag they declare appears in those tools' own `--help`."""
    registry = load_registry()
    python = sys.executable

    imported = registry.get("target", "import")
    assert registry.name_of(imported) == "target.import"
    assert registry.build_argv(imported, {"source": "runs/season-3", "dry_run": True}) == [
        python, str(ROOT / "autoresearch/target/import_runs.py"),
        "--from", "runs/season-3", "--profile", "example", "--dry-run",
    ]
    assert imported["mutates"] is True
    assert imported["executes_target_code"] is False
    assert registry.surfaces(imported) == ["cli"]

    for verb in ("status", "pause", "resume"):
        spec = registry.get("supervisor", verb)
        assert registry.name_of(spec) == f"supervisor.{verb}"
        built = registry.build_argv(spec, {"profile": "p"})
        assert built == [
            python, str(ROOT / "autoresearch/supervisor/control.py"), verb,
            registry.DEFAULT_RECIPE, "--profile", "p", "--binding", "hermes",
        ], built
        assert registry.surfaces(spec) == ["cli"], f"supervisor.{verb} must not reach HTTP"
        assert spec["local_only"] is True, (
            f"supervisor.{verb} reads the host's scheduler, not this repo's state")

    assert registry.get("supervisor", "status")["mutates"] is False
    assert registry.get("supervisor", "pause")["mutates"] is True
    assert registry.get("supervisor", "resume")["mutates"] is True

    for spec in (imported, *[registry.get("supervisor", v) for v in
                             ("status", "pause", "resume")]):
        text = help_text(registry, spec)
        for field in spec["args"].values():
            if field.get("positional") or field["type"] == "argv":
                continue
            assert field["flag"] in text, (
                f"{registry.name_of(spec)}: {field['flag']} is not a flag of "
                f"{registry.tool_path(spec).name}")

    # The no-orphan rule still holds: the tools these four share are reached.
    for rel in ("autoresearch/target/import_runs.py", "autoresearch/supervisor/control.py"):
        assert rel in reachable_paths(registry), rel


# --- AC-CMD-012 -------------------------------------------------------------


def test_the_entry_point_detector_has_an_honest_boundary(tmp_path):
    """AC-CMD-012: the detector finds what can be run and nothing else — a
    `__main__` module and a shell script are found, a library module and a
    non-runnable file are not. Without this the allowlist could hide a whole
    directory behind one word."""
    (tmp_path / "tool.py").write_text(
        "def main():\n    return 0\n\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8")
    (tmp_path / "shell.sh").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    (tmp_path / "script").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    (tmp_path / "library.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("if __name__ == '__main__':\n", encoding="utf-8")

    assert is_entry_point(tmp_path / "tool.py") is True
    assert is_entry_point(tmp_path / "shell.sh") is True
    assert is_entry_point(tmp_path / "script") is True
    assert is_entry_point(tmp_path / "library.py") is False
    assert is_entry_point(tmp_path / "notes.txt") is False

    # And the same files, through the walk, are found — the scan uses the detector.
    for rel in SCAN_DIRS:
        (tmp_path / rel).mkdir(parents=True)
    for name in ("tool.py", "library.py", "shell.sh", "notes.txt"):
        (tmp_path / "autoresearch" / "target" / name).write_text(
            (tmp_path / name).read_text(encoding="utf-8"), encoding="utf-8")
    found = entry_points(tmp_path)
    assert found == {
        "autoresearch/target/tool.py",
        "autoresearch/target/shell.sh",
    }, sorted(found)
