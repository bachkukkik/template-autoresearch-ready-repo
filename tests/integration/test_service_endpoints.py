"""Integration tier — the real service over a real socket. IDs: AC-MCP-211..215.

One module-scoped subprocess running the actual service (uvicorn via
``src.main``) on PORT 18000 with bearer auth enabled (AUTH_BEARER_TOKEN);
the run's SQLite database lives in a per-session tmp dir. Every test talks
to that live process over HTTP — no mocks, no in-process app.

The ``python3`` in the subprocess resolves to the checked-in service venv by
prepending its bin/ to PATH (system python3 has no service deps installed).
"""
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request

import pytest

BASE_URL = "http://127.0.0.1:18000"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE_DIR = os.path.join(REPO_ROOT, "service")
TOKEN = "test-token"
AUTH_HEADER = {"Authorization": f"Bearer {TOKEN}"}


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


def _request(method, path, headers=None, body=None):
    """HTTP helper returning (status, parsed json body)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, headers=headers or {}, method=method
    )
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _wait_completed(job_id, max_seconds=30):
    """Poll GET /api/v1/research/<id> until the job is completed."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        status, body = _request(
            "GET", f"/api/v1/research/{job_id}", headers=AUTH_HEADER
        )
        assert status == 200
        if body["status"] == "completed":
            return body
        time.sleep(0.5)
    raise AssertionError(f"job {job_id} did not complete within {max_seconds}s")


def test_health_is_open_and_ok_without_auth(service):
    """AC-MCP-211: /health returns 200 {status: ok} with no token."""
    status, body = _request("GET", "/health")
    assert status == 200
    assert body == {"status": "ok"}


def test_research_lifecycle_over_rest(service):
    """AC-MCP-212: POST 202 + job id; poll GET until completed; val_bpb numeric."""
    status, job = _request(
        "POST", "/api/v1/research", headers=AUTH_HEADER, body={"topic": "rest topic"}
    )
    assert status == 202
    job_id = job["id"]
    assert job_id and job["status"] == "queued"

    done = _wait_completed(job_id)
    assert done["status"] == "completed"
    assert done["result"] is not None
    val_bpb = done["result"]["val_bpb"]
    assert isinstance(val_bpb, (int, float)) and not isinstance(val_bpb, bool)


def test_post_without_token_returns_401(service):
    """AC-MCP-213: POST /api/v1/research with no Authorization header -> 401."""
    status, body = _request(
        "POST", "/api/v1/research", body={"topic": "nope"}
    )
    assert status == 401
    assert body.get("detail") == "unauthorized"


def test_unknown_job_id_returns_404(service):
    """AC-MCP-214: GET an unknown job id with a valid token -> 404."""
    status, _ = _request("GET", "/api/v1/research/deadbeef", headers=AUTH_HEADER)
    assert status == 404


def test_delete_cancels_a_fresh_job(service):
    """AC-MCP-215: DELETE /api/v1/research/<id> with token -> 200 cancelled."""
    status, job = _request(
        "POST", "/api/v1/research", headers=AUTH_HEADER, body={"topic": "cancelled"}
    )
    assert status == 202
    job_id = job["id"]

    status, cancelled = _request("DELETE", f"/api/v1/research/{job_id}", headers=AUTH_HEADER)
    assert status == 200
    assert cancelled["id"] == job_id
    assert cancelled["status"] == "cancelled"