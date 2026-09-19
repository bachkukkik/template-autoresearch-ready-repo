"""scripts/verify-clone.sh contract tests. IDs: AC-VC-001..008.

Hermetic by construction: no network (every throwaway tree comes from a local-path
``git clone``), every tree built under pytest's ``tmp_path``, and every invocation an
explicit-argv ``subprocess.run()`` with ``timeout=``, ``cwd=`` and
``capture_output=True`` — never ``shell=True``.

Non-vacuity. verify-clone.sh's success line is reachable only when ``checks_run`` is
greater than zero (the script's own loud-empty guard). That guard is unreachable from
outside the script — nothing a caller does can force ``checks_run`` to zero and then
reach the success line — so do NOT add a test that tries to trigger it: it would pass
for the wrong reason or not at all. Non-vacuity is pinned where it *is* observable:
AC-VC-001 asserts the parsed ``— N check(s) passed`` count is non-zero, and AC-VC-002
asserts the run changed nothing. Those two plus the negative controls below are the
whole contract.
"""
import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path("scripts") / "verify-clone.sh"
CI_WORKFLOW = Path(".github") / "workflows" / "ci.yml"

# 60s: one git-clone plus six read-only checks, with headroom for a loaded host.
TIMEOUT = 60

CHECK_COUNT_RE = re.compile(r"RESULT: PASSED — (\d+) check\(s\) passed")
RESULT_FAILED = "RESULT: FAILED"


