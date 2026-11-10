"""Dual-exposure autoresearch service (PRD-05 SC1-SC6).

One ASGI app serves REST under ``/api/v1`` and MCP streamable HTTP at ``/mcp``
from the same FastAPI/FastMCP process. SC1 — non-duplicated handler syntax:
each operation handler is defined once and reachable both as an HTTP route and
(as flagged in ``TOOL_FLAG``) as an MCP tool; ``/health`` is a REST-only probe
and is never a tool.

Scheduling: APScheduler's ``BackgroundScheduler`` (started in the FastAPI
lifespan, shut down on teardown) runs the research loop once per job. The MCP
app's own lifespan is entered explicitly — nested lifespans are not
auto-recognized when routes are spliced into a parent app.

Auth: ``require_bearer`` on every REST route except ``/health``; the ``/mcp``
route is wrapped in a small ASGI guard enforcing the same bearer token when
auth is enabled (``AUTH_DISABLED`` respected, token never logged).

Security posture: no shell, constant-time token compares, no hardcoded
secrets — everything comes from the environment.

PRD-06 concurrency: multiple topics run concurrently, each in its own
provisioned workspace. ``RESEARCH_MAX_CONCURRENT_JOBS`` caps the scheduler's
default executor thread pool, and corpus files are validated fail-fast at
start (missing file -> 400/tool error) before a job is ever queued. Handlers
remain ``sync def`` by design (PRD-06 SC4): the scheduler thread pool, not
the event loop, does the research work, so async handlers would buy nothing.
"""

import json
import os
from contextlib import asynccontextmanager

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .auth import auth_enabled, require_bearer, verify_token
from .jobs import JobStore
from .runner import ResearchRunner

PORT = int(os.environ.get("PORT", "8000"))

# PRD-06: cap on concurrently executing research jobs (scheduler thread pool).
MAX_CONCURRENT_JOBS = max(1, int(os.environ.get("RESEARCH_MAX_CONCURRENT_JOBS", "4")))

# Per-endpoint MCP tool flags (SC1): True means the operation is ALSO exposed
# as an MCP tool under the same name. /health is a REST probe — never a tool.
TOOL_FLAG = {
    "research_start": True,
    "research_status": True,
    "research_results": True,
    "research_cancel": True,
    "health": False,
}

# Route-to-operation mapping table (AC-MCP-004): (HTTP method, path) -> operation.
ROUTE_TO_OPERATION = {
    ("POST", "/api/v1/research"): "research_start",
    ("GET", "/api/v1/research/{job_id}"): "research_status",
    ("GET", "/api/v1/research/{job_id}/results"): "research_results",
    ("DELETE", "/api/v1/research/{job_id}"): "research_cancel",
}


class ResearchRequest(BaseModel):
    """Body of POST /api/v1/research."""

    topic: str
    params: dict | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


# -- runtime state ----------------------------------------------------------
# Module-level singletons populated by create_app(); the operation handlers
# read them lazily so the MCP tool registry (captured at import time) works
# against the app instance that create_app() builds.
_store = None
_scheduler = None
_runner = None

# The FastMCP server for the /mcp surface (streamable HTTP, stateless).
mcp = FastMCP("autoresearch")


# -- operations: one handler per operation, shared by REST and MCP -----------

