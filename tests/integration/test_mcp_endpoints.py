"""Integration tier — MCP tools over streamable HTTP. IDs: AC-MCP-201..205.

Same module-scoped subprocess pattern as test_service_endpoints.py, but the
service runs with AUTH_DISABLED=1 (MCP is unauthenticated here by design —
the bearer-guarded MCP surface is covered by AC-MCP-223 in test_auth.py).

FastMCP v4 client notes (verified against the venv's 4.0.3): ``Client`` accepts
a plain URL string, ``list_tools``/``call_tool`` are async and require the
``async with client:`` context manager, and tool results expose the returned
dict under ``CallToolResult.structured_content``.
"""
import asyncio
import os
import signal
import subprocess
import time
import urllib.request

import pytest
from fastmcp import Client

BASE_URL = "http://127.0.0.1:18000"
MCP_URL = f"{BASE_URL}/mcp"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE_DIR = os.path.join(REPO_ROOT, "service")

TOOL_NAMES = {
    "research_start",
    "research_status",
    "research_results",
    "research_cancel",
}


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    """Start the auth-disabled service in a subprocess, yield, then stop it."""
    db_path = tmp_path_factory.mktemp("jobs") / "jobs.db"
    env = dict(os.environ)
    venv_bin = os.path.join(SERVICE_DIR, ".venv", "bin")
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    env.update(
        {
            "PORT": "18000",
            "AUTH_DISABLED": "1",
            "RESEARCH_JOBS_DB": str(db_path),
        }
    )
    proc = subprocess.Popen(
        ["python3", "-m", "src.main"],
        cwd=SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    last_error = None
    try:
        # Wait for /health: retry up to 60 x 0.25s = 15s.
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception as exc:  # server not up yet
                last_error = exc
                time.sleep(0.25)
        else:
            raise AssertionError(
                f"service did not become healthy on {BASE_URL}: {last_error}"
            )
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


async def _start_job(client, topic):
    """Start a research job via MCP; returns the job dict (id, status queued)."""
    res = await client.call_tool("research_start", {"topic": topic})
    assert res.is_error is False
    job = res.structured_content
    assert job["status"] == "queued"
    return job


async def _wait_completed(client, job_id, max_seconds=30):
    """Poll research_status until the job is completed; returns the job dict."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        res = await client.call_tool("research_status", {"job_id": job_id})
        job = res.structured_content
        if job["status"] == "completed":
            return job
        await asyncio.sleep(0.5)
    raise AssertionError(f"job {job_id} did not complete within {max_seconds}s")


def test_mcp_lists_all_four_tools(service):
    """AC-MCP-201: list_tools includes research_start/status/results/cancel."""

    async def check():
        async with Client(MCP_URL) as client:
            tools = await client.list_tools()
            return {t.name for t in tools}

    names = asyncio.run(check())
    assert TOOL_NAMES <= names


def test_mcp_research_start_returns_32_hex_job_id(service):
    """AC-MCP-202: research_start returns a job dict with a 32-char id."""

    async def check():
        async with Client(MCP_URL) as client:
            return await _start_job(client, "mcp start")

    job = asyncio.run(check())
    assert job["id"]
    assert len(job["id"]) == 32
    assert job["status"] == "queued"
    assert job["result"] is None


def test_mcp_research_status_polls_to_completed(service):
    """AC-MCP-203: research_status reaches completed with val_bpb present."""

    async def check():
        async with Client(MCP_URL) as client:
            job = await _start_job(client, "mcp poll")
            return await _wait_completed(client, job["id"])

    job = asyncio.run(check())
    assert job["status"] == "completed"
    assert job["result"] is not None
    assert "val_bpb" in job["result"]
    assert isinstance(job["result"]["val_bpb"], (int, float)) and not isinstance(
        job["result"]["val_bpb"], bool
    )


def test_mcp_research_results_returns_result(service):
    """AC-MCP-204: research_results returns the job with its run report."""

    async def check():
        async with Client(MCP_URL) as client:
            job = await _start_job(client, "mcp results")
            await _wait_completed(client, job["id"])
            res = await client.call_tool("research_results", {"job_id": job["id"]})
            return res.structured_content

    job = asyncio.run(check())
    assert job["status"] == "completed"
    assert isinstance(job["result"], dict)
    assert "val_bpb" in job["result"]


def test_mcp_research_cancel_returns_cancelled(service):
    """AC-MCP-205: research_cancel on a fresh job reports status cancelled."""

    async def check():
        async with Client(MCP_URL) as client:
            job = await _start_job(client, "mcp cancel")
            res = await client.call_tool("research_cancel", {"job_id": job["id"]})
            return res.structured_content

    job = asyncio.run(check())
    assert job["id"]
    assert job["status"] == "cancelled"