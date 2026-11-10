"""Dual-exposure autoresearch service, re-founded on the engine (PRD-20 SC1-SC4).

One ASGI app serves REST under ``/api/v1`` and MCP streamable HTTP at ``/mcp``
from the same FastAPI/FastMCP process: each operation handler is defined once and
reachable both as an HTTP route and (as flagged in ``TOOL_FLAG``) as an MCP tool;
``/health`` is a REST-only probe and is never a tool.

The loop, the metric parser and the reporting are the **engine's**
(``autoresearch.loop`` / ``autoresearch.measure`` / ``autoresearch.report``) —
this module owns jobs, scheduling, policy and the HTTP/tool surface, and nothing
else. Every job runs on a per-job copy of a *bundled* workload
(``workspace.provision_run_repo``), never on a caller-supplied path.

Two operation families:

``research_*``
    The PRD-05/06 contract, unchanged: a topic (+ corpus), a durable job id, a
    numeric ``val_bpb``. Execution is one engine measurement of the bundled
    ``contract`` workload.
``run_*`` / ``doctor``
    PRD-20: a full keep/discard loop over a bundled workload driven by an
    allowlisted agent (``replay`` by default), its report, and an inventory of
    what this instance can run.

Scheduling: APScheduler's ``BackgroundScheduler`` (started in the FastAPI
lifespan, shut down on teardown) runs one job per entry. The MCP app's own
lifespan is entered explicitly — nested lifespans are not auto-recognized when
routes are spliced into a parent app.

Auth: ``require_bearer`` on every REST route except ``/health``; the ``/mcp``
route is wrapped in a small ASGI guard enforcing the same bearer token when
auth is enabled (``AUTH_DISABLED`` respected, token never logged).

Security posture: no shell, constant-time token compares, no hardcoded secrets,
no code-execution tool, and an agent allowlist (``policy``) that fails closed.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from autoresearch import adapters, config, ledger, loop, measure, report
from autoresearch import cli as engine_cli

from . import policy, workloads
from .auth import auth_enabled, require_bearer, verify_token
from .jobs import JobStore
from .workspace import (
    corpus_spec_from_params,
    corpus_stats,
    provision_run_repo,
    repo_dir,
    validate_corpus_files,
)

PORT = int(os.environ.get("PORT", "8000"))

# PRD-06: cap on concurrently executing jobs (scheduler thread pool).
MAX_CONCURRENT_JOBS = max(1, int(os.environ.get("RESEARCH_MAX_CONCURRENT_JOBS", "4")))

# The workload a research_* job measures: the bundled toy contract (PRD-20 SC3).
RESEARCH_WORKLOAD = "contract"

# Per-endpoint MCP tool flags: True means the operation is ALSO exposed as an
# MCP tool under the same name. /health is a REST probe — never a tool.
TOOL_FLAG = {
    "research_start": True,
    "research_status": True,
    "research_results": True,
    "research_cancel": True,
    "run_start": True,
    "run_status": True,
    "run_report": True,
    "run_cancel": True,
    "doctor": True,
    "health": False,
}

# Route-to-operation mapping table (AC-MCP-004): (HTTP method, path) -> operation.
ROUTE_TO_OPERATION = {
    ("POST", "/api/v1/research"): "research_start",
    ("GET", "/api/v1/research/{job_id}"): "research_status",
    ("GET", "/api/v1/research/{job_id}/results"): "research_results",
    ("DELETE", "/api/v1/research/{job_id}"): "research_cancel",
    ("POST", "/api/v1/runs"): "run_start",
    ("GET", "/api/v1/runs/{job_id}"): "run_status",
    ("GET", "/api/v1/runs/{job_id}/report"): "run_report",
    ("DELETE", "/api/v1/runs/{job_id}"): "run_cancel",
    ("GET", "/api/v1/doctor"): "doctor",
}


class ResearchRequest(BaseModel):
    """Body of POST /api/v1/research."""

    topic: str
    params: dict | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class RunRequest(BaseModel):
    """Body of POST /api/v1/runs (PRD-20 SC3/SC4)."""

    workload: str = RESEARCH_WORKLOAD
    agent: str = policy.REPLAY
    max_iterations: int = 3
    # Validated by ``policy.validate_records`` rather than by pydantic, so a
    # malformed record set is the documented 400 (not a 422 the policy never
    # sees) and REST/MCP refuse it identically.
    records: Any = None
    model: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


# -- runtime state ----------------------------------------------------------
# Module-level singletons populated by create_app(); the operation handlers
# read them lazily so the MCP tool registry (captured at import time) works
# against the app instance that create_app() builds.
_store = None
_scheduler = None

# The FastMCP server for the /mcp surface (streamable HTTP, stateless).
mcp = FastMCP("autoresearch")


# -- research operations: one handler per operation, shared by REST and MCP ---


def research_start(
    topic: str,
    params: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Create a queued job, schedule its execution, and return the job dict."""
    params = params or {}
    # Fail fast on missing corpus files (PRD-06 SC5): ValueError -> 400/tool error.
    validate_corpus_files(corpus_spec_from_params(params))
    job = _store.create_job(topic, params, idempotency_key=idempotency_key)
    if job["status"] == "queued":  # an idempotent replay returns the existing job
        _scheduler.add_job(_execute_research, args=[job["id"]])
    return job


