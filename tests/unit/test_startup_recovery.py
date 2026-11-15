"""Unit tier — recovery of jobs a restart left unfinished. ID: AC-SVC-007.

Spec: docs/prd/24-autoresearch-as-a-service.md (SC7).

The `service-data` compose volume keeps `jobs.db` across a restart; the
in-process APScheduler does not. At startup, inside the FastAPI lifespan, a
`queued` job (it never ran) is dispatched again through the SAME path a new job
uses, and a `running` job is moved to `failed` as interrupted rather than
re-run — it may already have had side effects.

Note: importing ``autoresearch_service.main`` runs ``create_app()`` at module
level, so a throwaway ``RESEARCH_JOBS_DB`` is pointed at a temp dir BEFORE the
import (the pattern in ``test_workspace.py``). The scheduler is replaced by a
recorder, so no research ever runs.
"""
import os
import tempfile
import threading

_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="ar-unit-recovery-"), "jobs.db")
os.environ["RESEARCH_JOBS_DB"] = _DB_PATH

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from autoresearch_service import main  # noqa: E402
from autoresearch_service.jobs import JobStore  # noqa: E402

#: The literal the docs quote, restated so the constant cannot drift from it.
INTERRUPTED = "interrupted: the service restarted while this job was running"

#: A run-kind job's params (``policy.validate_run_request`` stamps `kind`).
RUN_PARAMS = {"kind": "run", "workload": "contract", "agent": "replay"}


class _RecordingScheduler:
    """Stand-in for the BackgroundScheduler: records dispatch, runs nothing."""

    def __init__(self):
        self.started = False
        self.dispatched = []

    def start(self):
        self.started = True

    def add_job(self, func, args=None, **kwargs):
        self.dispatched.append((func, tuple(args or ())))

    def shutdown(self, wait=True):
        self.started = False


def _seed(store):
    """One queued research job, one queued run job, one running, one completed."""
    queued = store.create_job("never started", {})
    queued_run = store.create_job("run/contract/replay", dict(RUN_PARAMS))
    running = store.create_job("cut off mid-run", {})
    store.set_status(running["id"], "running")
    done = store.create_job("already finished", {})
    store.set_status(done["id"], "running")
    store.set_status(done["id"], "completed")
    return queued, queued_run, running, done


def _install(monkeypatch, store, scheduler):
    monkeypatch.setattr(main, "_store", store)
    monkeypatch.setattr(main, "_scheduler", scheduler)


def test_startup_dispatches_queued_and_fails_running(monkeypatch):
    """AC-SVC-007: startup re-dispatches every `queued` job through the normal
    dispatch path — each one to the executor its own `kind` names — fails every
    `running` job with the interrupted message, and leaves terminal jobs alone."""
    store = JobStore(_DB_PATH)
    try:
        queued, queued_run, running, done = _seed(store)
    finally:
        store.close()

    scheduler = _RecordingScheduler()
    store = JobStore(_DB_PATH)
    _install(monkeypatch, store, scheduler)

    try:
        with TestClient(main.app):  # entering the app runs the lifespan
            assert scheduler.started is True
            assert store.get_job(queued["id"])["status"] == "queued"
            assert store.get_job(queued_run["id"])["status"] == "queued"
            assert store.get_job(running["id"])["status"] == "failed"
            assert store.get_job(running["id"])["error"] == INTERRUPTED
            assert store.get_job(done["id"])["status"] == "completed"
    finally:
        store.close()

    # The ONE dispatch path a new job takes, routed by the job's own kind.
    assert sorted((func.__name__, args) for func, args in scheduler.dispatched) == [
        ("_execute_research", (queued["id"],)),
        ("_execute_run", (queued_run["id"],)),
    ]


def test_startup_on_a_fresh_store_has_nothing_to_recover(tmp_path, monkeypatch):
    """AC-SVC-007: a fresh store (what every integration test starts on)
    recovers nothing and dispatches nothing — the hook is inert without
    leftovers."""
    store = JobStore(str(tmp_path / "fresh.db"))
    scheduler = _RecordingScheduler()
    _install(monkeypatch, store, scheduler)

    try:
        with TestClient(main.app):
            assert scheduler.started is True
            assert scheduler.dispatched == []
            assert store.jobs_with_status("queued") == []
            assert store.jobs_with_status("running") == []
    finally:
        store.close()


