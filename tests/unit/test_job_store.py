"""Unit tier — durable SQLite job store. IDs: AC-MCP-011..014, AC-SVC-006.

Contract (PRD-05 SC4): job-id/poll over a durable SQLite store that survives a
service restart, with idempotent dispatch via an explicit idempotency_key.
AC-SVC-006 (PRD-24 SC7) pins the store's path: a relative RESEARCH_JOBS_DB
resolves against the service root, and a blank one is unset, never the root.
"""
import os
import threading
from pathlib import Path

import pytest

from autoresearch_service import jobs
from autoresearch_service.jobs import JobStore

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_create_job_roundtrip(tmp_path):
    """AC-MCP-011: create_job returns a queued job; get_job roundtrips it."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        job = store.create_job("test topic", {"budget": 5})
        assert job["id"]
        assert job["status"] == "queued"
        assert job["topic"] == "test topic"
        assert job["params"] == {"budget": 5}
        assert job["error"] is None
        assert job["result"] is None
        assert job["created_at"] and job["updated_at"]
        assert store.get_job(job["id"]) == job
    finally:
        store.close()


def test_get_job_missing_returns_none(tmp_path):
    """get_job on an unknown id returns None, not an exception."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        assert store.get_job("no-such-job") is None
    finally:
        store.close()


def test_idempotency_key_returns_existing_job(tmp_path):
    """AC-MCP-012: duplicate idempotency_key returns the existing job, same id."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        first = store.create_job("topic-a", {"a": 1}, idempotency_key="key-1")
        second = store.create_job("topic-b", {"b": 2}, idempotency_key="key-1")
        assert second["id"] == first["id"]
        assert second["topic"] == "topic-a"
        assert second["params"] == {"a": 1}
        assert second["created_at"] == first["created_at"]
    finally:
        store.close()


def test_different_idempotency_keys_create_distinct_jobs(tmp_path):
    """Distinct idempotency keys are separate jobs."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        a = store.create_job("t", {}, idempotency_key="k-a")
        b = store.create_job("t", {}, idempotency_key="k-b")
        assert a["id"] != b["id"]
    finally:
        store.close()


def test_jobs_without_idempotency_key_are_distinct(tmp_path):
    """Omitting idempotency_key never dedupes — every call is a new job."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        a = store.create_job("t", {})
        b = store.create_job("t", {})
        assert a["id"] != b["id"]
    finally:
        store.close()


def test_status_transition_chain(tmp_path):
    """AC-MCP-013: queued -> running -> completed; each step persists."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        job = store.create_job("t", {})
        job_id = job["id"]
        assert job["status"] == "queued"

        running = store.set_status(job_id, "running")
        assert running["status"] == "running"

        done = store.set_status(job_id, "completed")
        assert done["status"] == "completed"
        assert store.get_job(job_id)["status"] == "completed"
    finally:
        store.close()


def test_status_transition_to_failed_and_cancelled(tmp_path):
    """running -> failed and running -> cancelled are legal; error is recorded."""
    db = str(tmp_path / "jobs.db")
    store = JobStore(db)
    try:
        job = store.create_job("t", {})
        store.set_status(job["id"], "running")
        failed = store.set_status(job["id"], "failed", error="boom")
        assert failed["status"] == "failed"
        assert failed["error"] == "boom"

        job2 = store.create_job("t", {})
        store.set_status(job2["id"], "running")
        cancelled = store.set_status(job2["id"], "cancelled")
        assert cancelled["status"] == "cancelled"
        assert cancelled["error"] is None
    finally:
        store.close()


def test_queued_to_cancelled_transition(tmp_path):
    """AC-MCP-014: a queued job can be cancelled before it starts."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        job = store.create_job("t", {})
        job_id = job["id"]
        assert job["status"] == "queued"

        cancelled = store.set_status(job_id, "cancelled")
        assert cancelled["status"] == "cancelled"
        assert store.get_job(job_id)["status"] == "cancelled"
    finally:
        store.close()


def test_illegal_status_transitions_raise(tmp_path):
    """Skipped and unknown transitions raise ValueError and leave state intact."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        job = store.create_job("t", {})
        job_id = job["id"]
        with pytest.raises(ValueError):
            store.set_status(job_id, "completed")  # queued -> completed: skip
        with pytest.raises(ValueError):
            store.set_status(job_id, "bogus")
        # state unchanged after rejected transitions
        assert store.get_job(job_id)["status"] == "queued"

        store.set_status(job_id, "running")
        with pytest.raises(ValueError):
            store.set_status(job_id, "queued")  # running -> queued: illegal
        with pytest.raises(ValueError):
            store.set_status(job_id, "running")  # running -> running: no-op, illegal

        store.set_status(job_id, "completed")
        with pytest.raises(ValueError):
            store.set_status(job_id, "failed")  # completed is terminal
    finally:
        store.close()


def test_set_result_merges(tmp_path):
    """set_result merges into prior results instead of replacing them."""
    store = JobStore(str(tmp_path / "jobs.db"))
    try:
        job = store.create_job("t", {})
        store.set_result(job["id"], {"val_bpb": 1.23})
        store.set_result(job["id"], {"steps": 500})
        assert store.get_job(job["id"])["result"] == {"val_bpb": 1.23, "steps": 500}
    finally:
        store.close()


