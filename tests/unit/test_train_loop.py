"""SC3 — train.py runs within budget and logs results.tsv. IDs: AC-TPL-02N."""
import os
import time

import prepare
import train

STATUSES = ("keep", "discard", "crash")


def test_run_within_budget_prints_summary(monkeypatch, capsys, tmp_path):
    """AC-TPL-021: monkeypatched 1s budget completes fast and prints summary."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)  # never actually wait
    t0 = time.time()
    val_bpb = train.run(results_path=None)
    elapsed = time.time() - t0
    assert elapsed < 5.0  # hard cap: tests must be fast
    assert isinstance(val_bpb, float)
    out = capsys.readouterr().out
    for key in ("val_bpb:", "training_seconds:", "total_seconds:",
                "peak_vram_mb:", "num_steps:", "num_params_M:"):
        assert key in out


def test_results_tsv_written_exact_header_and_valid_row(tmp_path):
    """AC-TPL-022: results.tsv has exact header + one valid status row."""
    results_path = str(tmp_path / "results.tsv")
    train.run(results_path=results_path)
    with open(results_path) as f:
        lines = f.read().splitlines()
    assert lines[0] == "commit\tval_bpb\tmemory_gb\tstatus\tdescription"
    assert len(lines) == 2  # header + one row
    cols = lines[1].split("\t")
    assert len(cols) == 5
    commit, val_bpb, memory_gb, status, desc = cols
    assert len(commit) == 7
    assert status in STATUSES
    float(val_bpb)  # parseable
    float(memory_gb)
    assert desc


def test_crash_logging(tmp_path):
    """AC-TPL-023: crash rows record 0.000000 / 0.0 with status 'crash'."""
    results_path = str(tmp_path / "results.tsv")
    train.log_result(results_path, commit="0123456", val_bpb=0.0,
                     memory_gb=0.0, status="crash",
                     description="double model width (OOM)")
    with open(results_path) as f:
        lines = f.read().splitlines()
    assert lines[0] == "commit\tval_bpb\tmemory_gb\tstatus\tdescription"
    cols = lines[1].split("\t")
    assert cols[0] == "0123456"
    assert cols[1] == "0.000000"
    assert cols[2] == "0.0"
    assert cols[3] == "crash"
    # appending keeps header once
    train.log_result(results_path, commit="1234567", val_bpb=0.5,
                     memory_gb=0.0, status="discard", description="worse")
    with open(results_path) as f:
        lines = f.read().splitlines()
    assert lines[0] == "commit\tval_bpb\tmemory_gb\tstatus\tdescription"
    assert len(lines) == 3


def test_run_does_not_write_to_repo_root(monkeypatch, capsys):
    """AC-TPL-021b: no results path -> nothing written to the repo root."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    results_path = os.path.join(repo_root, "results.tsv")
    existed_before = os.path.exists(results_path)  # never delete live data
    train.run(results_path=None)
    # run() with no results path must not create/modify the repo-root ledger
    assert os.path.exists(results_path) == existed_before