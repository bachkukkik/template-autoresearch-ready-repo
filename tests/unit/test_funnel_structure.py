"""Funnel structure governance tests. IDs: AC-FUN-001..003."""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Product/doctrine files allowed at repo root (funnel rule 1). program.md may or
# may not exist yet — tolerating absence/presence is handled by the allowlist.
ROOT_MD_ALLOWLIST = {"AGENTS.md", "README.md", "PRD.md", "program.md"}

HARNESS_ENTRY_POINTS = [
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".claude/skills",
    ".claude/plugins",
]


def test_no_stray_markdown_at_root():
    """AC-FUN-001: no stray .md at repo root outside the funnel allowlist."""
    # Symlinks (CLAUDE.md -> AGENTS.md) are harness entry points, not stray
    # documents — they are validated by AC-FUN-003.
    strays = [
        p.name
        for p in REPO_ROOT.glob("*.md")
        if not p.is_symlink() and p.name not in ROOT_MD_ALLOWLIST
    ]
    assert strays == [], f"stray .md at repo root: {strays}"


def test_funnel_stage_dirs_exist():
    """AC-FUN-002: every funnel stage directory exists."""
    required = [
        "scratchpads",          # stage 1
        "kb/raw",               # stage 2
        "kb",                   # stage 3
        "kb/concepts",
        "kb/entities",
        "kb/comparisons",
        "kb/queries",
        "docs/prd",             # stage 4
        "docs/gaps",            # stage 5
        "docs",                 # stage 6
    ]
    missing = [rel for rel in required if not (REPO_ROOT / rel).is_dir()]
    assert missing == [], f"missing funnel stage dirs: {missing}"

    # Stage 6 requires at least one verified-reality doc (docs/NN-slug.md).
    nn_docs = [
        p.name
        for p in (REPO_ROOT / "docs").glob("*.md")
        if re.match(r"^\d{2}-.*\.md$", p.name)
    ]
    assert nn_docs, "docs/ has no NN-slug.md (verified-reality) files"


def test_harness_entry_points_resolve():
    """AC-FUN-003: harness entry points are symlinks to existing targets."""
    for rel in HARNESS_ENTRY_POINTS:
        path = REPO_ROOT / rel
        assert os.path.islink(path), f"{rel} is not a symlink"
        assert os.path.exists(path), f"{rel} symlink target does not exist"