def research_start(
    topic: str,
    params: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Create a queued job, schedule its execution, and return the job dict."""
    params = params or {}
    # Fail fast on missing corpus files (PRD-06 SC5): ValueError -> 400/tool error.
    from .workspace import corpus_spec_from_params, validate_corpus_files

    spec = corpus_spec_from_params(params)
    validate_corpus_files(spec)
    job = _store.create_job(topic, params, idempotency_key=idempotency_key)
    if job["status"] == "queued":  # an idempotent replay returns the existing job
        _scheduler.add_job(_run_job, args=[job["id"]])
    return job


def research_status(job_id: str) -> dict:
    """Return the job dict; unknown ids raise ValueError (REST maps to 404)."""
    job = _store.get_job(job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    return job


def research_results(job_id: str) -> dict:
    """Return the job dict; it carries the run report once completed."""
    return research_status(job_id)


def research_cancel(job_id: str) -> dict:
    """Cancel a queued or running job; already-terminal jobs return unchanged."""
    job = _store.get_job(job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    if job["status"] not in ("queued", "running"):
        return job
    return _store.set_status(job_id, "cancelled")


def _run_job(job_id: str) -> None:
    """Scheduler entrypoint: run the loop once and persist the outcome.

    The runner report carries its own ``status`` ('completed' | 'failed' |
    'timeout'); it is stored as the job result and mirrored onto the job status.
    A job cancelled while queued (or mid-run) keeps its terminal state.
    """
    job = _store.get_job(job_id)
    if job is None or job["status"] != "queued":
        return  # cancelled or unknown before the run began
    _store.set_status(job_id, "running")
    # PRD-06: run in a per-job provisioned workspace so concurrent topics
    # never share working state.
    from .workspace import corpus_spec_from_params, provision_workspace

    spec = corpus_spec_from_params(job["params"])
    try:
        work_dir = provision_workspace(job_id=job_id, topic=job["topic"], spec=spec)
        report = _runner.run_loop(work_dir=str(work_dir))
    except Exception as exc:
        report = {
            "status": "failed",
            "val_bpb": None,
            "output": f"workspace provisioning failed: {exc}",
            "duration_s": 0.0,
            "command": "python3 prepare.py && python3 train.py",
        }
    try:
        _store.set_result(job_id, report)
        _store.set_status(job_id, report["status"])
    except ValueError:
        pass  # cancelled mid-run — the terminal state wins


# Register the flagged operations as MCP tools (SC1: same handler objects).
for _op, _is_tool in TOOL_FLAG.items():
    if _is_tool:
        mcp.tool(globals()[_op], name=_op)


# -- /mcp bearer guard -------------------------------------------------------

class _BearerGuard:
    """ASGI guard: reject requests to /mcp without a valid bearer token.

    Only acts when auth is enabled (``auth_enabled()``); the token is compared
    constant-time and is never logged. Runs before the streamable-HTTP app.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not auth_enabled():
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        authorization = headers.get(b"authorization")
        ok = (
            authorization is not None
            and authorization.startswith(b"Bearer ")
            and verify_token(authorization[len(b"Bearer "):].decode("latin-1"))
        )
        if not ok:
            body = json.dumps({"detail": "unauthorized"}).encode()
            headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ]
            # Complete ASGI response: start + body. A start-only reply would
            # leave the client hanging on a body that never arrives.
            await send({"type": "http.response.start", "status": 401, "headers": headers})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return
        await self.app(scope, receive, send)


# -- app factory -------------------------------------------------------------

def _bearer_dependency(authorization: str | None = Header(default=None)) -> None:
    """Bind the Authorization header for ``require_bearer``.

    FastAPI treats a bare ``authorization: str | None = None`` parameter as a
    *query* parameter, so the header must be declared explicitly with
    ``Header`` or every auth-enabled REST request would see ``None`` and 401.
    """
    require_bearer(authorization)


def _op_or_404(op_call, job_id: str) -> dict:
    """Map a handler's 'not found' ValueError to an HTTP 404."""
    try:
        return op_call(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def create_app() -> FastAPI:
    """Build the dual-exposure ASGI app (REST routes + /mcp mount)."""
    global _store, _scheduler, _runner
    _store = JobStore()
    _runner = ResearchRunner()
    _scheduler = BackgroundScheduler(
        executors={
            "default": ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
        }
    )

    # FastMCP v4 streamable-HTTP app (stateless), mounted by splicing its route
    # into the FastAPI app; its lifespan is entered explicitly below because
    # nested lifespans are not auto-recognized.
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True)
    mcp_guarded = _BearerGuard(mcp_app)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _scheduler.start()
        try:
            async with mcp_app.lifespan(app):
                yield
        finally:
            _scheduler.shutdown(wait=True)

    app = FastAPI(title="autoresearch-service", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def _health() -> dict:
        return {"status": "ok"}

    @app.post("/api/v1/research", status_code=202, dependencies=[Depends(_bearer_dependency)])
    def _rest_start(body: ResearchRequest) -> dict:
        try:
            return research_start(body.topic, body.params, body.idempotency_key)
        except ValueError as exc:
            # Corpus validation failure (PRD-06 SC5): missing file -> 400, not 500.
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/research/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_status(job_id: str) -> dict:
        return _op_or_404(research_status, job_id)

    @app.get("/api/v1/research/{job_id}/results", dependencies=[Depends(_bearer_dependency)])
    def _rest_results(job_id: str) -> dict:
        return _op_or_404(research_results, job_id)

    @app.delete("/api/v1/research/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_cancel(job_id: str) -> dict:
        return _op_or_404(research_cancel, job_id)

    # /mcp mount: the streamable-HTTP route(s) registered directly on the
    # FastAPI app behind the bearer guard.
    for route in mcp_app.routes:
        app.add_route(route.path, mcp_guarded, methods=list(route.methods or []))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)