"""The JUnit seconds script. IDs: AC-MCV-020..024 (PRD 30 SC-mcv-6..7).

``scripts/ci_metrics.py`` measures the runner; it does not gate it. These tests
drive it as the operator does — a subprocess with ``--junit PATH`` — and check
the three things the contract promises: a fixed-width per-suite table with a
total, an honest zero for an unusable ``time`` attribute, and exit 2 (one line,
no traceback) for a file it cannot read.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci_metrics.py"

HEADER_CELLS = ["suite", "cases", "fail", "error", "skip", "seconds"]

TWO_SUITES = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="tests.integration.test_engine_cost" tests="4" failures="1"
             errors="0" skipped="1" time="3.426">
    <testcase name="a" classname="c"><failure message="boom"/></testcase>
    <testcase name="b" classname="c"/>
    <testcase name="c" classname="c"/>
    <testcase name="d" classname="c"><skipped/></testcase>
  </testsuite>
  <testsuite name="tests.integration.test_measurement_report" tests="2"
             failures="0" errors="1" skipped="0" time="1.074">
    <testcase name="e" classname="c"/>
    <testcase name="f" classname="c"><error message="kaboom"/></testcase>
  </testsuite>
</testsuites>
"""


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def write(tmp_path, text, name="junit.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def row_for(stdout, name):
    """The table row for one suite, as cells — independent of column widths."""
    matches = [line for line in stdout.splitlines() if line.startswith(name)]
    assert len(matches) == 1, stdout
    return matches[0].split()


# ─── the table (AC-MCV-020) ──────────────────────────────────────────────────


def test_every_suite_gets_a_row_and_the_table_ends_in_a_total(tmp_path):
    """AC-MCV-020: per suite — name, cases, failures, errors, skipped and
    seconds — in a fixed-width table, then one total line that adds them up.
    """
    path = write(tmp_path, TWO_SUITES)

    result = run("--junit", str(path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].split() == HEADER_CELLS
    assert row_for(result.stdout, "tests.integration.test_engine_cost") == [
        "tests.integration.test_engine_cost", "4", "1", "0", "1", "3.43",
    ]
    assert row_for(result.stdout, "tests.integration.test_measurement_report") == [
        "tests.integration.test_measurement_report", "2", "0", "1", "0", "1.07",
    ]
    assert row_for(result.stdout, "total") == ["total", "6", "1", "1", "1", "4.50"]

    # Fixed width: every row is the same length, so the columns line up.
    widths = {len(line) for line in result.stdout.splitlines() if line}
    assert len(widths) == 1, result.stdout


def test_counts_are_derived_when_the_attributes_are_absent(tmp_path):
    """AC-MCV-020: a suite that states no counts is counted from its own
    ``<testcase>`` children — a table of zeros for a suite with cases would be
    a measurement of nothing.
    """
    text = """<testsuite name="hand.made">
    <testcase name="a" classname="c"><failure/></testcase>
    <testcase name="b" classname="c"><skipped/></testcase>
    <testcase name="c" classname="c"/>
</testsuite>
"""
    result = run("--junit", str(write(tmp_path, text)))

    assert result.returncode == 0, result.stderr
    assert row_for(result.stdout, "hand.made") == [
        "hand.made", "3", "1", "0", "1", "0.00?",
    ]


def test_a_suite_without_a_name_is_still_labelled(tmp_path):
    """AC-MCV-020: a nameless suite falls back to the enclosing element's name,
    then to a placeholder — an empty first column would hide whose numbers they
    are.
    """
    nested = """<testsuites name="suite.umbrella">
    <testsuite tests="1" time="0.5"><testcase name="a" classname="c"/></testsuite>
</testsuites>
"""
    assert row_for(
        run("--junit", str(write(tmp_path, nested, "a.xml"))).stdout, "suite.umbrella"
    ) == ["suite.umbrella", "1", "0", "0", "0", "0.50"]

    unnamed = """<testsuite tests="1" time="0.5"><testcase name="a" classname="c"/>
</testsuite>
"""
    assert row_for(
        run("--junit", str(write(tmp_path, unnamed, "b.xml"))).stdout, "<unnamed"
    )[0] == "<unnamed"


# ─── seconds are a number (AC-MCV-021) ──────────────────────────────────────


def test_a_missing_or_unusable_time_counts_as_zero_and_is_flagged(tmp_path):
    """AC-MCV-021: no ``time`` attribute, or one that is not a number, counts as
    0.0 and the row is flagged ``?`` — so a zero is never read as a measurement.
    """
    text = """<testsuites>
  <testsuite name="no.time" tests="1" failures="0" errors="0" skipped="0">
    <testcase name="a" classname="c"/>
  </testsuite>
  <testsuite name="bad.time" tests="1" failures="0" errors="0" skipped="0"
             time="--">
    <testcase name="b" classname="c"/>
  </testsuite>
  <testsuite name="real.time" tests="1" failures="0" errors="0" skipped="0"
             time="2.5">
    <testcase name="c" classname="c"/>
  </testsuite>
</testsuites>
"""
    result = run("--junit", str(write(tmp_path, text)))

    assert result.returncode == 0, result.stderr
    assert row_for(result.stdout, "no.time")[-1] == "0.00?"
    assert row_for(result.stdout, "bad.time")[-1] == "0.00?"
    assert row_for(result.stdout, "real.time")[-1] == "2.50"
    # The unusable zeros add nothing to the total, which is still a measurement.
    assert row_for(result.stdout, "total")[-1] == "2.50"


# ─── it reports a bad path once (AC-MCV-022, AC-MCV-023) ────────────────────


def test_a_missing_file_exits_two_with_one_line_on_stderr(tmp_path):
    """AC-MCV-022: a mistyped path is the operator's typo, not a traceback —
    exit 2, one line, and nothing on stdout.
    """
    missing = tmp_path / "not-there.xml"

    result = run("--junit", str(missing))

    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert str(missing) in result.stderr


def test_an_unparseable_file_exits_two_with_one_line_on_stderr(tmp_path):
    """AC-MCV-023: a file that is not XML cannot be measured; it is reported the
    same way, in one line, and the exit code is not 1 (nothing was audited).
    """
    path = write(tmp_path, "this is not xml\n")

    result = run("--junit", str(path))

    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "not parseable" in result.stderr
    assert "Traceback" not in result.stderr


# ─── the runner it measures (AC-MCV-024) ────────────────────────────────────


def test_it_reads_the_file_the_integration_job_writes(tmp_path):
    """AC-MCV-024: the real artefact — pytest's own JUnit output — is what the
    script parses, and the paths line up: the workflow writes
    ``/tmp/integration.xml`` and ``local-ci.sh`` leaves its job log under
    ``${TMPDIR:-/tmp}``, both readable by the thing that measures them.
    """
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "def test_one():\n    assert True\n\n"
        "def test_two():\n    assert True\n",
        encoding="utf-8",
    )
    xml = tmp_path / "integration.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(sample), "-q",
         "-p", "no:cacheprovider", f"--junitxml={xml}"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert xml.is_file()

    result = run("--junit", str(xml))

    assert result.returncode == 0, result.stderr
    assert row_for(result.stdout, "total")[1] == "2"

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--junitxml=/tmp/integration.xml" in workflow
    local_ci = (ROOT / "scripts" / "local-ci.sh").read_text(encoding="utf-8")
    assert 'LOG_DIR="${TMPDIR:-/tmp}"' in local_ci
    assert 'log="$LOG_DIR/act-$job.log"' in local_ci
