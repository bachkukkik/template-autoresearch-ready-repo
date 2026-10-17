"""Integration tier — the live `codegraph` CLI behind PRD-07 SC4/SC5. IDs: AC-CG-201..202.

PRD-07 SC4 (`codegraph sync` brings a stale index current) and SC5 (`codegraph
affected --stdin` maps a changed file to its tests) are properties of a LIVE
codegraph binary, so they cannot be asserted hermetically — and the CI runners do
not install the Node tool (issue #29). The module is therefore **opt-in**: each test
resolves `codegraph` through the `require_tool` preflight in `tests/conftest.py` and
SKIPS, naming the tool, on a host that has none. On a host that has one it drives the
real CLI against a hermetic `tmp_path` git project — never this repo — and asserts the
real subprocess output. A whole-tier skip is therefore visible in the CI junit guard's
"executed N test(s), M skipped" line rather than hiding behind a green check.

Transport is the subprocess (`PRD.md` § *Global Test Suite Structure*: integration =
cross-process), which is why this module lives in `tests/integration/`. Every call
sets `DO_NOT_TRACK=1` (SC6) and every call carries a timeout; none uses `shell=True`.
"""
import json
import os
import subprocess

import pytest

CODEGRAPH = "codegraph"
TIMEOUT = 120
NEW_FUNCTION = "\n\ndef b():\n    return 2\n"
SOURCE = "src/m.py"
TEST_FILE = "tests/test_m.py"


def _cg_env():
    """The environment for every codegraph call — `DO_NOT_TRACK=1` is mandatory (SC6)."""
    env = dict(os.environ)
    env["DO_NOT_TRACK"] = "1"
    return env


def _run(args, cwd, *, stdin=None):
    """Run one codegraph invocation: no shell, bounded by TIMEOUT, env pinned."""
    return subprocess.run(
        args,
        cwd=str(cwd),
        input=stdin,
        capture_output=True,
        text=True,
        env=_cg_env(),
        timeout=TIMEOUT,
        check=False,
    )


def _probe_codegraph(exe):
    """Probe: the resolved `codegraph` reports a version (the preflight's contract)."""
    try:
        version = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            env=_cg_env(),
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "`codegraph --version` timed out after 60s"
    if version.returncode != 0:
        return f"`codegraph --version` exited {version.returncode}"
    return None


@pytest.fixture
def cg_project(tmp_path, require_tool):
    """A hermetic git project with a fresh codegraph index; skips without the tool.

    `tmp_path` is the project root, so nothing here touches this repo. The git
    identity is set because `codegraph init` refuses to index a repo without one.
    """
    exe = require_tool(CODEGRAPH, probe=_probe_codegraph)

    def git(*args):
        subprocess.run(
            ["git", *args],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=_cg_env(),
            check=True,
            timeout=TIMEOUT,
        )

    git("init", "-q")
    git("config", "user.name", "codegraph-live-test")
    git("config", "user.email", "codegraph-live-test@example.invalid")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "m.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(
        "from src.m import a\n\n\ndef test_a():\n    assert a() == 1\n",
        encoding="utf-8",
    )

    init = _run([exe, "init"], tmp_path)
    assert init.returncode == 0, (
        f"`codegraph init` failed in the fixture project: {init.stdout}\n{init.stderr}"
    )
    return tmp_path, exe


def test_sync_brings_a_stale_index_current_then_query_finds_the_new_symbol(cg_project):
    """AC-CG-201 (SC4): after the tree moves past the index, `codegraph status`
    reports pending changes and points at `codegraph sync`; after the sync the
    index is up to date again and the new symbol is queryable.

    This is the whole SC4 claim: a session that does not run `sync` reads a stale
    graph, and `status` is what tells it so.
    """
    project, exe = cg_project

    current = _run([exe, "status"], project)
    assert current.returncode == 0, current.stderr
    assert "up to date" in current.stdout.lower(), (
        f"a freshly built index must report as up to date, got: {current.stdout}"
    )

    with (project / SOURCE).open("a", encoding="utf-8") as handle:
        handle.write(NEW_FUNCTION)

    stale = _run([exe, "status"], project)
    combined = stale.stdout + stale.stderr
    assert "Pending Changes" in combined, (
        f"status must report the tree moved past the index, got: {combined}"
    )
    assert "codegraph sync" in combined, (
        f"status must point at the remedy, `codegraph sync`, got: {combined}"
    )

    synced = _run([exe, "sync"], project)
    assert synced.returncode == 0, synced.stderr

    current = _run([exe, "status"], project)
    assert "up to date" in current.stdout.lower(), (
        f"sync must clear the pending state, got: {current.stdout}"
    )

    found = _run([exe, "query", "b"], project)
    assert SOURCE in found.stdout, (
        f"the symbol added before the sync must be queryable after it, got: {found.stdout}"
    )


def test_affected_maps_a_changed_source_file_to_its_test(cg_project):
    """AC-CG-202 (SC5): `codegraph affected --stdin` maps a changed source file to
    the test that covers it — given a test-file glob.

    The default filter matches nothing on this Python layout, so the SC is met
    through `-f <glob>` and both halves are asserted here: the glob maps the file,
    and the default filter is documented-empty (never a silent false negative).
    """
    project, exe = cg_project

    default = _run([exe, "affected", "--stdin", "--json"], project, stdin=f"{SOURCE}\n")
    assert default.returncode == 0, default.stderr
    assert json.loads(default.stdout)["affectedTests"] == [], (
        "the DEFAULT filter is expected to map nothing on a Python layout — if this "
        "now maps the test, the `-f` glob in the PRD-07 SC5 note is stale"
    )

    filtered = _run(
        [exe, "affected", "--stdin", "-f", "tests/*.py", "-j"],
        project,
        stdin=f"{SOURCE}\n",
    )
    assert filtered.returncode == 0, filtered.stderr
    assert json.loads(filtered.stdout)["affectedTests"] == [TEST_FILE], (
        "a test-file glob must map the changed source file to its covering test, "
        f"got: {filtered.stdout}"
    )
