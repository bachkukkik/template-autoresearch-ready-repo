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

# The column list every job read selects, in the order _row_to_job unpacks.
_JOB_COLUMNS = "id, topic, params, status, error, result, created_at, updated_at"

# The service root (the directory holding autoresearch_service/): runtime paths
# resolve against it, so a host run from any cwd and the container agree on one
# store. realpath (not abspath), so a symlinked checkout resolves like Path.resolve().
SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

DEFAULT_DB_PATH = os.path.join(SERVICE_ROOT, "data", "jobs.db")

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


def _service_path(value: str) -> str:
    """A relative path resolves against the service root, never the process cwd."""
    return value if os.path.isabs(value) else os.path.join(SERVICE_ROOT, value)


def _default_db_path() -> str:
    """RESEARCH_JOBS_DB env var wins; otherwise <service-root>/data/jobs.db.

    A *relative* RESEARCH_JOBS_DB is service-root-relative: a host run started
    from the repo root and the container then name the same store, instead of
    one writing ``data/jobs.db`` beside the cwd and the other writing it under
    the service. A blank value (empty or whitespace-only) is unset, not a path —
    otherwise it would resolve to the service root and scatter job dirs into the
    tracked tree.
    """
    value = (os.environ.get("RESEARCH_JOBS_DB") or "").strip()
    return _service_path(value or DEFAULT_DB_PATH)


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
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id = ?",
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

    def claim(self, job_id: str) -> bool:
        """Atomically take a `queued` job for execution; False if it is taken.

        One ``UPDATE ... WHERE id = ? AND status = 'queued'`` under the store
        lock, so two dispatches of the same job cannot both win: exactly one
        gets True, the other gets False and runs nothing. Losing that race is
        not an error — unlike `set_status`, where running -> running stays an
        illegal transition.
        """
        with self._lock:
            changed = self._conn.execute(
                "UPDATE jobs SET status = 'running', error = NULL, updated_at = ?"
                " WHERE id = ? AND status = 'queued'",
                (_now(), job_id),
            ).rowcount
            self._conn.commit()
        return changed == 1

    def jobs_with_status(self, status: str) -> list[dict]:
        """Every job currently in `status`, oldest first — the restart scan.

        Used at startup to find what a stopped process left behind: `queued`
        jobs never ran, `running` ones were cut off mid-run.
        """
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE status = ?"
                " ORDER BY created_at, id",
                (status,),
            ).fetchall()
        found = []
        for row in rows:
            job = self._row_to_job(row)
            assert job is not None  # selected rows exist
            found.append(job)
        return found

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
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE idempotency_key = ?",
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