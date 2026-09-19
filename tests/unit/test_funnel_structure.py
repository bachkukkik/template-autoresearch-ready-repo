"""Funnel structure governance tests. IDs: AC-FUN-001..004."""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Product/doctrine files allowed at repo root (funnel rule 1). program.md is
# not a root file anymore — the autoresearch contract lives in contract/.
ROOT_MD_ALLOWLIST = {"AGENTS.md", "README.md", "ADOPTING.md", "PRD.md"}

HARNESS_ENTRY_POINTS = [
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".claude/skills",
    ".claude/plugins",
]

# Every directory a fresh clone needs: the funnel stages, and the tracked roots
# that are not stages (rules 10-11). Kept in step with the `doctrine` job's
# DOCTRINE_ROOTS list by AC-FUN-003 — a tracked root is a multi-file edit.
REQUIRED_DIRS = [
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
    ".agents",              # harness adapter (skills/plugins the symlinks point at)
    ".claude",              # harness symlink dir
    ".codegraph",           # graph index placeholder
    ".credentials",         # documented credential home (README + *.example only)
    ".github",              # CI itself
    "contract",             # autoresearch contract (program.md/train.py/prepare.py)
    "ops",                  # vendored artifacts for an externally operated subject
    "scripts",              # operator/verification scripts (e.g. verify-clone.sh)
    "service",              # MCP + REST research service
    "tests",                # the three tiers
]

# The `doctrine` job declares its tracked-root list on one line so it can be
# parsed here with no YAML dependency (tests/requirements.txt has no pyyaml).
DOCTRINE_ROOTS_RE = re.compile(r'^\s*DOCTRINE_ROOTS:\s*"(?P<roots>[^"]+)"\s*$', re.M)


def _doctrine_roots():
    """The doctrine job's declared tracked roots, parsed out of ci.yml."""
    match = DOCTRINE_ROOTS_RE.search(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert match, (
        f"cannot parse the doctrine job's tracked-root list out of "
        f"{CI_WORKFLOW.relative_to(REPO_ROOT)} — AC-FUN-003 needs the declaration "
        'on a single line: DOCTRINE_ROOTS: "root1 root2 …" (AGENTS.md funnel rule 11)'
    )
    return match.group("roots").split()


def test_no_stray_markdown_at_root():
    """AC-FUN-001: no stray .md at repo root outside the funnel allowlist."""
    # Symlinks (CLAUDE.md -> AGENTS.md) are harness entry points, not stray
    # documents — they are validated by AC-FUN-004.
    strays = [
        p.name
        for p in REPO_ROOT.glob("*.md")
        if not p.is_symlink() and p.name not in ROOT_MD_ALLOWLIST
    ]
    assert strays == [], f"stray .md at repo root: {strays}"


def test_funnel_stage_dirs_exist():
    """AC-FUN-002: every funnel stage directory — and every tracked root
    directory — exists in the tree."""
    missing = [rel for rel in REQUIRED_DIRS if not (REPO_ROOT / rel).is_dir()]
    assert missing == [], f"missing funnel stage / tracked root dirs: {missing}"

    # Stage 6 requires at least one verified-reality doc (docs/NN-slug.md).
    nn_docs = [
        p.name
        for p in (REPO_ROOT / "docs").glob("*.md")
        if re.match(r"^\d{2}-.*\.md$", p.name)
    ]
    assert nn_docs, "docs/ has no NN-slug.md (verified-reality) files"


def test_doctrine_job_lists_every_required_dir():
    """AC-FUN-003: the ci.yml `doctrine` job's tracked-root list and
    AC-FUN-002's REQUIRED_DIRS cannot drift — every required directory must be
    named by the job, and every directory the job names must be required here.
    Hermetic: two file reads, no git and no subprocess (the CI job derives the
    tracked set from the index; this test keeps the two literal lists honest)."""
    declared = _doctrine_roots()

    missing_from_ci = sorted(set(REQUIRED_DIRS) - set(declared))
    assert missing_from_ci == [], (
        f"AC-FUN-002 requires {missing_from_ci}, but the `doctrine` job's "
        f"DOCTRINE_ROOTS list in {CI_WORKFLOW.relative_to(REPO_ROOT)} does not name "
        "them — add each there too (AGENTS.md funnel rule 11)"
    )

    # The other direction: a directory root the job declares must be a directory
    # AC-FUN-002 asserts exists (a file entry point such as README.md is not).
    declared_dirs = {p for p in declared if (REPO_ROOT / p).is_dir()}
    not_required = sorted(declared_dirs - set(REQUIRED_DIRS))
    assert not_required == [], (
        f"the `doctrine` job declares the directory root(s) {not_required}, which "
        "AC-FUN-002 does not require — add each to REQUIRED_DIRS so a clone is "
        "checked for it (AGENTS.md funnel rule 11)"
    )


def test_harness_entry_points_resolve():
    """AC-FUN-004: harness entry points are symlinks to existing targets."""
    for rel in HARNESS_ENTRY_POINTS:
        path = REPO_ROOT / rel
        assert os.path.islink(path), f"{rel} is not a symlink"
        assert os.path.exists(path), f"{rel} symlink target does not exist"
