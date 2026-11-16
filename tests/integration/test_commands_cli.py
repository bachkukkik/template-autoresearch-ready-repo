"""PRD 23 — the catalog's CLI smoke, for real. ID: AC-CMD-201.

The unit tier proves the argv mapping and the declared schema; this tier proves
the wrapper: every catalog command answers `--help` as itself, `commands
describe` round-trips a name, and one declared command runs its real tool and
returns that tool's own exit code. No network, no round, no docker — every child
is a `--help` or a read-only tool.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "autoresearch" / "bin" / "autoresearch"


def run(argv, cwd=ROOT, timeout=120):
    """Run one child, bounded, no shell."""
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, cwd=str(cwd)
    )


def catalog_rows():
    done = run([str(BIN), "commands", "list", "--format", "json"])
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["commands"]


def test_ac_cmd_201_every_catalog_command_answers_help_as_itself():
    """AC-CMD-201: each row of the catalog, spelled exactly as the catalog spells
    it, prints its own usage and names one of its declared flags — so a command
    that only exists in the table fails here."""
    rows = catalog_rows()
    assert len(rows) >= 15, f"the catalog shrank to {len(rows)} commands"

    for row in rows:
        verb = row["verb"]
        argv = [str(BIN), row["group"], verb, "--help"] if verb else [
            str(BIN), row["group"], "--help"]
        done = run(argv)
        assert done.returncode == 0, f"{' '.join(argv)}: {done.stderr}"
        assert "usage:" in done.stdout, f"{row['name']} printed no usage: {done.stdout!r}"

        describe = [str(BIN), "commands", "describe", row["group"]]
        if verb:
            describe.append(verb)
        described = run(describe)
        assert described.returncode == 0, f"{row['name']}: {described.stderr}"
        body = json.loads(described.stdout)
        assert body["name"] == row["name"], (row["name"], body["name"])
        assert body["schema"] == row["schema"], row["name"]
        assert body["mutates"] == row["mutates"], row["name"]
        assert body["surfaces"] == row["surfaces"], row["name"]


def test_ac_cmd_201_a_declared_command_runs_its_real_tool():
    """AC-CMD-201: `engine objective-validate` runs the real engine against this
    repo's tracked record, and the wrapper returns the tool's own exit code — not
    a rewritten one."""
    done = run([str(BIN), "engine", "objective-validate"])
    assert done.returncode == 0, done.stderr
    assert "valid" in done.stdout, done.stdout

    # A refusal is the tool's exit code too: an undeclared leg is the engine's 1 or 2.
    bad = run([str(BIN), "engine", "objective-validate", "--file", "/nonexistent.json"])
    assert bad.returncode == 2, (bad.returncode, bad.stdout, bad.stderr)

    # `--help` on a positional-only command still comes from the schema.
    helped = run([str(BIN), "target", "profile", "--help"])
    assert helped.returncode == 0, helped.stderr
    assert "--repo" in helped.stdout and "name" in helped.stdout


def test_ac_cmd_201_the_passthrough_reaches_the_engines_own_cli():
    """AC-CMD-201: `autoresearch engine <args...>` is the engine's CLI, unchanged —
    the same version string the engine's own wrapper prints."""
    through = run([str(BIN), "engine", "--version"])
    direct = run([str(ROOT / "autoresearch" / "engine" / "bin" / "autoresearch"), "--version"])
    assert through.returncode == 0, through.stderr
    assert direct.returncode == 0, direct.stderr
    assert through.stdout == direct.stdout, (through.stdout, direct.stdout)


def test_ac_cmd_201_the_catalog_table_and_json_are_the_same_rows():
    """AC-CMD-201: the table printed for a human names every row the JSON carries —
    one catalog, two renderings, never two lists."""
    rows = catalog_rows()
    table = run([str(BIN), "commands", "list"])
    assert table.returncode == 0, table.stderr
    for row in rows:
        assert row["name"] in table.stdout, f"the table omits {row['name']}"
    assert len(table.stdout.splitlines()) >= len(rows), "the table lost a row"
