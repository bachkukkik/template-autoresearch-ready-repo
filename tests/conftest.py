"""Shared fixtures — imports for the tests, plus the ambient-dependency preflight.

The ``sys.path`` block makes the service + contract packages importable. The
preflight below it is this repo's one definition of how a test whose verdict
would otherwise depend on the host (an ambient binary on ``PATH``) decides
whether it can run at all — see AGENTS.md §5.
"""
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Repo root and the contract/ subdir must both be importable so
# `import prepare` / `import train` work from tests/unit/ (autoresearch
# contract files live in contract/).
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
for pkg_dir in ("contract", "service"):
    path = os.path.join(ROOT, pkg_dir)
    if path not in sys.path:
        sys.path.insert(0, path)


def resolve_ambient(tool, *, path=None, probe=None):
    """Resolve ``tool`` the way the code under test resolves it, then interrogate it.

    Returns ``(resolved, reason)``: ``reason`` is ``None`` when the tool is
    usable, otherwise the message naming what was resolved and why it is
    unsuitable. Resolution is ``shutil.which(tool, path=path)`` — the same call
    with the same argument shape the production code makes. ``probe(resolved)``
    is the caller's probe: it returns a reason string when the resolved tool is
    unsuitable and a falsy value when it is fine, so the fixture never invents
    its own notion of "suitable".
    """
    resolved = shutil.which(tool, path=path)
    if resolved is None:
        looked_in = "PATH" if path is None else f"PATH override {path!r}"
        return None, f"ambient tool {tool!r} is not on {looked_in} (shutil.which)"
    if probe is not None:
        why = probe(resolved)
        if why:
            return resolved, (
                f"ambient tool {tool!r} resolved to {resolved!r} but is "
                f"unsuitable — {why}"
            )
    return resolved, None


@pytest.fixture
def require_tool():
    """Preflight for a test whose verdict would otherwise depend on the host.

    (a) Why it exists: a test that shells out to an ambient binary is *green on
    a developer host and red in the runner* (or the reverse), because its
    verdict is a property of whatever is first on ``PATH`` rather than of the
    repo. The three-tier doctrine has no tier for that, so it surfaces as
    "flaky" and gets muted or deleted — worse than the bug.
    (b) It must mirror the production resolution path: it resolves with the same
    ``shutil.which`` call — including the same ``path=`` override when the code
    under test rewrites ``PATH`` — and probes the result with the caller's own
    probe, so the fixture's answer and the code's answer cannot disagree.
    (c) It skips rather than fails: a tool that is absent or unsuitable on this
    host is not a repo defect, so a red tier would only train the reader to
    ignore red. The skip reason always names the tool, the path it resolved to
    and why that resolved tool is unsuitable.

    Usage::

        def test_bats_runner(require_tool):
            def probe(exe):
                version = subprocess.run([exe, "--version"], capture_output=True, text=True)
                return None if version.returncode == 0 else "bats could not report a version"

            bats = require_tool("bats", probe=probe)   # skips if absent/unsuitable
            subprocess.run([bats, "tests/e2e/"], check=True)
    """
    def _require(tool, *, path=None, probe=None):
        resolved, reason = resolve_ambient(tool, path=path, probe=probe)
        if reason:
            pytest.skip(reason)
        return resolved

    return _require


# ─── Integration-tier preflight ──────────────────────────────────────────────
# The integration modules spawn `python3 -m src.main` with service/.venv/bin
# prepended to PATH, so the interpreter that runs the service is ambient. Rather
# than edit four files to request the fixture, the tier gets the same preflight
# once, at collection: the spawn either has the service's deps or the test could
# never pass, so it must skip (naming what was resolved) instead of failing 15s
# later with a service it could not start.
_SERVICE_VENV_BIN = os.path.join(ROOT, "service", ".venv", "bin")
_SERVICE_IMPORTS = "import fastapi, fastmcp, uvicorn"


def _probe_service_python(resolved):
    """Probe: can the interpreter the tier spawns import the service's deps?"""
    try:
        proc = subprocess.run(
            [resolved, "-c", _SERVICE_IMPORTS],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "the probe timed out after 60s"
    if proc.returncode == 0:
        return None
    tail = (proc.stderr or proc.stdout).strip().splitlines()
    return tail[-1] if tail else f"the probe exited {proc.returncode}"


def pytest_collection_modifyitems(config, items):
    """Apply the ambient preflight to the integration tier (see above)."""
    integration = [
        item
        for item in items
        if "/tests/integration/" in str(item.path).replace(os.sep, "/")
    ]
    if not integration:
        return
    _, reason = resolve_ambient(
        "python3",
        path=_SERVICE_VENV_BIN + os.pathsep + os.environ.get("PATH", ""),
        probe=_probe_service_python,
    )
    if reason:
        marker = pytest.mark.skip(reason=f"integration tier ambient preflight: {reason}")
        for item in integration:
            item.add_marker(marker)
