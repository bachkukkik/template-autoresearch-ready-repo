"""SC8/SC9 — evaluator-owned decision + ledger checker. IDs: AC-TPL-025, AC-TPL-027.

Both live in the frozen evaluator (`contract/prepare.py`), never in the agent's
`train.py`: the agent cannot award itself a `keep` (that is the anti-cheat
surface), and the ledger it appends to is validated by the same frozen file.
Hermetic: stdlib only, one subprocess for the CLI exit-code contract.
"""
import subprocess
import sys
from pathlib import Path

import prepare

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "contract"
HEADER = "commit\tval_bpb\tmemory_gb\tstatus\tdescription"


def _write(tmp_path, *rows, name="results.tsv"):
    """Write a ledger with the exact header plus `rows`, return its path."""
    path = tmp_path / name
    path.write_text("\n".join((HEADER,) + rows) + "\n")
    return str(path)


# --- decide(): the evaluator-owned keep/discard decision -------------------


def test_decide_direction_and_noise_floor_are_declared():
    """AC-TPL-025: the evaluator owns DIRECTION and a positive NOISE_FLOOR."""
    assert prepare.DIRECTION == "lower"
    assert isinstance(prepare.NOISE_FLOOR, float)
    assert 0.0 < prepare.NOISE_FLOOR < 0.1


def test_decide_baseline_is_kept():
    """AC-TPL-025: no incumbent (the first/baseline run) -> keep."""
    assert prepare.decide(3.7, None) == "keep"
    assert prepare.decide(0.0, None) == "keep"


def test_decide_strict_improvement_beyond_noise_floor_is_kept():
    """AC-TPL-025: lower is better; a change beyond the noise floor is a keep."""
    # 3.70 vs incumbent 3.80 is a 2.6% gain — well outside the noise floor.
    assert prepare.decide(3.70, 3.80) == "keep"


def test_decide_within_noise_floor_discards_unless_it_shrinks():
    """AC-TPL-025: inside the noise floor the simplicity criterion decides.

    A tie is a discard; an epsilon-sized gain is only a keep when the artifact
    also shrinks (the noise-floor rule from the calibration lessons).
    """
    assert prepare.decide(3.800, 3.800) == "discard"          # exact tie
    assert prepare.decide(3.798, 3.800) == "discard"          # inside noise floor
    assert prepare.decide(3.798, 3.800, shrinks=True) == "keep"  # ... but simpler


def test_decide_worse_is_discarded():
    """AC-TPL-025: a worse metric never yields a keep (the C2 defect)."""
    assert prepare.decide(3.90, 3.80) == "discard"
    assert prepare.decide(3.90, 3.80, shrinks=True) == "discard"


def test_decide_respects_direction_higher():
    """AC-TPL-025: DIRECTION is a parameter — 'higher' inverts the rule."""
    assert prepare.decide(0.96, 0.94, direction="higher") == "keep"
    assert prepare.decide(0.94, 0.94, direction="higher") == "discard"
    assert prepare.decide(0.93, 0.94, direction="higher") == "discard"


# --- check_ledger(): the append-only ledger contract -----------------------


def test_check_ledger_accepts_a_clean_ledger(tmp_path):
    """AC-TPL-027: baseline-keep + equal-discard + crash is a valid ledger."""
    path = _write(
        tmp_path,
        "aaaaaaa\t3.800000\t0.012\tkeep\tbaseline",
        "bbbbbbb\t3.800000\t0.012\tdiscard\tsame bigram, no gain",
        "ccccccc\t0.000000\t0.000\tcrash\tdouble the width (OOM)",
        "ddddddd\t3.500000\t0.013\tkeep\tlower lr",
        "eeeeeee\t3.500000\t0.013\tdiscard\ttypo fix, no gain",
    )
    assert prepare.check_ledger(path) == []


