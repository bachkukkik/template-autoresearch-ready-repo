"""Integration tier — concurrent multi-topic research over the live service. IDs: AC-MCP-231..233.

One module-scoped subprocess running the actual service (uvicorn via
``src.main``) on PORT 18001 with bearer auth enabled (AUTH_BEARER_TOKEN),
a tmp SQLite database, a tmp workspaces root (so nothing is ever written
into the repo's data/ dir), and RESEARCH_CORPUS_ROOT pointing at the repo's
kb/raw. Every test talks to that live process over HTTP — no mocks, no
in-process app.

PRD-06 SC2/SC3/SC5: two topics with distinct inline corpora complete
concurrently with distinct results (AC-MCP-231); corpus files resolve under
the corpus root (AC-MCP-232); a missing corpus file is rejected fail-fast
with a 400 at submit (AC-MCP-233).

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

BASE_URL = "http://127.0.0.1:18001"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE_DIR = os.path.join(REPO_ROOT, "service")
CORPUS_ROOT = os.path.join(REPO_ROOT, "kb", "raw")
TOKEN = "test-token"
AUTH_HEADER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    """Start the auth-enabled service in a subprocess, yield, then stop it."""
    db_path = tmp_path_factory.mktemp("jobs") / "jobs.db"
    workspaces_dir = tmp_path_factory.mktemp("workspaces")
    env = dict(os.environ)
    venv_bin = os.path.join(SERVICE_DIR, ".venv", "bin")
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    env.update(
        {
            "PORT": "18001",
            "AUTH_BEARER_TOKEN": TOKEN,
            "RESEARCH_JOBS_DB": str(db_path),
            # Hermetic PRD-06 isolation: workspaces live in the tmp run,
            # never in the repo's data/ dir; corpus files resolve under kb/raw.
            "RESEARCH_WORKSPACES_DIR": str(workspaces_dir),
            "RESEARCH_CORPUS_ROOT": CORPUS_ROOT,
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


def _post_research(topic, texts=None, files=None):
    """POST one research job with the given inline corpus (texts and/or files)."""
    params = {}
    if texts is not None:
        params["corpus"] = {"texts": texts}
    elif files is not None:
        params["corpus"] = {"files": files}
    body = {"topic": topic}
    if params:
        body["params"] = params
    return _request("POST", "/api/v1/research", headers=AUTH_HEADER, body=body)


def test_two_topics_run_concurrently_with_distinct_results(service):
    """AC-MCP-231 (SC2+SC3): two topics, distinct inline corpora, both complete.

    POST two research jobs with DIFFERENT topics and DIFFERENT inline corpus
    texts (topic1: 1 text; topic2: 2 texts), then poll both to completion.
    Each result echoes its own topic and reports its own corpus file counts
    (1 and 2 respectively) with a numeric val_bpb — proving topic wiring and
    per-job workspace isolation over the live service.
    """
    topic1 = "multi-topic alpha"
    topic2 = "multi-topic beta"
    texts1 = [{"title": "alpha source", "content": "First inline corpus text."}]
    texts2 = [
        {"title": "beta source one", "content": "Second inline corpus text."},
        {"title": "beta source two", "content": "Third inline corpus text."},
    ]

    status1, job1 = _post_research(topic1, texts=texts1)
    status2, job2 = _post_research(topic2, texts=texts2)
    assert status1 == 202 and job1["status"] == "queued"
    assert status2 == 202 and job2["status"] == "queued"
    assert job1["id"] != job2["id"]

    done1 = _wait_completed(job1["id"])
    done2 = _wait_completed(job2["id"])

    # Topic wiring: each job's result echoes ITS OWN topic, and they differ.
    assert done1["result"]["topic"] == topic1
    assert done2["result"]["topic"] == topic2
    assert done1["result"]["topic"] != done2["result"]["topic"]

    # Corpus stats follow each job's own inline corpus (1 vs 2 files).
    assert done1["result"]["corpus"]["files"] == 1
    assert done2["result"]["corpus"]["files"] == 2
    assert done1["result"]["corpus"]["chars"] > 0
    assert done2["result"]["corpus"]["chars"] > 0

    # Both completed with a real numeric val_bpb (canonical contract ~3.7).
    for done in (done1, done2):
        val_bpb = done["result"]["val_bpb"]
        assert isinstance(val_bpb, (int, float)) and not isinstance(val_bpb, bool)
        assert val_bpb > 0


def test_corpus_file_from_transcripts_resolves_under_corpus_root(service):
    """AC-MCP-232 (SC2 files): a real kb/raw/transcripts file as the corpus.

    POST a job whose corpus is a single file path relative to
    RESEARCH_CORPUS_ROOT; it must complete with corpus {'files': 1,
    'chars': >0} and echo the topic.
    """
    topic = "file-based topic"
    status, job = _post_research(
        topic, files=["transcripts/ZhMGNlCU4qc.txt"]
    )
    assert status == 202 and job["status"] == "queued"

    done = _wait_completed(job["id"])
    assert done["status"] == "completed"
    result = done["result"]
    assert result["topic"] == topic
    assert result["corpus"]["files"] == 1
    assert result["corpus"]["chars"] > 0
    val_bpb = result["val_bpb"]
    assert isinstance(val_bpb, (int, float)) and not isinstance(val_bpb, bool)
    assert val_bpb > 0


def test_missing_corpus_file_fails_fast_with_400(service):
    """AC-MCP-233 (SC5 fail-fast): a missing corpus file -> 400 at submit.

    The job must be rejected with HTTP 400 and detail
    'corpus file not found: transcripts/does-not-exist.txt' — never queued,
    never discovered mid-run.
    """
    missing = "transcripts/does-not-exist.txt"
    status, body = _post_research("doomed topic", files=[missing])
    assert status == 400
    assert body.get("detail") == f"corpus file not found: {missing}"