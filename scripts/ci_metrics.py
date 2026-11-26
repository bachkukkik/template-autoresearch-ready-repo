#!/usr/bin/env python3
"""Per-suite seconds from a JUnit XML file (PRD 30 SC-mcv-6).

Stdlib only: ``xml.etree.ElementTree`` and ``argparse``. It reads a file,
prints a fixed-width table, and writes nothing. It measures; it does not
gate — no ``--check``, no threshold: making a slow suite fail a build is a
separate decision with its own PRD.

    python3 scripts/ci_metrics.py --junit /tmp/integration.xml

The path is the one the ``integration`` CI job already writes (``pytest
--junitxml=/tmp/integration.xml``) and the one ``scripts/local-ci.sh`` leaves
its per-job log beside, so the table can be read from the runner it measures.

Per ``<testsuite>``: name, cases, failures, errors, skipped and total seconds,
then one total line. Counts come from the suite's attributes, or are counted
from its ``<testcase>`` children when an attribute is absent. Seconds come from
the suite's ``time`` attribute; a missing or non-numeric value counts as 0.0 and
the row is flagged ``?`` so the zero is never mistaken for a measurement.

Exit 0 on success; exit 2 with a one-line message on stderr when the file is
missing or is not parseable XML — the operator hears about a typo'd path once,
not as a traceback.
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

#: Column widths of the fixed table. A suite name wider than the column is
#: truncated from the left, where pytest's shared ``tests.tier.`` prefix lives.
NAME_WIDTH = 44
COUNT_WIDTH = 6
SECONDS_WIDTH = 9

UNNAMED = "<unnamed suite>"


def _number(text):
    """A float from an attribute, or ``None`` when absent or not a number."""
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def suite_name(element, parent=None):
    """The suite's name: its own ``name``, else its parent's, else a placeholder

    A pytest file always writes ``name``, but a hand-made or third-party writer
    need not, and an empty first column would hide which suite the numbers
    belong to. Falling back to the enclosing element's name keeps a nested
    ``<testsuites>`` label visible; the placeholder is the last resort.
    """
    for source in (element, parent):
        if source is None:
            continue
        name = (source.get("name") or "").strip()
        if name:
            return name
    return UNNAMED


def count_of(suite, attribute, child_tag):
    """One count: the attribute when numeric, else its ``<testcase>`` children.

    ``child_tag`` of ``testcase`` counts the cases themselves; anything else
    counts the cases carrying that child (``failure``, ``error``, ``skipped``).
    """
    value = _number(suite.get(attribute))
    if value is not None:
        return int(value)
    cases = suite.findall("testcase")
    if child_tag == "testcase":
        return len(cases)
    return sum(1 for case in cases if case.find(child_tag) is not None)


def rows_of(root):
    """One row per ``<testsuite>``: name, four counts, seconds, flag.

    The root may be a ``<testsuites>`` wrapper or a single ``<testsuite>``;
    both are what pytest writes depending on its arguments.
    """
    if root.tag == "testsuites":
        pairs = [(suite, root) for suite in root.findall("testsuite")]
    else:
        pairs = [(root, None)]
    rows = []
    for suite, parent in pairs:
        seconds = _number(suite.get("time"))
        rows.append(
            {
                "name": suite_name(suite, parent),
                "cases": count_of(suite, "tests", "testcase"),
                "failures": count_of(suite, "failures", "failure"),
                "errors": count_of(suite, "errors", "error"),
                "skipped": count_of(suite, "skipped", "skipped"),
                "seconds": 0.0 if seconds is None else seconds,
                "flag": "?" if seconds is None else "",
            }
        )
    return rows


HEADER = (
    f"{'suite':<{NAME_WIDTH}} {'cases':>{COUNT_WIDTH}} {'fail':>{COUNT_WIDTH}} "
    f"{'error':>{COUNT_WIDTH}} {'skip':>{COUNT_WIDTH}} "
    f"{'seconds':>{SECONDS_WIDTH}}"
)


def _line(name, cases, failures, errors, skipped, seconds, flag=""):
    """One fixed-width table line, the total included."""
    label = name if len(name) <= NAME_WIDTH else name[-NAME_WIDTH:]
    return (
        f"{label:<{NAME_WIDTH}} {cases:>{COUNT_WIDTH}} "
        f"{failures:>{COUNT_WIDTH}} {errors:>{COUNT_WIDTH}} "
        f"{skipped:>{COUNT_WIDTH}} {seconds:>{SECONDS_WIDTH}.2f}{flag}"
    )


def format_table(rows):
    """The header, one line per suite and one total line."""
    lines = [HEADER, "-" * len(HEADER)]
    for row in rows:
        lines.append(
            _line(
                row["name"], row["cases"], row["failures"], row["errors"],
                row["skipped"], row["seconds"], row["flag"],
            )
        )
    cases = sum(row["cases"] for row in rows)
    failures = sum(row["failures"] for row in rows)
    errors = sum(row["errors"] for row in rows)
    skipped = sum(row["skipped"] for row in rows)
    seconds = sum(row["seconds"] for row in rows)
    lines.append(_line("total", cases, failures, errors, skipped, seconds))
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ci_metrics.py",
        description="Print per-suite case counts and seconds from a JUnit XML "
        "file. It measures the runner; it does not gate it.",
    )
    parser.add_argument(
        "--junit",
        required=True,
        metavar="PATH",
        help="the JUnit XML file to read "
        "(e.g. /tmp/integration.xml, as the integration job writes it)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    path = Path(args.junit)
    if not path.is_file():
        print(f"ci_metrics: {path}: no such file", file=sys.stderr)
        return 2
    try:
        root = ET.parse(str(path)).getroot()
    except (ET.ParseError, OSError) as exc:
        # One line, no traceback: a mistyped path and a corrupt file are the
        # same answer to the operator — this file cannot be measured.
        reason = " ".join(str(exc).split())
        print(
            f"ci_metrics: {path}: not parseable XML ({reason})",
            file=sys.stderr,
        )
        return 2
    print(format_table(rows_of(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
