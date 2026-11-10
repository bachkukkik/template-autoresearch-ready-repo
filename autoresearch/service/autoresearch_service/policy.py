"""What the API will run, and for whom — safe by default (PRD-20 SC4).

Over REST/MCP the only agent allowed without configuration is ``replay``: it
needs no harness binary, no credentials and no network, and it replays a patch
the caller already supplied. ``claude``/``opencode``/``hermes``/``dsh`` are
allowed only when listed in ``RESEARCH_ALLOWED_AGENTS``, because each one runs a
model with the credentials of whoever hosts the service.

``command`` — an arbitrary shell template — is refused over the API even when
listed: its argv comes from the request, so no allowlist can bound what it runs.
The CLI keeps it for operators who own the machine.

Every check here runs **before** a job is created, so a refused request leaves no
queued job behind.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional, Sequence

#: Agents that need a harness binary and host credentials; allowlisted per name.
HARNESSES = ("claude", "opencode", "hermes", "dsh")

#: The one agent that is always allowed: no binary, no credentials, no network.
REPLAY = "replay"

#: Refused over the API regardless of configuration (arbitrary shell template).
NEVER_ALLOWED = ("command",)

#: Shape of a replay request. The engine re-applies each patch to the run repo.
MAX_RECORDS = 50
MAX_PATCH_BYTES = 200_000
MIN_ITERATIONS = 1
MAX_ITERATIONS = 20


def allowed_agents(environ: Optional[Mapping[str, str]] = None) -> tuple[str, ...]:
    """``replay`` plus the configured harnesses, in the engine's stable order.

    Only the four harness names can enter the set: a value in
    ``RESEARCH_ALLOWED_AGENTS`` that the engine does not know is ignored rather
    than forwarded, and ``command`` can never appear.
    """
    env = os.environ if environ is None else environ
    listed = {part.strip() for part in (env.get("RESEARCH_ALLOWED_AGENTS") or "").split(",")}
    return (REPLAY,) + tuple(name for name in HARNESSES if name in listed)


def validate_agent(agent: str) -> str:
    """Return ``agent`` when the API may run it; ``ValueError`` otherwise."""
    if agent in NEVER_ALLOWED:
        raise ValueError(
            f"agent {agent!r} is never available over the API — it runs an "
            "arbitrary command; use the CLI for it"
        )
    allowed = allowed_agents()
    if agent not in allowed:
        raise ValueError(
            f"agent {agent!r} is not allowed; allowed: {', '.join(allowed)} "
            "(list more in RESEARCH_ALLOWED_AGENTS)"
        )
    return agent


def validate_max_iterations(max_iterations: int) -> int:
    """Cap an iteration budget at ``1..20`` (a request cannot run forever)."""
    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or not MIN_ITERATIONS <= max_iterations <= MAX_ITERATIONS
    ):
        raise ValueError(
            f"max_iterations must be an integer in {MIN_ITERATIONS}..{MAX_ITERATIONS}, "
            f"got {max_iterations!r}"
        )
    return max_iterations


def validate_records(records: Optional[Sequence]) -> list[dict]:
    """Normalise a replay record list, or raise ``ValueError`` on any defect.

    A record is ``{iteration: int >= 1, patch: str, description?: str}``. Patches
    are capped so one request cannot fill the job store: the list is stored with
    the job and replayed by the engine's ``replay`` adapter.
    """
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError(
            "agent 'replay' requires a non-empty records list of "
            "{iteration, patch} objects"
        )
    if len(records) > MAX_RECORDS:
        raise ValueError(f"at most {MAX_RECORDS} records per run, got {len(records)}")
    out: list[dict] = []
    for position, record in enumerate(records, start=1):
        where = f"records[{position - 1}]"
        if not isinstance(record, dict):
            raise ValueError(f"{where} must be an object, got {type(record).__name__}")
        iteration = record.get("iteration")
        if (
            not isinstance(iteration, int)
            or isinstance(iteration, bool)
            or iteration < 1
        ):
            raise ValueError(f"{where}.iteration must be an integer >= 1")
        patch = record.get("patch")
        if not isinstance(patch, str):
            raise ValueError(f"{where}.patch must be a string")
        if len(patch.encode("utf-8", "replace")) > MAX_PATCH_BYTES:
            raise ValueError(
                f"{where}.patch is larger than {MAX_PATCH_BYTES} bytes"
            )
        description = record.get("description")
        out.append(
            {
                "iteration": iteration,
                "patch": patch,
                "description": description if isinstance(description, str) else "",
            }
        )
    return out


def validate_run_request(
    *,
    workload: str,
    agent: str,
    max_iterations: int,
    records: Optional[Sequence] = None,
    model: Optional[str] = None,
) -> dict:
    """Validate a full ``run_start`` request; return the params to persist.

    Raises ``ValueError`` (REST 400 / MCP tool error) before anything is stored.
    """
    from . import workloads

    spec = workloads.get_workload(workload)
    validate_agent(agent)
    validate_max_iterations(max_iterations)
    if model is not None and not isinstance(model, str):
        raise ValueError("model must be a string")
    params: dict = {
        "kind": "run",
        "workload": spec.name,
        "agent": agent,
        "max_iterations": max_iterations,
        "model": model,
    }
    if agent == REPLAY:
        params["records"] = validate_records(records)
    elif records:
        raise ValueError("records only apply to agent 'replay'")
    return params
