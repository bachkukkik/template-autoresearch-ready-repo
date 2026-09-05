"""Unit tier — dual-exposure routing (REST + MCP surface). IDs: AC-MCP-001..006.

Contract (PRD-05 SC1): one ASGI app serves REST under /api/v1 and MCP
streamable HTTP at /mcp; each operation handler is defined once and reachable
both ways; /health is a REST-only probe and is never a tool.

Note: importing ``src.main`` runs ``create_app()`` at module level, so a
throwaway ``RESEARCH_JOBS_DB`` is pointed at a temp dir BEFORE the import to
keep the repo root free of stray SQLite files.
"""
import asyncio
import os
import tempfile

_TEST_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="ar-unit-routes-"), "jobs.db")
os.environ["RESEARCH_JOBS_DB"] = _TEST_DB_PATH

from fastapi.testclient import TestClient  # noqa: E402

from src import main  # noqa: E402
from src.jobs import JobStore  # noqa: E402


def test_app_exposes_rest_and_mcp_surface():
    """AC-MCP-001: create_app() builds an app exposing POST /api/v1/research
    and the /mcp surface (the FastMCP streamable-HTTP route is spliced in)."""
    app = main.create_app()
    routes = {(m, r.path) for r in app.routes for m in (r.methods or [])}
    assert ("POST", "/api/v1/research") in routes
    assert ("GET", "/api/v1/research/{job_id}") in routes
    assert ("GET", "/api/v1/research/{job_id}/results") in routes
    assert ("DELETE", "/api/v1/research/{job_id}") in routes
    assert any(path == "/mcp" for _, path in routes)


def test_health_not_a_tool_while_research_start_is():
    """AC-MCP-002: /health is never registered as an MCP tool, while
    research_start (and the other flagged operations) are — verified against
    the module-level FastMCP tool registry."""
    tools = asyncio.run(main.mcp.list_tools())
    names = {t.name for t in tools}
    assert "research_start" in names
    assert "research_status" in names
    assert "research_results" in names
    assert "research_cancel" in names
    assert "health" not in names
    # registry-level check confirms the tool objects exist / are absent
    assert asyncio.run(main.mcp.get_tool("research_start")) is not None
    assert asyncio.run(main.mcp.get_tool("health")) is None


def test_research_without_auth_returns_401(monkeypatch):
    """AC-MCP-003: POST /api/v1/research without a bearer header is rejected
    with 401 when auth is enabled (fail closed); the same request WITH the
    token passes — proving the Authorization header is actually bound."""
    import src.auth as auth

    monkeypatch.setattr(auth, "AUTH_TOKEN", "test-token")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)

    with TestClient(main.app) as client:
        denied = client.post("/api/v1/research", json={"topic": "t"})
        assert denied.status_code == 401
        assert denied.json()["detail"] == "unauthorized"

        allowed = client.post(
            "/api/v1/research",
            json={"topic": "t"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert allowed.status_code == 202
        assert len(allowed.json()["id"]) == 32


def test_route_to_operation_mapping_covers_all_operations():
    """AC-MCP-004: ROUTE_TO_OPERATION maps every HTTP route to its operation —
    start/status/results/cancel are all covered (and nothing else)."""
    assert main.ROUTE_TO_OPERATION == {
        ("POST", "/api/v1/research"): "research_start",
        ("GET", "/api/v1/research/{job_id}"): "research_status",
        ("GET", "/api/v1/research/{job_id}/results"): "research_results",
        ("DELETE", "/api/v1/research/{job_id}"): "research_cancel",
    }
    assert set(main.ROUTE_TO_OPERATION.values()) == {
        "research_start",
        "research_status",
        "research_results",
        "research_cancel",
    }


def test_job_id_is_uuid4_hex(tmp_path):
    """AC-MCP-005: a job id from JobStore.create_job is uuid4 hex — 32 chars,
    valid hex digits, unique across jobs."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        first = store.create_job("t", {})
        second = store.create_job("t", {})
        for job in (first, second):
            assert len(job["id"]) == 32
            int(job["id"], 16)  # valid hex; raises ValueError otherwise
        assert first["id"] != second["id"]
    finally:
        store.close()


def test_tool_flag_defaults():
    """AC-MCP-006: TOOL_FLAG defaults are True for the research operations and
    False for health — health is REST-only by construction."""
    assert main.TOOL_FLAG == {
        "research_start": True,
        "research_status": True,
        "research_results": True,
        "research_cancel": True,
        "health": False,
    }