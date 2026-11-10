"""SC5 — bounded, sandboxed measurement. IDs: AC-MCP-021..024.

Retargeted (PRD-20 W2): the service no longer owns a subprocess loop or a metric
parser — the engine's ``measure`` module does. These IDs now pin the same
behaviours on that engine-backed path: a completed baseline with a numeric
metric, a timeout that is bounded and mapped, a failure when the workload cannot
be configured, and the contract's own summary line being parsed by the engine.
"""
import os
import tempfile
import time
from pathlib import Path

import pytest

from autoresearch import config, measure

_SCRATCH = Path(tempfile.mkdtemp(prefix="ar-unit-runner-"))
os.environ["RESEARCH_JOBS_DB"] = str(_SCRATCH / "jobs.db")
os.environ["RESEARCH_WORKSPACES_DIR"] = str(_SCRATCH / "workspaces")
os.environ["AUTH_DISABLED"] = "1"

from autoresearch_service import main, workspace, workloads  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workloads"
# The service's workload IS the canonical contract (single source of truth).
REFERENCE = REPO_ROOT / "autoresearch" / "contract"


def test_contract_workload_measures_with_metric():
    """AC-MCP-021: the bundled `contract` workload, provisioned the way the
    service provisions it, completes one engine measurement and parses val_bpb."""
    t0 = time.time()
    repo = workspace.provision_run_repo(
        "job-metric", workloads.get_workload("contract"), workspaces_root=_SCRATCH / "ws-metric"
    )
    result = main._measure_once(repo)
    wall = time.time() - t0

    assert result["status"] == "completed"
    assert isinstance(result["val_bpb"], (int, float)) and not isinstance(
        result["val_bpb"], bool
    )
    # the contract's bigram baseline lands ~3.7 — a tolerant band, not an exact value
    assert 3.0 < result["val_bpb"] < 4.5
    assert result["command"] == workloads.get_workload("contract").verify
    assert result["duration_s"] < 30.0  # RESEARCH_RUN_TIMEOUT budget
    assert wall < 10.0  # the reference workload must complete in seconds
    # the metric came out of the contract's own summary block
    assert "val_bpb:" in result["output"]


def test_timeout_is_bounded_and_mapped(monkeypatch):
    """AC-MCP-022: a 1.5s budget on a 5s-sleeping train.py -> status timeout,
    no metric, killed rather than waited out."""
    monkeypatch.setenv("RESEARCH_WORKLOAD_DIR", str(FIXTURES / "slow"))
    monkeypatch.setenv("RESEARCH_RUN_TIMEOUT", "1.5")

    repo = workspace.provision_run_repo(
        "job-timeout", workloads.get_workload("contract"), workspaces_root=_SCRATCH / "ws-timeout"
    )
    result = main._measure_once(repo)

    assert result["status"] == "timeout"
    assert result["val_bpb"] is None
    assert result["duration_s"] < 10.0  # killed, not waited out (train sleeps 5s)


def test_incomplete_workload_refuses_to_provision(monkeypatch):
    """AC-MCP-023: a workload missing prepare.py cannot be configured at all —
    the engine's init refuses it, so the job fails instead of measuring junk."""
    monkeypatch.setenv("RESEARCH_WORKLOAD_DIR", str(FIXTURES / "no_prepare"))

    with pytest.raises(config.ConfigError, match="prepare.py"):
        workspace.provision_run_repo(
            "job-incomplete",
            workloads.get_workload("contract"),
            workspaces_root=_SCRATCH / "ws-incomplete",
        )


def test_engine_parses_the_contract_summary_line():
    """AC-MCP-024: the contract's `val_bpb: 3.795531` line is parsed by the
    engine's `parse_metric`, last occurrence wins, and the service carries no
    parser of its own."""
    stdout = (
        "logging noise\n---\nval_bpb:          3.795531\n"
        "training_seconds: 0.0\n---\n"
    )
    assert measure.parse_metric(stdout, "val_bpb") == 3.795531
    assert measure.parse_metric("val_bpb: 9.5\nval_bpb: 2.5\n", "val_bpb") == 2.5
    assert measure.parse_metric("no metric here", "val_bpb") is None
    assert not hasattr(main, "parse_val_bpb")
