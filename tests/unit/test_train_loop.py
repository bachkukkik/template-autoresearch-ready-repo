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
    """AC-TPL-023: crash rows record 0.000000 / 0.000 with status 'crash'."""
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
    assert float(cols[2]) == 0.0  # crash memory is numeric zero
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


def _statuses(results_path):
    """The status column of every data row, in order."""
    with open(results_path) as f:
        return [line.split("\t")[3] for line in f.read().splitlines()[1:]]


def test_budget_is_checked_in_loop_and_reports_budget(monkeypatch, capsys):
    """AC-TPL-024: the loop stops at the deadline and says so (stop_reason)."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 0)  # deadline already elapsed
    t0 = time.time()
    val_bpb = train.run(results_path=None)
    assert time.time() - t0 < 5.0  # no wall-clock wait
    assert isinstance(val_bpb, float)
    out = capsys.readouterr().out
    assert "stop_reason:" in out
    assert "budget" in out


def test_default_run_converges_under_the_budget_ceiling(monkeypatch, capsys):
    """AC-TPL-024: TIME_BUDGET is a ceiling — a converged run finishes at once."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 300)
    t0 = time.time()
    train.run(results_path=None)
    elapsed = time.time() - t0
    out = capsys.readouterr().out
    assert "stop_reason:" in out
    assert "converged" in out
    assert elapsed < 5.0  # the 300s ceiling is a bound, not a wait


def test_results_status_is_decided_by_the_evaluator(tmp_path, monkeypatch):
    """AC-TPL-026: --results writes decide()'s status, not a hard-coded keep.

    The first (baseline) row is a keep; a byte-identical second candidate is a
    discard — the exact opposite of hard-coding 'keep' (the C2 defect).
    """
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    results_path = str(tmp_path / "results.tsv")
    train.run(results_path=results_path)  # baseline -> keep
    train.run(results_path=results_path)  # identical metric -> discard
    assert _statuses(results_path) == ["keep", "discard"]


def test_results_keeps_a_candidate_better_than_the_incumbent(tmp_path, monkeypatch):
    """AC-TPL-026: a metric below the ledger's best keep is recorded as keep."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    results_path = str(tmp_path / "results.tsv")
    train.log_result(results_path, commit="0000000", val_bpb=9.999999,
                     memory_gb=0.0, status="keep", description="weak baseline")
    train.run(results_path=results_path)
    assert _statuses(results_path) == ["keep", "keep"]


def test_results_discards_a_candidate_worse_than_the_incumbent(tmp_path, monkeypatch):
    """AC-TPL-026: a metric above the ledger's best keep is recorded as discard."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    results_path = str(tmp_path / "results.tsv")
    train.log_result(results_path, commit="0000000", val_bpb=1.000000,
                     memory_gb=0.0, status="keep", description="strong baseline")
    train.run(results_path=results_path)
    assert _statuses(results_path) == ["keep", "discard"]


def test_main_takes_results_and_description_args(tmp_path, monkeypatch):
    """AC-TPL-026: --results + --description append a row without hand-editing."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    results_path = str(tmp_path / "results.tsv")
    train.main(["--results", results_path, "--description", "cli row"])
    row = open(results_path).read().splitlines()[1].split("\t")
    assert row[4] == "cli row"
    assert row[3] in STATUSES


def test_peak_rss_is_measured():
    """AC-TPL-028: memory is measured from the host, not a placeholder 0.0."""
    gb = train.peak_rss_gb()
    assert isinstance(gb, float)
    assert gb > 0.0


def test_results_memory_column_is_measured(tmp_path, monkeypatch):
    """AC-TPL-028: the results.tsv memory_gb column carries a real measurement."""
    monkeypatch.setattr(prepare, "TIME_BUDGET", 1)
    results_path = str(tmp_path / "results.tsv")
    train.run(results_path=results_path)
    memory_gb = float(open(results_path).read().splitlines()[1].split("\t")[2])
    assert memory_gb > 0.0