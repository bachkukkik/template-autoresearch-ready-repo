"""Integration tier — bearer auth on the REST + MCP surface. IDs: AC-MCP-221..223.

Auth-enabled module-scoped subprocess (AUTH_BEARER_TOKEN=test-token). SC6:
bearer token required on REST and MCP; unauthenticated requests get 401;
/health stays unauthenticated (covered by AC-MCP-211).

NOTE (implementation truth): the service has no ``GET /api/v1/research`` list
route — that exact path returns 405 with or without a token, so the
unauthorized/authorized GET cases are exercised on the real job-id
sub-resource ``GET /api/v1/research/{job_id}``, where the auth dependency
fires before the 404 lookup. AC-MCP-221 asserts 401 there; AC-MCP-222 asserts
a 200 JSON job body there.
"""
import os
import signal
import subprocess
import time
import urllib.request

import httpx
import pytest

BASE_URL = "http://127.0.0.1:18000"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE_DIR = os.path.join(REPO_ROOT, "service")
TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    """Start the auth-enabled service in a subprocess, yield, then stop it."""
    db_path = tmp_path_factory.mktemp("jobs") / "jobs.db"
    env = dict(os.environ)
    venv_bin = os.path.join(SERVICE_DIR, ".venv", "bin")
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    env.update(
        {
            "PORT": "18000",
            "AUTH_BEARER_TOKEN": TOKEN,
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


def test_get_research_without_token_returns_401(service):
    """AC-MCP-221: GET on the research resource without a token -> 401.

    The auth dependency runs before the job-id lookup, so an unknown id with
    no token is 401 (not 404).
    """
    resp = httpx.get(f"{BASE_URL}/api/v1/research/deadbeef", timeout=10)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "unauthorized"


def test_get_research_with_token_returns_valid_json(service):
    """AC-MCP-222: GET on the research resource with the bearer token -> 200."""

    def create_job():
        resp = httpx.post(
            f"{BASE_URL}/api/v1/research",
            headers=AUTH_HEADERS,
            json={"topic": "auth topic"},
            timeout=10,
        )
        assert resp.status_code == 202
        return resp.json()["id"]

    def poll_completed(job_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            resp = httpx.get(
                f"{BASE_URL}/api/v1/research/{job_id}",
                headers=AUTH_HEADERS,
                timeout=10,
            )
            assert resp.status_code == 200
            if resp.json()["status"] == "completed":
                return resp.json()
            time.sleep(0.5)
        raise AssertionError(f"job {job_id} did not complete within 30s")

    job_id = create_job()
    resp = httpx.get(
        f"{BASE_URL}/api/v1/research/{job_id}", headers=AUTH_HEADERS, timeout=10
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == job_id
    assert isinstance(body["topic"], str)
    assert isinstance(body["status"], str)
    assert poll_completed(job_id)["status"] == "completed"


def test_raw_mcp_post_without_token_returns_401(service):
    """AC-MCP-223: raw JSON-RPC POST to /mcp with no Authorization -> 401.

    Exercises the complete ASGI bearer guard: the response is a full 401 JSON
    body, not a start-only reply that would hang the client.
    """
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    resp = httpx.post(f"{BASE_URL}/mcp", json=payload, timeout=10)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "unauthorized"