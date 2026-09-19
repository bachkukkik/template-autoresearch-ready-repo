"""ops/sync.sh contract tests. IDs: AC-OPS-001..010.

Hermetic by construction: no network, no ambient tooling beyond bash and coreutils,
every tree built under pytest's tmp_path, and every invocation is an explicit-argv
subprocess.run() with a timeout — never shell=True.
"""
import ast
import inspect
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC = REPO_ROOT / "ops" / "sync.sh"

# Keep every invocation short — these are pure file-copy runs, not workloads.
TIMEOUT = 30

SUCCESS_LINE = "== sync complete =="

# Ambient OPS_* vars must not leak into a test's resolution.
_BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith("OPS_")}


@pytest.fixture(autouse=True)
def _require_bash(require_tool):
    """Preflight (AGENTS.md §5): every test here runs ops/sync.sh, whose shebang
    resolves bash from PATH — without this the module's verdict is a property of
    the host rather than of the repo. Applied once for the module, like the
    integration-tier preflight in tests/conftest.py."""
    require_tool("bash")


def run_sync(args, confirm=False, extra_env=None, timeout=TIMEOUT):
    """Invoke ops/sync.sh with explicit argv and a bounded timeout."""
    env = dict(_BASE_ENV)
    if confirm:
        env["OPS_APPLY_CONFIRM"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(SYNC), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def snapshot(root):
    """Content of every file under root, keyed by path relative to root."""
    root = Path(root)
    if not root.is_dir():
        return {}
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


ARTIFACT_FILES = {
    "pipeline.example.json": '{"board": "demo"}\n',
    "wrapper.example.sh": "#!/usr/bin/env bash\necho demo\n",
    "board/graph.example.json": '{"nodes": []}\n',
}


def build(tmp_path, live_files=None, artifact_files=None, allowlist_lines=()):
    """Build a repo/live/allowlist trio under tmp_path.

    live_files/artifact_files map relative path -> text. Omitted means "the same as
    the vendored artifacts" (i.e. in sync).
    """
    artifacts = tmp_path / "repo" / "ops" / "artifacts"
    artifacts.mkdir(parents=True)
    for rel, text in (ARTIFACT_FILES if artifact_files is None else artifact_files).items():
        write(artifacts / rel, text, mode=0o755 if rel.endswith(".sh") else 0o644)

    live = tmp_path / "live"
    live.mkdir(parents=True)
    for rel, text in (ARTIFACT_FILES if live_files is None else live_files).items():
        write(live / rel, text)

    allowlist = tmp_path / "repo" / "ops" / "state-allowlist.txt"
    write(allowlist, "".join(line + "\n" for line in allowlist_lines))

    return SimpleNamespace(
        tmp=tmp_path, artifacts=artifacts, live=live, allowlist=allowlist,
    )


def base_args(tree):
    """--repo/--live flags, plus the allowlist via its env-only knob."""
    return ["--repo", str(tree.tmp / "repo"), "--live", str(tree.live)], {
        "OPS_ALLOWLIST": str(tree.allowlist)
    }


# --- loud enumeration -------------------------------------------------------


def test_absent_artifact_root_fails_loudly(tmp_path):
    """AC-OPS-001: absent artifact root → non-zero exit and no success line."""
    tree = build(tmp_path)
    tree.artifacts.rename(tmp_path / "moved-away")
    args, extra = base_args(tree)

    check = run_sync(["--check", *args], extra_env=extra)
    assert check.returncode != 0, check.stdout
    assert SUCCESS_LINE not in check.stdout
    assert "artifact root" in (check.stdout + check.stderr)

    apply = run_sync(["--apply", *args], confirm=True, extra_env=extra)
    assert apply.returncode != 0, apply.stdout
    assert SUCCESS_LINE not in apply.stdout
    assert snapshot(tree.live) == snapshot(tree.live)  # nothing was touched


def test_empty_artifact_root_fails_loudly(tmp_path):
    """AC-OPS-002: empty artifact root → non-zero exit, no success line (no-op guard)."""
    tree = build(tmp_path, artifact_files={}, live_files={})   # both sides empty
    args, extra = base_args(tree)

    check = run_sync(["--check", *args], extra_env=extra)
    assert check.returncode != 0, check.stdout
    assert SUCCESS_LINE not in check.stdout
    assert "zero files" in (check.stdout + check.stderr)

    # A green success line over a copy that deployed nothing is the failure class this
    # guards: --apply must not report success, and must not create anything.
    before = snapshot(tree.live)
    apply = run_sync(["--apply", *args], confirm=True, extra_env=extra)
    assert apply.returncode != 0, apply.stdout
    assert SUCCESS_LINE not in apply.stdout
    assert snapshot(tree.live) == before == {}


# --- --check, both directions -----------------------------------------------


def test_check_in_sync_is_clean(tmp_path):
    """AC-OPS-003: --check on identical trees → exit 0 and no drift reported."""
    tree = build(tmp_path)
    args, extra = base_args(tree)

    result = run_sync(["--check", *args], extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRIFT" not in result.stdout
    assert "in sync, no drift" in result.stdout
    # The run is self-describing: it prints the resolution it used.
    assert str(tree.artifacts) in result.stdout
    assert str(tree.live) in result.stdout
    assert str(tree.allowlist) in result.stdout


def test_check_reports_drifted_live_file(tmp_path):
    """AC-OPS-004: --check with a drifted live file → non-zero and the file is named."""
    tree = build(tmp_path)
    write(tree.live / "pipeline.example.json", '{"board": "edited-on-the-live-side"}\n')
    args, extra = base_args(tree)

    result = run_sync(["--check", *args], extra_env=extra)
    assert result.returncode != 0
    assert "pipeline.example.json" in result.stdout
    assert "differ" in result.stdout
    # Read-only: the drift report changed nothing.
    assert (tree.live / "pipeline.example.json").read_text() == \
        '{"board": "edited-on-the-live-side"}\n'
    assert SUCCESS_LINE not in result.stdout


def test_check_reports_live_only_file(tmp_path):
    """AC-OPS-005: --check reports a live-only file with no vendored counterpart."""
    tree = build(tmp_path)
    write(tree.live / "stray-settings.json", '{"nobody": "vendored me"}\n')
    args, extra = base_args(tree)

    result = run_sync(["--check", *args], extra_env=extra)
    assert result.returncode != 0
    assert "stray-settings.json" in result.stdout
    assert "no vendored counterpart" in result.stdout


def test_check_excuses_allowlisted_runtime_state(tmp_path):
    """AC-OPS-006: an allowlisted live-only generated file is excused, both directions."""
    tree = build(tmp_path)
    generated = write(tree.live / "board" / "run-manifest.json", '{"run": 1, "generated": true}\n')
    write(tree.allowlist, "# generated by the scheduler\n*-manifest.json\n")
    args, extra = base_args(tree)

    result = run_sync(["--check", *args], extra_env=extra)
    assert result.returncode == 0, result.stdout
    assert "run-manifest.json" not in result.stdout

    # Same exclusion, other direction: vendoring a generated file is a classification
    # bug, so --check flags it and --apply refuses before writing anything.
    write(tree.artifacts / "board" / "run-manifest.json", '{"run": 0, "stale": true}\n')
    flagged = run_sync(["--check", *args], extra_env=extra)
    assert flagged.returncode != 0
    assert "run-manifest.json" in flagged.stdout

    before = snapshot(tree.live)
    applied = run_sync(["--apply", *args], confirm=True, extra_env=extra)
    assert applied.returncode != 0, applied.stdout
    assert SUCCESS_LINE not in applied.stdout
    assert snapshot(tree.live) == before
    assert generated.read_text() == '{"run": 1, "generated": true}\n'   # not clobbered


# --- --apply ----------------------------------------------------------------


def test_apply_without_confirmation_refuses_and_writes_nothing(tmp_path):
    """AC-OPS-007: --apply without OPS_APPLY_CONFIRM=1 → non-zero, refuses, writes nothing."""
    tree = build(tmp_path, live_files={})
    args, extra = base_args(tree)

    result = run_sync(["--apply", *args], confirm=False, extra_env=extra)
    assert result.returncode != 0
    assert "OPS_APPLY_CONFIRM=1" in (result.stdout + result.stderr)
    assert SUCCESS_LINE not in result.stdout
    assert snapshot(tree.live) == {}          # nothing was written
    assert list(tree.live.iterdir()) == []


def test_apply_deploys_artifacts_and_preserves_live_only_state(tmp_path):
    """AC-OPS-008: --apply with the confirmation set copies artifacts and prints success."""
    tree = build(tmp_path, live_files={"board/run-manifest.json": '{"run": 7}\n'},
                 allowlist_lines=["*-manifest.json"])
    args, extra = base_args(tree)

    result = run_sync(["--apply", *args], confirm=True, extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert SUCCESS_LINE in result.stdout
    assert "deployed 3 artifact(s)" in result.stdout

    for rel, text in ARTIFACT_FILES.items():
        assert (tree.live / rel).read_text() == text, rel
    # Live-only generated state is not --apply's to touch.
    assert (tree.live / "board" / "run-manifest.json").read_text() == '{"run": 7}\n'
    # A wrapper deployed with cp -p stays executable.
    assert os.access(tree.live / "wrapper.example.sh", os.X_OK)


def test_apply_deploys_through_a_symlinked_live_root(tmp_path):
    """AC-OPS-009: a symlinked deploy root is deployed THROUGH, not skipped."""
    tree = build(tmp_path)
    real = tmp_path / "real-live"
    real.mkdir()
    link = tmp_path / "linked-live"
    link.symlink_to(real, target_is_directory=True)

    args = ["--repo", str(tree.tmp / "repo"), "--live", str(link)]
    extra = {"OPS_ALLOWLIST": str(tree.allowlist)}

    check = run_sync(["--check", *args], extra_env=extra)
    assert check.returncode != 0            # nothing deployed through the link yet
    assert "pipeline.example.json" in check.stdout

    result = run_sync(["--apply", *args], confirm=True, extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert SUCCESS_LINE in result.stdout

    for rel, text in ARTIFACT_FILES.items():
        via_link = link / rel
        assert via_link.is_file(), rel
        assert via_link.read_text() == text, rel
        assert (real / rel).is_file(), rel   # the bytes landed past the link
        assert (real / rel).read_text() == text, rel

    # And --check now agrees through the link.
    assert run_sync(["--check", *args], extra_env=extra).returncode == 0


def test_subprocess_calls_are_bounded():
    """AC-OPS-010: every sync invocation in this module carries a timeout."""
    default = inspect.signature(run_sync).parameters["timeout"].default
    assert default == TIMEOUT
    assert 0 < TIMEOUT <= 30, "keep the tier fast; these are file-copy runs"

    # By construction: every subprocess.run call in this module — the helper's, and any a
    # future test adds — must pass timeout=. Parsed as an AST so a mention of the call in
    # a comment or docstring cannot satisfy the check.
    calls = [
        node
        for node in ast.walk(ast.parse(Path(__file__).read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and getattr(node.func.value, "id", "") == "subprocess"
    ]
    assert calls, "expected the subprocess.run call site"
    for call in calls:
        assert any(kw.arg == "timeout" for kw in call.keywords), ast.dump(call)
