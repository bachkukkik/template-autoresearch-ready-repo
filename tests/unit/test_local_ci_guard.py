"""Local CI's skipped-job guard (unit tier). IDs: AC-VET-007.

VD-14 of `docs/prd/28-veteran-layer.md`: a skipped job is a failure.
`scripts/local-ci.sh` reads act's exit code and its `Job failed` marker, and
before this guard a job act skipped altogether reported `pass`. These tests
run the real script against a stub `act` first on `PATH`, so the guard is
proven behaviourally — exit code and printed status — never by matching
strings in the script's own source.
"""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "local-ci.sh"
JOB = "unit"
SKIP_MARKERS = ("Skipping unsupported platform", "Job skipped")


def _stub_act(tmp_path, lines):
    """Write an executable `act` stub into `tmp_path/bin`, return that dir."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    body = "".join(f"printf '%s\\n' {line!r}\n" for line in lines)
    stub = bindir / "act"
    source = "#!/usr/bin/env bash\n" + body + "exit 0\n"
    stub.write_text(source, encoding="utf-8")
    stub.chmod(0o755)
    return bindir


def _run_script(tmp_path, bindir):
    """Run the real script for one job, stub act first on PATH, no shell."""
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["TMPDIR"] = str(tmp_path)
    return subprocess.run(
        ["bash", str(SCRIPT), JOB],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _status_line_index(stdout):
    """Index of the one status line the script prints for the `unit` job."""
    for index, line in enumerate(stdout.splitlines()):
        if line.strip().startswith(JOB) and "(log:" in line:
            return index
    raise AssertionError(f"no status line for {JOB!r} in:\n{stdout}")


def _reason_line(stdout):
    """The `reason:` line the script prints after a FAIL status line."""
    index = _status_line_index(stdout)
    lines = stdout.splitlines()
    assert index + 1 < len(lines), f"status line is last, no reason:\n{stdout}"
    return lines[index + 1]


def test_skipped_job_fails_local_ci(tmp_path):
    """AC-VET-007: act exits 0 having written a skip marker; the script must
    mark the job FAIL, print the reason and exit non-zero."""
    for marker in SKIP_MARKERS:
        result = _run_script(tmp_path, _stub_act(tmp_path, [marker]))
        assert "FAIL" in result.stdout, (
            f"a log carrying {marker!r} reported a pass:\n{result.stdout}"
        )
        assert result.returncode == 1, (
            f"a skipped job must fail the run, got {result.returncode}"
        )
        assert "RESULT: FAILED" in result.stdout, result.stdout
        reason = _reason_line(result.stdout)
        assert reason.strip().startswith("reason:"), (
            f"the reason must follow the status line, got {reason!r}"
        )
        assert "skip" in reason.lower(), reason


def test_clean_job_still_passes(tmp_path):
    """AC-VET-007: a job that really ran — exit 0, a clean log — still
    reports pass and exits 0."""
    bindir = _stub_act(tmp_path, ["unit: 592 passed", "Job succeeded"])
    result = _run_script(tmp_path, bindir)
    assert result.returncode == 0, result.stdout + result.stderr
    status = result.stdout.splitlines()[_status_line_index(result.stdout)]
    assert "pass" in status, status
    assert "RESULT: PASSED" in result.stdout, result.stdout
    assert "reason:" not in result.stdout, "a passing job prints no reason"


def test_skip_guard_does_not_replace_the_job_failed_check(tmp_path):
    """AC-VET-007: a log carrying both a skip marker and `Job failed` still
    reports the job failure, so the new check did not shadow the old one."""
    bindir = _stub_act(tmp_path, ["Job failed", SKIP_MARKERS[0]])
    result = _run_script(tmp_path, bindir)
    assert result.returncode == 1, result.stdout
    reason = _reason_line(result.stdout).lower()
    assert "job failed" in reason, (
        f"the reason lost the job failure to the skip marker: {reason!r}"
    )


def test_failing_exit_code_is_reported_with_a_reason(tmp_path):
    """AC-VET-007: act exiting non-zero with a clean log is still a FAIL,
    and the reason names the exit code."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "act"
    stub.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    stub.chmod(0o755)
    result = _run_script(tmp_path, bindir)
    assert result.returncode == 1, result.stdout
    assert "exit" in _reason_line(result.stdout).lower(), result.stdout
