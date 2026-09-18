"""Unit tier — the service runbook stays real. IDs: AC-MCP-044..045.

PRD-06 SC6 claims `service/README.md` is the agent-facing runbook and names the
sections it must carry. Nothing machine-checked that claim before, so the
runbook could rot (routes, env vars, workspace layout) while every other tier
stayed green. These two tests are that check.

Read-only and stdlib-only: they assert the documented contract, not the prose.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "service" / "README.md"

# PRD-06 SC6 content list -> a distinctive string that must appear.
REQUIRED = {
    "what the service is": "## What this is",
    "how to run it (compose)": "docker compose up",
    "how to run it (uv)": "uv sync",
    "REST surface": "/api/v1",
    "MCP surface": "/mcp",
    "job lifecycle": "## Job lifecycle",
    "concurrency + multi-topic model": "## Multi-topic concurrent research",
    "workspace layout": "## Workspace layout",
    "security": "## Security",
    "update-this-file convention": "## Maintaining this file",
}

# The three env vars PRD-06 introduced must be documented in the runbook.
NEW_ENV_VARS = (
    "RESEARCH_MAX_CONCURRENT_JOBS",
    "RESEARCH_WORKSPACES_DIR",
    "RESEARCH_CORPUS_ROOT",
)


def test_service_runbook_exists():
    """AC-MCP-044: the runbook exists, is non-empty, and declares its scope."""
    assert RUNBOOK.is_file(), "service/README.md is missing (PRD-06 SC6)"
    text = RUNBOOK.read_text()
    assert text.strip(), "service/README.md is empty"
    assert "runbook" in text, "service/README.md no longer declares itself a runbook"


def test_service_runbook_covers_prd06_sc6_sections():
    """AC-MCP-045: every section and env var PRD-06 SC6 names is present."""
    text = RUNBOOK.read_text()
    missing = [name for name, needle in REQUIRED.items() if needle not in text]
    assert missing == [], f"service/README.md is missing PRD-06 SC6 sections: {missing}"
    missing_env = [v for v in NEW_ENV_VARS if v not in text]
    assert missing_env == [], f"service/README.md omits env vars: {missing_env}"
