"""Gap lifecycle governance tests. ID: AC-FUN-021."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAPS_DIR = REPO_ROOT / "docs" / "gaps"
ARCHIVE_DIR = GAPS_DIR / "_archive"

# A gap file is `NN-slug.md`; docs/gaps/README.md carries no NN and is excluded.
GAP_FILE_RE = re.compile(r"^\d{2}.*\.md$")
STATUS_RE = re.compile(r"^\*\*Status:\*\* (\w+)\s*$", re.M)

# The contract docs/gaps/README.md fixes for a gap file, and the sections of
# README.md this check depends on (funnel rule 7; docs/gaps/README.md is the
# single statement of the lifecycle).
REQUIRED_GAP_SECTIONS = ("## Observation", "## Evidence", "## Impact", "## Resolution")
REQUIRED_README_SECTIONS = (
    "## Naming",
    "## Required sections",
    "## Lifecycle",
    "## Open gaps",
)
VALID_STATUSES = ("open", "resolved", "withdrawn")


def _gap_files(directory):
    """Sorted `NN-*.md` files directly in `directory`."""
    return sorted(p for p in directory.glob("*.md") if GAP_FILE_RE.match(p.name))


def _status(text):
    """The gap's `**Status:**` value, or None when the line is absent."""
    match = STATUS_RE.search(text)
    return match.group(1) if match else None


def test_gap_lifecycle():
    """AC-FUN-021: the gap machinery is present and real; every LIVE gap file
    carries the required sections and a Resolution; an open gap is listed in
    docs/gaps/README.md.

    The live set may legitimately be EMPTY — a resolved gap is archived inside
    the repo (`docs/gaps/_archive/`, never deleted), so the archive is the
    always-present input that keeps this check from passing vacuously."""
    readme = GAPS_DIR / "README.md"
    assert readme.is_file(), "docs/gaps/README.md is missing"
    readme_text = readme.read_text(encoding="utf-8")
    for section in REQUIRED_README_SECTIONS:
        assert section in readme_text, (
            f"docs/gaps/README.md lost its '{section}' section — the gap "
            "lifecycle contract (AGENTS.md funnel rule 7) is unenforced"
        )

    # The archive is what a closed gap becomes: read it in full, so this check
    # has real gap records behind it even when no gap is open.
    archived = _gap_files(ARCHIVE_DIR)
    assert archived, (
        "docs/gaps/_archive/ holds no NN-*.md files — the archive scan is wrong "
        "(a resolved gap is archived inside the repo, never deleted)"
    )
    archived_statuses = {}
    for gap in archived:
        status = _status(gap.read_text(encoding="utf-8"))
        assert status, f"docs/gaps/_archive/{gap.name} carries no '**Status:**' line"
        archived_statuses[gap.name] = status
    assert {"resolved", "withdrawn"} & set(archived_statuses.values()), (
        "no archived gap is resolved or withdrawn — the archive read is not "
        f"reaching real gap records: {archived_statuses}"
    )

    # Live gaps — legitimately zero today; the loop still runs, and still bites,
    # the moment one exists.
    for gap in _gap_files(GAPS_DIR):
        text = gap.read_text(encoding="utf-8")
        for section in REQUIRED_GAP_SECTIONS:
            assert section in text, f"{gap.name} is missing its '{section}' section"
        status = _status(text)
        assert status, f"{gap.name} carries no '**Status:**' line"
        assert status in VALID_STATUSES, (
            f"{gap.name} has Status '{status}' — expected one of {VALID_STATUSES}"
        )
        if status == "open":
            assert gap.name in readme_text, (
                f"open gap {gap.name} is not listed in docs/gaps/README.md"
            )