def test_job_and_result_survive_reopen(tmp_path):
    """AC-MCP-013: full lifecycle persists across a NEW JobStore on the same db_path."""
    db_path = str(tmp_path / "jobs.db")
    store = JobStore(db_path)
    try:
        job = store.create_job("durable topic", {"budget": 3}, idempotency_key="dup-1")
        job_id = job["id"]
        store.set_status(job_id, "running")
        store.set_result(job_id, {"val_bpb": 0.5, "keep": True})
        store.set_status(job_id, "completed")
    finally:
        store.close()

    store2 = JobStore(db_path)  # simulates a service restart
    try:
        reopened = store2.get_job(job_id)
        assert reopened is not None
        assert reopened["id"] == job_id
        assert reopened["status"] == "completed"
        assert reopened["params"] == {"budget": 3}
        assert reopened["result"] == {"val_bpb": 0.5, "keep": True}
        # idempotency constraint is durable too
        dup = store2.create_job("other", {}, idempotency_key="dup-1")
        assert dup["id"] == job_id
    finally:
        store2.close()


def test_db_path_from_env_var(tmp_path, monkeypatch):
    """db_path defaults to RESEARCH_JOBS_DB when set."""
    monkeypatch.setenv("RESEARCH_JOBS_DB", str(tmp_path / "env-jobs.db"))
    store = JobStore()  # no explicit path -> env var
    try:
        assert store.db_path == str(tmp_path / "env-jobs.db")
        job = store.create_job("t", {})
        assert store.get_job(job["id"])["id"] == job["id"]
    finally:
        store.close()


def test_db_path_fallback_is_service_data(tmp_path, monkeypatch):
    """db_path falls back to autoresearch/service/data/jobs.db (service root, not cwd)."""
    monkeypatch.delenv("RESEARCH_JOBS_DB", raising=False)
    assert jobs.DEFAULT_DB_PATH == str(
        REPO_ROOT / "autoresearch" / "service" / "data" / "jobs.db"
    )

    # The parent-directory creation is exercised against a temp path so the test
    # never writes into the tracked tree.
    monkeypatch.setattr(jobs, "DEFAULT_DB_PATH", str(tmp_path / "data" / "jobs.db"))
    monkeypatch.chdir(tmp_path)  # cwd must not decide the fallback
    store = JobStore()
    try:
        assert store.db_path == str(tmp_path / "data" / "jobs.db")
        assert os.path.isdir(tmp_path / "data")
        assert os.path.isfile(tmp_path / "data" / "jobs.db")
    finally:
        store.close()


def test_a_relative_env_db_path_resolves_against_the_service_root(tmp_path, monkeypatch):
    """AC-SVC-006: a *relative* RESEARCH_JOBS_DB is service-root-relative.

    The container (`WORKDIR /app`) and a host shell are two working directories
    for one config: resolving the env value against the process cwd wrote
    `data/jobs.db` beside whichever directory the process started in — one job
    store with two homes. The path is asserted, not opened, so the test never
    writes into the tracked tree.
    """
    monkeypatch.setenv("RESEARCH_JOBS_DB", "data/jobs.db")
    service_data = REPO_ROOT / "autoresearch" / "service" / "data" / "jobs.db"

    other = tmp_path / "somewhere-else"
    other.mkdir()
    monkeypatch.chdir(tmp_path)
    from_tmp = jobs._default_db_path()
    monkeypatch.chdir(other)
    assert jobs._default_db_path() == from_tmp  # cwd does not decide it
    assert from_tmp == str(service_data)

    # An absolute value still wins, untouched.
    monkeypatch.setenv("RESEARCH_JOBS_DB", str(tmp_path / "mine.db"))
    assert jobs._default_db_path() == str(tmp_path / "mine.db")


def test_a_blank_env_db_path_is_unset_not_the_service_root(tmp_path, monkeypatch):
    """AC-SVC-006: `RESEARCH_JOBS_DB=` (or whitespace) is unset.

    Treated as a path, a blank value resolves to the service root itself, so the
    store would land at `autoresearch/service/jobs.db` inside the tracked tree.
    """
    for blank in ("", "   "):
        monkeypatch.setenv("RESEARCH_JOBS_DB", blank)
        monkeypatch.chdir(tmp_path)
        assert jobs._default_db_path() == jobs.DEFAULT_DB_PATH
        assert jobs._default_db_path() != jobs.SERVICE_ROOT


def test_claim_takes_a_queued_job_exactly_once(tmp_path):
    """claim(): True for a queued job once, False for a taken or unknown id.

    Dispatch is idempotent only because of this one guarded UPDATE: the second
    caller gets False and runs nothing, and losing that race is not an error —
    unlike `set_status`, where `running -> running` is an illegal transition.
    """
    store = JobStore(str(tmp_path / "claim.db"))
    try:
        job_id = store.create_job("claimable", {})["id"]

        assert store.claim(job_id) is True
        assert store.get_job(job_id)["status"] == "running"
        assert store.claim(job_id) is False  # already taken
        assert store.claim("no-such-job") is False  # unknown id

        store.set_status(job_id, "completed")
        assert store.claim(job_id) is False  # terminal is not claimable
        assert store.get_job(job_id)["status"] == "completed"  # and is untouched
    finally:
        store.close()


def test_concurrent_access_from_multiple_threads(tmp_path):
    """check_same_thread=False + lock: concurrent create/status/result is safe."""
    store = JobStore(str(tmp_path / "jobs.db"))
    job_ids = []
    lock = threading.Lock()

    def worker(i):
        job = store.create_job(f"t{i}", {"i": i}, idempotency_key=f"k{i}")
        store.set_status(job["id"], "running")
        store.set_result(job["id"], {"i": i})
        store.set_status(job["id"], "completed")
        with lock:
            job_ids.append(job["id"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(job_ids) == 8
    for job_id in job_ids:
        assert store.get_job(job_id)["status"] == "completed"
        assert store.get_job(job_id)["result"] is not None
    store.close()