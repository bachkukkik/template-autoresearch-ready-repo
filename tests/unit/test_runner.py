"""SC5 — bounded sandboxed loop runner. IDs: AC-MCP-02N."""
import time
from pathlib import Path

from src.runner import ResearchRunner, parse_val_bpb

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workloads"
REFERENCE = REPO_ROOT / "service" / "workload"

COMMAND = "python3 prepare.py && python3 train.py"


def test_default_workload_completes_with_metric():
    """AC-MCP-021: default reference workload runs in seconds; parses val_bpb."""
    t0 = time.time()
    result = ResearchRunner().run_loop()
    wall = time.time() - t0

    assert result["status"] == "completed"
    assert result["val_bpb"] == 1.234
    assert result["command"] == COMMAND
    assert result["duration_s"] < 30.0  # budget default
    assert wall < 10.0  # the reference workload must complete in seconds
    assert "RESULT val_bpb=1.234" in result["output"]
    # train.py's JSON run summary line carries both keys
    assert '"training_seconds"' in result["output"]
    assert '"num_params_M"' in result["output"]


def test_timeout_kills_slow_train():
    """AC-MCP-022: 0.01s budget on a 5s-sleeping train.py -> status timeout."""
    result = ResearchRunner(
        workload_dir=str(FIXTURES / "slow"), timeout_s=0.01
    ).run_loop()

    assert result["status"] == "timeout"
    assert result["val_bpb"] is None
    assert result["command"] == COMMAND
    assert result["duration_s"] < 10.0  # killed, not waited out (train sleeps 5s)


def test_missing_prepare_fails():
    """AC-MCP-023: workload with no prepare.py -> status failed, train never runs."""
    result = ResearchRunner(workload_dir=str(FIXTURES / "no_prepare")).run_loop()

    assert result["status"] == "failed"
    assert result["val_bpb"] is None
    assert result["command"] == COMMAND
    assert "prepare.py" in result["output"]


def test_parse_val_bpb_takes_last_matching_line():
    """AC-MCP-024: parser returns the float of the LAST 'RESULT val_bpb=' line."""
    out = "logging noise\nRESULT val_bpb=0.5\nRESULT val_bpb=1.234\n"
    assert parse_val_bpb(out) == 1.234
    assert parse_val_bpb("RESULT val_bpb=-2.5e-1\n") == -0.25
    assert parse_val_bpb("no RESULT line here") is None