def test_check_ledger_rejects_a_worse_keep_row(tmp_path):
    """AC-TPL-027: a keep row worse than the incumbent beyond the noise floor is
    the C2 defect — a worse candidate may not be recorded as keep."""
    path = _write(
        tmp_path,
        "aaaaaaa\t3.700000\t0.012\tkeep\tbaseline",
        "bbbbbbb\t3.900000\t0.012\tkeep\tworse, but claimed as keep",
    )
    violations = prepare.check_ledger(path)
    assert violations, "a worse keep row was accepted"
    assert any("keep" in v for v in violations), violations


def test_check_ledger_allows_a_within_noise_floor_keep(tmp_path):
    """AC-TPL-027: an epsilon-sized keep is legal (shrink is not recorded)."""
    path = _write(
        tmp_path,
        "aaaaaaa\t3.700000\t0.012\tkeep\tbaseline",
        "bbbbbbb\t3.699500\t0.012\tkeep\tsimplify, within noise floor",
    )
    assert prepare.check_ledger(path) == []


def test_check_ledger_rejects_a_bad_header_or_column_count(tmp_path):
    """AC-TPL-027: the exact header and 5 tab columns are enforced."""
    bad_header = tmp_path / "bad_header.tsv"
    bad_header.write_text("commit\tval_bpb\tstatus\tdescription\n")
    assert prepare.check_ledger(str(bad_header))

    cols = _write(tmp_path, "aaaaaaa\t3.800000\tkeep\tmissing memory column")
    assert prepare.check_ledger(cols)

    header_only = tmp_path / "header_only.tsv"
    header_only.write_text(HEADER + "\n")
    assert prepare.check_ledger(str(header_only))


def test_check_ledger_rejects_unknown_status_and_short_commit(tmp_path):
    """AC-TPL-027: status vocabulary and the 7-char commit are enforced."""
    status = _write(tmp_path, "aaaaaaa\t3.800000\t0.012\tkept\tbogus status")
    assert prepare.check_ledger(status)

    commit = _write(tmp_path, "abc\t3.800000\t0.012\tkeep\tshort commit")
    assert prepare.check_ledger(commit)


def test_check_ledger_rejects_a_non_keep_first_row(tmp_path):
    """AC-TPL-027: the first data row is the baseline and must be a keep."""
    path = _write(tmp_path, "aaaaaaa\t3.800000\t0.012\tdiscard\tno baseline")
    violations = prepare.check_ledger(path)
    assert violations
    assert any("baseline" in v for v in violations), violations


def test_check_ledger_rejects_a_crash_row_with_a_metric(tmp_path):
    """AC-TPL-027: crash rows carry 0.000000 val_bpb and 0.000 memory_gb."""
    path = _write(
        tmp_path,
        "aaaaaaa\t3.800000\t0.012\tkeep\tbaseline",
        "bbbbbbb\t3.700000\t0.012\tcrash\tcrash that still scored",
    )
    assert prepare.check_ledger(path)


def test_check_ledger_reports_a_missing_file(tmp_path):
    """AC-TPL-027: a missing ledger is a violation, not a crash."""
    violations = prepare.check_ledger(str(tmp_path / "nope.tsv"))
    assert violations and any("missing" in v.lower() for v in violations)


def test_check_ledger_cli_exit_codes(tmp_path):
    """AC-TPL-027: `prepare.py --check-ledger` exits 0 clean / 1 on violations."""
    clean = _write(tmp_path, "aaaaaaa\t3.800000\t0.012\tkeep\tbaseline",
                   name="clean.tsv")
    dirty = _write(tmp_path, "aaaaaaa\t3.800000\t0.012\tdiscard\tno baseline",
                   name="dirty.tsv")
    for path, expected in ((clean, 0), (dirty, 1)):
        proc = subprocess.run(
            [sys.executable, "prepare.py", "--check-ledger", path],
            cwd=str(CONTRACT), capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == expected, (path, proc.stdout, proc.stderr)


def test_check_ledger_reports_multiple_violations(tmp_path):
    """AC-TPL-027: every violation is reported, not just the first."""
    path = _write(
        tmp_path,
        "aaaaaaa\t3.800000\t0.012\tdiscard\tno baseline",
        "bad\tnot-a-float\t0.012\tkept\tbad status and commit",
    )
    assert len(prepare.check_ledger(path)) >= 3