def test_startup_failure_after_start_still_shuts_the_scheduler_down(tmp_path, monkeypatch):
    """A raise during recovery must not strand a started scheduler.

    The scheduler starts before recovery runs, so an exception there (an
    unreadable store, `database is locked`) used to skip the lifespan's
    `finally`: the scheduler stayed up, the NEXT start raised
    SchedulerAlreadyRunningError, and the real cause was hidden. Startup still
    fails with the original error, the scheduler is shut down, and a second
    start works.
    """
    store = JobStore(str(tmp_path / "unreadable.db"))
    scheduler = _RecordingScheduler()
    _install(monkeypatch, store, scheduler)
    try:
        with pytest.MonkeyPatch.context() as failing:

            def _boom(_store):
                raise RuntimeError("database is locked")

            failing.setattr(main, "recover_interrupted_jobs", _boom)
            with pytest.raises(RuntimeError, match="database is locked"):
                with TestClient(main.app):
                    pass  # entering the app runs the lifespan

        assert scheduler.started is False  # shut down despite the failure

        with TestClient(main.app):  # a second start is not SchedulerAlreadyRunning
            assert scheduler.started is True
    finally:
        store.close()


def _stub_execution(monkeypatch, tmp_path):
    """Replace provisioning and measuring with a counter; return the counter."""
    calls = {"measure": 0}

    def _provision(job_id, workload, **kwargs):
        return tmp_path / job_id / "repo"

    def _measure(repo):
        calls["measure"] += 1
        return {
            "status": "completed",
            "val_bpb": 0.0,
            "output": "stub",
            "duration_s": 0.0,
            "command": "stub",
        }

    monkeypatch.setattr(main, "provision_run_repo", _provision)
    monkeypatch.setattr(main, "_measure_once", _measure)
    return calls


def test_a_job_dispatched_twice_runs_the_loop_once(tmp_path, monkeypatch):
    """A repeat dispatch is a true no-op, not a second run or a traceback.

    Recovery re-dispatches a `queued` job through the same path a new job takes,
    and APScheduler may hand one job to two threads. The atomic claim makes the
    loser return before the measurement, so the loop runs exactly once and no
    `illegal status transition: running -> running` is logged.
    """
    store = JobStore(str(tmp_path / "twice.db"))
    calls = _stub_execution(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "_store", store)
    try:
        job = store.create_job("dispatched twice", {})
        main._execute_research(job["id"])
        main._execute_research(job["id"])  # the repeat dispatch

        assert calls["measure"] == 1
        assert store.get_job(job["id"])["status"] == "completed"
    finally:
        store.close()


def test_concurrent_dispatches_of_one_job_run_the_loop_once(tmp_path, monkeypatch):
    """Two dispatches racing on one queued job: one runs, the other returns.

    APScheduler can hand one job to two threads and both may read it as
    `queued`. Without an atomic claim the loser then raises an illegal status
    transition (`running -> running`, or `completed -> running` if the winner
    has already finished), which the scheduler logs as a traceback; with one,
    the loser claims nothing and returns.

    Deterministic interleaving: `get_job` holds both callers at the queued read
    until both have arrived, so neither can slip past the status check before
    the other has read it too.
    """
    store = JobStore(str(tmp_path / "race.db"))
    calls = _stub_execution(monkeypatch, tmp_path)
    both_read = threading.Barrier(2, timeout=10)
    real_get_job = store.get_job
    job = store.create_job("dispatched twice", {})

    def gated_get_job(job_id):
        found = real_get_job(job_id)
        if found is not None and found["status"] == "queued":
            both_read.wait()  # both dispatches have read `queued`; now they race
        return found

    monkeypatch.setattr(store, "get_job", gated_get_job)
    monkeypatch.setattr(main, "_store", store)
    errors = []

    def dispatch():
        try:
            main._execute_research(job["id"])
        except BaseException as exc:  # an illegal transition surfaced here
            errors.append(exc)

    try:
        threads = [threading.Thread(target=dispatch) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert errors == []
        assert calls["measure"] == 1
        assert real_get_job(job["id"])["status"] == "completed"
    finally:
        store.close()
