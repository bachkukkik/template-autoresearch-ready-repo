"""KB layout governance tests (llm-wiki spec). IDs: AC-FUN-011..012."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

KB_SECTIONS = ("concepts", "entities", "comparisons", "queries")

# The four llm-wiki raw subdirs. Only ones that exist must be real dirs.
RAW_SUBDIRS = ("articles", "papers", "transcripts", "assets")
# Allowed stray-proof top-level files in kb/raw/ itself (none shipped today).
RAW_TOP_ALLOWLIST = {"README.md", "SCHEMA.md"}


def test_kb_schema_and_index():
    """AC-FUN-011: kb/SCHEMA.md exists; kb/index.md lists every kb/ page."""
    schema = REPO_ROOT / "kb" / "SCHEMA.md"
    index = REPO_ROOT / "kb" / "index.md"
    assert schema.is_file(), "kb/SCHEMA.md is missing"
    assert index.is_file(), "kb/index.md is missing"
    index_text = index.read_text()

    missing = []
    for section in KB_SECTIONS:
        section_dir = REPO_ROOT / "kb" / section
        if not section_dir.is_dir():
            continue
        for page in sorted(section_dir.glob("*.md")):
            rel = f"{section}/{page.name}"
            if rel not in index_text:
                missing.append(rel)
    assert missing == [], f"kb/index.md does not list: {missing}"


def test_kb_raw_layout():
    """AC-FUN-012: every kb/raw/ file lives in one of the four llm-wiki subdirs."""
    raw = REPO_ROOT / "kb" / "raw"
    assert raw.is_dir(), "kb/raw/ is missing"

    for sub in RAW_SUBDIRS:
        d = raw / sub
        if d.exists():
            assert d.is_dir(), f"kb/raw/{sub} exists but is not a directory"

    strays = []
    for p in raw.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(raw)
        if rel.parts[0] not in RAW_SUBDIRS and rel.parts[0] not in RAW_TOP_ALLOWLIST:
            strays.append(str(rel))
    assert strays == [], f"stray files in kb/raw/: {strays}"