def run_verify(bash, root, timeout=TIMEOUT):
    """Invoke the copy of verify-clone.sh inside ``root`` with an explicit argv.

    verify-clone.sh derives its ROOT from ``BASH_SOURCE``, so it must be run as the
    copy *inside* the tree under test; running the repo's own copy with a different
    cwd would still check the repo, not the tree. ``cwd`` is set anyway so the run is
    pinned rather than inherited.
    """
    return subprocess.run(
        [bash, str(root / SCRIPT)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def clone_repo(git, dest):
    """A hermetic, source-read-only clone of this repo at ``dest``.

    A local path — no network — and ``--no-hardlinks`` so the clone's objects are its
    own. ``--depth 1`` yields a real index, so ``git ls-files``/``check-ignore`` behave
    like a fresh clone's (git warns that it ignores ``--depth`` on a local clone; the
    clone is still correct, which is all the checks need).
    """
    proc = subprocess.run(
        [git, "clone", "--quiet", "--no-hardlinks", "--depth", "1",
         str(REPO_ROOT), str(dest)],
        cwd=str(dest.parent),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )
    assert proc.returncode == 0, f"git clone failed ({proc.returncode}): {proc.stderr}"
    return dest


@pytest.fixture
def clone(require_tool, tmp_path):
    """A throwaway clone of this repo, removed when the test ends.

    pytest does not delete ``tmp_path`` on test completion: by default it keeps the
    last three sessions' basetemp trees (``tmp_path_retention_count = 3``), so a 4 MB
    clone per test would linger for three sessions. Remove it explicitly instead.
    """
    dest = tmp_path / "clone"
    clone_repo(require_tool("git"), dest)
    yield dest
    shutil.rmtree(dest, ignore_errors=True)


def git_state(git):
    """The real repo's (porcelain status, HEAD sha) — what the script promises not to change."""
    def capture(*args):
        return subprocess.run(
            [git, *args], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=TIMEOUT
        )

    return capture("status", "--porcelain").stdout, capture("rev-parse", "HEAD").stdout


def assert_named_failure(result, needle):
    """Exit 1 exactly, the verdict line present, and the offender named in stdout."""
    assert result.returncode == 1, result.stdout + result.stderr
    assert RESULT_FAILED in result.stdout, result.stdout
    assert needle in result.stdout, result.stdout


# --- the real repo ----------------------------------------------------------


def test_real_repo_passes_and_reports_a_nonzero_check_count(require_tool):
    """AC-VC-001: the real repo passes, and the run reports a non-zero check count."""
    bash = require_tool("bash")
    require_tool("git")   # the script's checks shell out to git too

    result = run_verify(bash, REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    match = CHECK_COUNT_RE.search(result.stdout)
    assert match, result.stdout
    # The point of this assertion: a run that performed no checks must never be able to
    # satisfy this test. "RESULT: PASSED — 0 check(s) passed" is a vacuous green.
    assert int(match.group(1)) > 0, result.stdout


def test_real_repo_run_is_read_only(require_tool):
    """AC-VC-002: the script's header promises no files, no index, no config — pin it."""
    bash = require_tool("bash")
    git = require_tool("git")

    before = git_state(git)
    result = run_verify(bash, REPO_ROOT)
    after = git_state(git)

    assert result.returncode == 0, result.stdout + result.stderr
    assert after == before, (
        "verify-clone.sh changed the worktree or HEAD — it promises to write nothing\n"
        f"before: {before!r}\nafter:  {after!r}"
    )


# --- negative controls: one broken thing per throwaway clone ----------------


def test_dangling_harness_symlink_fails(require_tool, clone):
    """AC-VC-003: a dangling harness entry point → exit 1, and CLAUDE.md is named."""
    bash = require_tool("bash")
    tree = clone

    link = tree / "CLAUDE.md"
    link.unlink()
    link.symlink_to("does-not-exist.md")

    assert_named_failure(run_verify(bash, tree), "CLAUDE.md is a dangling symlink")


def test_plain_copy_entry_point_fails(require_tool, clone):
    """AC-VC-004: a harness entry point copied instead of symlinked → exit 1, named."""
    bash = require_tool("bash")
    tree = clone

    link = tree / "CLAUDE.md"
    link.unlink()
    link.write_text("AGENTS.md\n")

    assert_named_failure(run_verify(bash, tree), "CLAUDE.md is not a symlink")


def test_undeclared_tracked_root_fails(require_tool, clone):
    """AC-VC-005: a tracked top-level dir nobody declared → exit 1, and it is named."""
    bash = require_tool("bash")
    git = require_tool("git")
    tree = clone

    (tree / "newroot").mkdir()
    (tree / "newroot" / "a.txt").write_text("")
    added = subprocess.run(
        [git, "add", "newroot"], cwd=str(tree), capture_output=True, text=True, timeout=TIMEOUT
    )
    assert added.returncode == 0, added.stderr

    assert_named_failure(run_verify(bash, tree), "newroot is a tracked top-level directory")


def test_gitignored_doctrine_path_fails(require_tool, clone):
    """AC-VC-006: a doctrine path gitignored → exit 1, and docs is named.

    Two moves, because one does not control anything: git's ``check-ignore``
    deliberately does not report a *tracked* path as ignored (``--no-index`` is the
    option that would), so appending ``docs/`` to .gitignore while ``docs`` stays in
    the index leaves the run green. Untracking ``docs`` is what makes the ignore rule
    bite — which is the state the check exists to catch.
    """
    bash = require_tool("bash")
    git = require_tool("git")
    tree = clone

    with open(tree / ".gitignore", "a", encoding="utf-8") as handle:
        handle.write("docs/\n")
    untracked = subprocess.run(
        [git, "rm", "-r", "-q", "--cached", "docs"],
        cwd=str(tree), capture_output=True, text=True, timeout=TIMEOUT,
    )
    assert untracked.returncode == 0, untracked.stderr

    assert_named_failure(run_verify(bash, tree), "docs is matched by a .gitignore rule")


def test_missing_tracked_root_list_fails_loudly(require_tool, clone):
    """AC-VC-007: no tracked-root list in ci.yml → exit 1, naming the file and the shapes."""
    bash = require_tool("bash")
    tree = clone

    ci = tree / CI_WORKFLOW
    kept = "".join(
        line for line in ci.read_text(encoding="utf-8").splitlines(keepends=True)
        # Only the declaration line, the one that holds the list.
        if not re.match(r"\s*DOCTRINE_ROOTS\s*:", line)
    )
    assert not any(re.match(r"\s*DOCTRINE_ROOTS\s*:", line) for line in kept.splitlines()), \
        "the declaration line was not stripped"
    ci.write_text(kept, encoding="utf-8")

    result = run_verify(bash, tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert RESULT_FAILED in result.stdout, result.stdout
    # Never a silent skip: the file it looked in and the shapes it accepted are named.
    assert "no tracked-root list found in .github/workflows/ci.yml" in result.stdout, result.stdout
    assert "VAR=(a b c)" in result.stdout, result.stdout


# --- invocation shape -------------------------------------------------------


def test_subprocess_calls_are_bounded_and_hermetic():
    """AC-VC-008: every subprocess.run call site passes timeout=, cwd= and capture_output=True."""
    assert TIMEOUT == 60

    # By construction: parsed as an AST so a mention of the call in a comment or
    # docstring cannot satisfy the check.
    calls = [
        node
        for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and getattr(node.func.value, "id", "") == "subprocess"
    ]
    assert calls, "expected the subprocess.run call sites"
    for call in calls:
        kwargs = {kw.arg for kw in call.keywords}
        assert "timeout" in kwargs, ast.dump(call)
        assert "cwd" in kwargs, ast.dump(call)
        assert "capture_output" in kwargs, ast.dump(call)
        # Explicit argv — a list of arguments, never one shell string.
        assert isinstance(call.args[0], ast.List), ast.dump(call)
