"""Durable SQLite job store for the research job-id/poll pattern (PRD-05 SC4).

Job lifecycle: queued -> running -> completed | failed | cancelled, with results
merged via set_result. Jobs survive a service restart because they live in a
SQLite file (WAL mode), and dispatch is idempotent via an explicit
idempotency_key.

Standards: stdlib sqlite3 only (no ORM), WAL mode, thread-safe via
check_same_thread=False + a lock guarding every transaction.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

# Allowed status transitions; anything else raises ValueError.
ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled"},  # +cancelled: cancel before start (AC-MCP-014)
    "running": {"completed", "failed", "cancelled", "timeout"},  # +timeout: runner budget expiry
}

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})

DEFAULT_DB_PATH = os.path.join("data", "jobs.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    params          TEXT NOT NULL,
    status          TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    error           TEXT,
    result          TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
)
"""


def _now() -> str:
    """UTC ISO-8601 timestamp, e.g. 2026-09-05T12:00:00.123456+00:00."""
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> str:
    """RESEARCH_JOBS_DB env var wins; otherwise ./data/jobs.db."""
    return os.environ.get("RESEARCH_JOBS_DB") or DEFAULT_DB_PATH


class JobStore:
    """Thread-safe, durable SQLite job store.

    A single connection is opened per instance (check_same_thread=False) and
    every transaction is serialized under a lock. Opening a new JobStore on
    the same db_path reads the same jobs — that is the restart-survival story.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _default_db_path()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()

    # -- public API ---------------------------------------------------------

    def create_job(
        self,
        topic: str,
        params: dict,
        idempotency_key: str | None = None,
    ) -> dict:
        """Create a queued job and return it.

        A repeated idempotency_key returns the EXISTING job (same id) instead
        of creating a second one. Jobs created without a key are never deduped.
        """
        job_id = uuid.uuid4().hex
        now = _now()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO jobs"
                    " (id, topic, params, status, idempotency_key, error,"
                    " result, created_at, updated_at)"
                    " VALUES (?, ?, ?, 'queued', ?, NULL, NULL, ?, ?)",
                    (job_id, topic, json.dumps(params), idempotency_key, now, now),
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                if idempotency_key is None:
                    raise
                # Unique(idempotency_key) collision — return the existing job.
                existing = self._get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing
                raise
        job = self.get_job(job_id)
        assert job is not None  # freshly inserted above
        return job

    def get_job(self, job_id: str) -> dict | None:
        """Return the job dict, or None when no such job exists."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, topic, params, status, error, result,"
                " created_at, updated_at FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return self._row_to_job(row)

    def set_status(self, job_id: str, status: str, error: str | None = None) -> dict:
        """Transition a job to a new status; returns the updated job.

        Allowed: queued -> running -> completed | failed | cancelled.
        Raises ValueError on an illegal transition or an unknown job id.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"job not found: {job_id}")
            current = row[0]
            if status not in ALLOWED_TRANSITIONS.get(current, ()):
                raise ValueError(
                    f"illegal status transition: {current} -> {status}"
                )
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                " WHERE id = ?",
                (status, error, _now(), job_id),
            )
            self._conn.commit()
        job = self.get_job(job_id)
        assert job is not None  # status row existed above
        return job

    def set_result(self, job_id: str, result: dict) -> dict:
        """Merge results into the job (later keys win); returns the updated job."""
        with self._lock:
            row = self._conn.execute(
                "SELECT result FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"job not found: {job_id}")
            merged = {}
            if row[0] is not None:
                merged.update(json.loads(row[0]))
            merged.update(result)
            self._conn.execute(
                "UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged), _now(), job_id),
            )
            self._conn.commit()
        job = self.get_job(job_id)
        assert job is not None  # result row existed above
        return job

    # -- internals ----------------------------------------------------------

    def _get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, topic, params, status, error, result,"
                " created_at, updated_at FROM jobs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return self._row_to_job(row)

    @staticmethod
    def _row_to_job(row) -> dict | None:
        if row is None:
            return None
        return {
            "id": row[0],
            "topic": row[1],
            "params": json.loads(row[2]),
            "status": row[3],
            "error": row[4],
            "result": json.loads(row[5]) if row[5] is not None else None,
            "created_at": row[6],
            "updated_at": row[7],
        }