def research_status(job_id: str) -> dict:
    """Return the job dict; unknown ids raise ValueError (REST maps to 404)."""
    return _require_job(job_id)


def research_results(job_id: str) -> dict:
    """Return the job dict; it carries the run report once completed."""
    return _require_job(job_id)


def research_cancel(job_id: str) -> dict:
    """Cancel a queued or running job; terminal jobs return unchanged."""
    return _cancel(job_id)


# -- run operations (PRD-20) -------------------------------------------------


def run_start(
    workload: str = RESEARCH_WORKLOAD,
    agent: str = policy.REPLAY,
    max_iterations: int = 3,
    records: list[dict] | None = None,
    model: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Validate a run request, queue the job, and return the job dict.

    Every refusal (unknown workload, agent not allowlisted, ``command``, a
    malformed or oversized replay record set, an out-of-range iteration budget)
    raises ``ValueError`` — REST 400 / MCP tool error — *before* a job exists.
    """
    params = policy.validate_run_request(
        workload=workload,
        agent=agent,
        max_iterations=max_iterations,
        records=records,
        model=model,
    )
    job = _store.create_job(
        f"run/{params['workload']}/{params['agent']}",
        params,
        idempotency_key=idempotency_key,
    )
    if job["status"] == "queued":
        _scheduler.add_job(_execute_run, args=[job["id"]])
    return job


def run_status(job_id: str) -> dict:
    """Job dict plus the engine's summary of the run, once it has started."""
    job = _require_job(job_id)
    return {**job, "engine": _engine_summary(repo_dir(job_id))}


def run_report(job_id: str) -> dict:
    """The engine's report markdown and results rows for a run."""
    job = _require_job(job_id)
    repo = repo_dir(job_id)
    if not config.run_json_path(repo).is_file():
        # Queued, or provisioning never got as far as a configured run.
        return {"job_id": job_id, "status": job["status"], "report": "", "results": []}
    cfg = config.load(repo)
    events, problems = ledger.load(cfg.events_path)
    if problems:
        # A ledger that fails its own replay check is not a report — say so.
        raise ValueError("ledger invalid: " + "; ".join(problems))
    return {
        "job_id": job_id,
        "status": job["status"],
        "report": report.render_markdown(cfg, events),
        "results": report.trial_rows(events),
    }


def run_cancel(job_id: str) -> dict:
    """Cancel a queued or running run; terminal jobs return unchanged."""
    return _cancel(job_id)


def doctor() -> dict:
    """What this instance can run: allowed agents, harness binaries, workloads.

    Reuses the engine's own doctor probe (per-harness binary, path and version).
    Credential state is reported by name only — no value is ever read or echoed.
    """
    allowed = policy.allowed_agents()
    harnesses = [
        {**row, "allowed": row["agent"] in allowed} for row in engine_cli.probe_harnesses()
    ]
    return {
        "allowed_agents": list(allowed),
        "refused_agents": list(policy.NEVER_ALLOWED),
        "harnesses": harnesses,
        "workloads": list(workloads.known_workloads()),
    }


# -- job execution -----------------------------------------------------------


def _require_job(job_id: str) -> dict:
    job = _store.get_job(job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    return job


def _cancel(job_id: str) -> dict:
    job = _require_job(job_id)
    if job["status"] not in ("queued", "running"):
        return job
    return _store.set_status(job_id, "cancelled")


def _finish(job_id: str, result: dict) -> None:
    """Persist a job's result and mirror its status; a cancelled job wins."""
    try:
        _store.set_result(job_id, result)
        _store.set_status(job_id, result["status"])
    except ValueError:
        pass  # cancelled mid-run — the terminal state stays


def _execute_research(job_id: str) -> None:
    """Scheduler entrypoint: one engine measurement of the bundled contract.

    The result keeps the PRD-05/06 shape (``status``, ``val_bpb``, ``output``,
    ``duration_s``, ``command``) plus the PRD-06 ``topic``/``corpus`` stats.
    ``status`` is mapped from the measurement: ``completed`` | ``timeout`` |
    ``failed``.
    """
    job = _store.get_job(job_id)
    if job is None or job["status"] != "queued":
        return  # cancelled or unknown before the run began
    _store.set_status(job_id, "running")
    topic = job["topic"]
    repo = repo_dir(job_id)
    try:
        repo = provision_run_repo(
            job_id,
            workloads.get_workload(RESEARCH_WORKLOAD),
            topic=topic,
            spec=corpus_spec_from_params(job["params"]),
        )
        result = _measure_once(repo)
        result["topic"] = topic
        result["corpus"] = corpus_stats(repo)
    except Exception as exc:  # provisioning or config failure, surfaced as a result
        result = {
            "status": "failed",
            "val_bpb": None,
            "output": f"run provisioning failed: {exc}",
            "duration_s": 0.0,
            "command": "",
            "topic": topic,
            "corpus": corpus_stats(repo) if repo.is_dir() else {"files": 0, "chars": 0},
        }
    _finish(job_id, result)


def _measure_once(repo: Path) -> dict:
    """Run the guard, then one engine measurement; map it onto a job result."""
    cfg = config.load(repo)
    guard_ok, guard_log = measure.run_guard(cfg)
    if not guard_ok:
        return {
            "status": "failed",
            "val_bpb": None,
            "output": guard_log,
            "duration_s": 0.0,
            "command": cfg.verify,
        }
    measurement = measure.measure(cfg)
    if measurement.ok:
        status = "completed"
    elif measurement.log_tail.startswith("timeout"):
        status = "timeout"
    else:
        status = "failed"
    return {
        "status": status,
        "val_bpb": measurement.value,
        "output": measurement.log_tail,
        "duration_s": round(measurement.seconds, 3),
        "command": cfg.verify,
    }


def _execute_run(job_id: str) -> None:
    """Scheduler entrypoint: drive the engine loop over a provisioned run repo."""
    job = _store.get_job(job_id)
    if job is None or job["status"] != "queued":
        return
    _store.set_status(job_id, "running")
    params = job["params"]
    result: dict = {"status": "failed"}
    try:
        agent = str(params.get("agent"))
        repo = provision_run_repo(job_id, workloads.get_workload(str(params.get("workload"))))
        workspace = repo.parent
        records = None
        if agent == policy.REPLAY:
            records = adapters.load_records(
                _write_records(workspace, params.get("records") or [])
            )
        adapter = adapters.make_adapter(agent, model=params.get("model"), records=records)
        cfg = config.load(repo)
        opts = loop.Options(
            max_iterations=int(params.get("max_iterations")),
            json_output=True,
        )
        events_out = workspace / "events.out"
        with open(events_out, "w", encoding="utf-8") as stream:
            emit = loop.Emitter(json_output=True, stream=stream)
            # One run per repo: the engine's own single-writer guard.
            with config.state_lock(cfg.repo):
                code = loop.run(cfg, adapter, ledger.Ledger(cfg.events_path), opts, emit)
        result.update(
            {
                "status": "completed" if code == 0 else "failed",
                "exit_code": code,
                "summary": _engine_summary(repo),
                "events": str(events_out),
            }
        )
    except Exception as exc:  # a refused request or a missing binary is a result
        result.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    _finish(job_id, result)


def _write_records(workspace: Path, records: list) -> str:
    """Write the job's replay records as JSONL beside its repo; return the path."""
    path = Path(workspace) / "records.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return str(path)


def _engine_summary(repo: Path) -> dict | None:
    """The engine's own view of a run: baseline, incumbent, trials, stop reason.

    ``None`` when the repo has no run configured yet (queued, or provisioning
    failed) — a status endpoint should say "nothing yet", not raise.
    """
    try:
        if not config.run_json_path(repo).is_file():
            return None
        cfg = config.load(repo)
        events, _problems = ledger.load(cfg.events_path)
        summary = report.summarize(cfg, events)
    except (OSError, ValueError, config.ConfigError):
        return None
    return {
        "metric_name": cfg.metric_name,
        "direction": cfg.direction,
        "baseline_metric": summary["baseline_metric"],
        "incumbent_metric": summary["best_metric"],
        "trials": summary["iterations"],
        "outcomes": summary["outcomes"],
        "stop_reason": summary["stop_reason"],
    }


# Register the flagged operations as MCP tools (same handler objects).
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


def _bad_request(exc: ValueError) -> HTTPException:
    """A refused request (policy, corpus, workload) is a 400, never a 500."""
    return HTTPException(status_code=400, detail=str(exc))


def create_app() -> FastAPI:
    """Build the dual-exposure ASGI app (REST routes + /mcp mount)."""
    global _store, _scheduler
    _store = JobStore()
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
            raise _bad_request(exc) from exc

    @app.get("/api/v1/research/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_status(job_id: str) -> dict:
        return _op_or_404(research_status, job_id)

    @app.get("/api/v1/research/{job_id}/results", dependencies=[Depends(_bearer_dependency)])
    def _rest_results(job_id: str) -> dict:
        return _op_or_404(research_results, job_id)

    @app.delete("/api/v1/research/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_cancel(job_id: str) -> dict:
        return _op_or_404(research_cancel, job_id)

    @app.post("/api/v1/runs", status_code=202, dependencies=[Depends(_bearer_dependency)])
    def _rest_run_start(body: RunRequest) -> dict:
        try:
            return run_start(
                workload=body.workload,
                agent=body.agent,
                max_iterations=body.max_iterations,
                records=body.records,
                model=body.model,
                idempotency_key=body.idempotency_key,
            )
        except ValueError as exc:
            # Policy / workload refusal happens before a job is created.
            raise _bad_request(exc) from exc

    @app.get("/api/v1/runs/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_run_status(job_id: str) -> dict:
        return _op_or_404(run_status, job_id)

    @app.get("/api/v1/runs/{job_id}/report", dependencies=[Depends(_bearer_dependency)])
    def _rest_run_report(job_id: str) -> dict:
        return _op_or_404(run_report, job_id)

    @app.delete("/api/v1/runs/{job_id}", dependencies=[Depends(_bearer_dependency)])
    def _rest_run_cancel(job_id: str) -> dict:
        return _op_or_404(run_cancel, job_id)

    @app.get("/api/v1/doctor", dependencies=[Depends(_bearer_dependency)])
    def _rest_doctor() -> dict:
        return doctor()

    # /mcp mount: the streamable-HTTP route(s) registered directly on the
    # FastAPI app behind the bearer guard.
    for route in mcp_app.routes:
        app.add_route(route.path, mcp_guarded, methods=list(route.methods or []))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
