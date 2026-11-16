"""Unit tier — compose host-port contract. IDs: AC-MCP-047, AC-MCP-048.

Hermetic: `git ls-files` plus file reads — no docker, no network, no service
import. The subjects are the tracked compose files and the tracked `.gitignore`.

This template is cloned to start many projects, and several derived projects may
share one Docker host. A tracked host port therefore collides. Host access stays
a per-deployment opt-in through the gitignored `docker-compose.override.yml`
(PRD-01 SC6; `docs/05-mcp-rest-service.md`). The pathspec recurses, so a compose
file committed in a subdirectory is caught as well as the repo-root one.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

UNTRACKED_OPT_IN = "docker-compose.override.yml"


def _tracked_compose_files():
    """Every tracked compose file, via a recursive `git ls-files` pathspec."""
    result = subprocess.run(
        ["git", "ls-files", ":(glob)**/docker-compose*.yml"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`git ls-files` failed in {REPO_ROOT}: {result.stderr.strip()}"
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert files, (
        "no tracked compose files found — `git ls-files "
        "':(glob)**/docker-compose*.yml'` returned nothing in "
        f"{REPO_ROOT}"
    )
    return files


def _ports_mappings(text):
    """Line numbers whose stripped content opens a `ports:` mapping."""
    return [
        number
        for number, line in enumerate(text.splitlines(), 1)
        if not line.strip().startswith("#") and line.strip().startswith("ports:")
    ]


def test_ac_mcp_047_no_tracked_compose_file_binds_a_host_port():
    """AC-MCP-047: no tracked compose file carries a `ports:` mapping."""
    files = _tracked_compose_files()
    assert "docker-compose.yml" in files, (
        f"the base compose file is not in the tracked set: {files}"
    )
    violations = []
    for name in files:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        violations.extend(f"{name}:{number}" for number in _ports_mappings(text))
    assert not violations, (
        f"a `ports:` mapping is tracked in: {violations} — host port binding is "
        f"opt-in via a gitignored {UNTRACKED_OPT_IN}, never tracked (AC-MCP-047)"
    )


def test_ac_mcp_048_override_path_is_gitignored():
    """AC-MCP-048: the documented host-port opt-in path stays gitignored."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored = any(
        line.strip() == UNTRACKED_OPT_IN or line.strip().startswith(UNTRACKED_OPT_IN)
        for line in text.splitlines()
    )
    assert ignored, (
        f"`.gitignore` does not ignore {UNTRACKED_OPT_IN} — the documented "
        "host-port opt-in path must stay gitignored, or a derived deployment's "
        "port mapping leaks into the template (AC-MCP-048)"
    )
