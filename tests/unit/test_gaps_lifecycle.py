"""Gap lifecycle governance tests. ID: AC-FUN-021."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

GAP_FILE_RE = re.compile(r"^\d{2}.*\.md$")


def test_gap_lifecycle():
    """AC-FUN-021: every gap file has a Resolution section; open gaps are listed."""
    gaps_dir = REPO_ROOT / "docs" / "gaps"
    readme = gaps_dir / "README.md"
    assert readme.is_file(), "docs/gaps/README.md is missing"
    readme_text = readme.read_text()

    gap_files = sorted(p for p in gaps_dir.glob("*.md") if GAP_FILE_RE.match(p.name))
    assert gap_files, "no docs/gaps/NN-*.md files found"

    for gap in gap_files:
        text = gap.read_text()
        assert "## Resolution" in text, (
            f"{gap.name} is missing a Resolution section"
        )
        if "**Status:** open" in text:
            assert gap.name in readme_text, (
                f"open gap {gap.name} is not listed in docs/gaps/README.md"
            )