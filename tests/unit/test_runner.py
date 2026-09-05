"""SC5 — bounded sandboxed loop runner. IDs: AC-MCP-02N."""
import time
from pathlib import Path

from src.runner import ResearchRunner, parse_val_bpb

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workloads"
# The runner's default workload IS the canonical contract (single source of truth).
REFERENCE = REPO_ROOT / "contract"

COMMAND = "python3 prepare.py && python3 train.py"


def test_default_workload_completes_with_metric():
    """AC-MCP-021: the canonical contract/ runs in seconds; parses val_bpb."""
    t0 = time.time()
    result = ResearchRunner().run_loop()
    wall = time.time() - t0

    assert result["status"] == "completed"
    assert isinstance(result["val_bpb"], (int, float)) and not isinstance(
        result["val_bpb"], bool
    )
    assert result["val_bpb"] > 0.0
    # the contract's bigram baseline lands ~3.7 — assert a tolerant band, not an exact value
    assert 3.0 < result["val_bpb"] < 4.5
    assert result["command"] == COMMAND
    assert result["duration_s"] < 30.0  # budget default
    assert wall < 10.0  # the reference workload must complete in seconds
    # canonical contract summary block carries the metric + run stats
    assert "val_bpb:" in result["output"]
    assert "training_seconds" in result["output"]
    assert "num_params_M" in result["output"]


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
    """AC-MCP-024: parser handles BOTH formats, last occurrence wins.

    Supported formats: legacy vendor-stub `RESULT val_bpb=<float>` and the
    canonical contract summary line `val_bpb: <float>`.
    """
    out = "logging noise\nRESULT val_bpb=0.5\nRESULT val_bpb=1.234\n"
    assert parse_val_bpb(out) == 1.234
    assert parse_val_bpb("RESULT val_bpb=-2.5e-1\n") == -0.25
    assert parse_val_bpb("no RESULT line here") is None
    # summary-only output (canonical contract summary block)
    assert (
        parse_val_bpb(
            "---\nval_bpb:          3.795531\ntraining_seconds: 0.0\n---\n"
        )
        == 3.795531
    )
    # RESULT line first, then a LATER summary line -> the later one wins
    assert parse_val_bpb("RESULT val_bpb=2.5\nmore noise\nval_bpb: 9.5\n") == 9.5
    # both patterns on the SAME line -> the RESULT line wins
    assert parse_val_bpb("RESULT val_bpb=2.5 val_bpb: 9.5\n") == 2.5