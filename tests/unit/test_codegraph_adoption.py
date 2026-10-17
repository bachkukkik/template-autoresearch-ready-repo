"""CodeGraph adoption-surface tests (hermetic). IDs: AC-CG-001..006.

The repo adopts CodeGraph as its primary agent graph search; these tests pin the
adoption SURFACE a red PR could actually break — `AGENTS.md` `## codegraph` and
the harness adapter, the gitignore rule for the local index, the stage-3 kb
grounding, and the stage-4/stage-6 PRD pair.

Hermetic: file reads and stdlib only, with one exception — AC-CG-004 reads the git
index through a `git` subprocess behind the ambient preflight, because
"git tracks nothing under .codegraph/" is a property of the index and not of any
file. The optional `codegraph` binary is Node and not guaranteed present on a CI
runner, so nothing here shells out to it, and nothing asserts the contents of the
gitignored `.codegraph/` index — that is the ambient-dependency class the unit tier
forbids.
"""
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"
GITIGNORE = REPO_ROOT / ".gitignore"
PRD_MD = REPO_ROOT / "PRD.md"
PRD_STAGE4 = REPO_ROOT / "docs" / "prd" / "07-codegraph-adoption.md"
DOC_STAGE6 = REPO_ROOT / "docs" / "07-codegraph-adoption.md"

KB_GROUNDING_RAW = "raw/articles/codegraph-mcp-code-intelligence.md"
KB_PAGES = (
    REPO_ROOT / "kb" / "entities" / "codegraph.md",
    REPO_ROOT / "kb" / "concepts" / "agent-code-graph-search.md",
    REPO_ROOT / "kb" / "comparisons" / "codegraph-vs-graphify.md",
)
KB_RAW_ARTICLE = REPO_ROOT / "kb" / "raw" / "articles" / "codegraph-mcp-code-intelligence.md"


def _read(path):
    """The text of a tracked file, with the read failure named by its path."""
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


def _section_body(text, heading):
    """The body of `## <heading>`, up to the next level-2 heading ('' if absent).

    A `###` subsection stays inside the body — only `## ` splits.
    """
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        name, _, body = part.partition("\n")
        if name.strip() == heading:
            return body
    return ""


def test_agents_codegraph_section_names_primary_graph_search_and_prd():
    """AC-CG-001: `AGENTS.md` carries the `## codegraph` section, names CodeGraph
    the primary graph search, documents the one-tool `codegraph_explore` surface,
    and points at the stage-4 PRD (`docs/prd/07-codegraph-adoption.md`)."""
    body = _section_body(_read(AGENTS_MD), "codegraph")
    assert body, "AGENTS.md has no '## codegraph' section — the adoption is unstated"
    assert "primary graph search" in body, (
        "## codegraph no longer names CodeGraph the primary graph search"
    )
    assert re.search(r"one\s+(?:mcp\s+)?tool\s+by\s+design", body, re.I), (
        "## codegraph no longer documents the one-tool MCP surface"
    )
    assert "codegraph_explore" in body, (
        "## codegraph no longer names the single exposed MCP tool, codegraph_explore"
    )
    assert "docs/prd/07-codegraph-adoption.md" in body, (
        "## codegraph no longer points at the stage-4 PRD"
    )


def test_cli_twins_fallback_documented_for_a_harness_without_mcp():
    """AC-CG-002: the adapter documents the CLI-twins fallback for a harness with
    no MCP client — in `## codegraph` and in the Harness-Adapter per-harness row."""
    text = _read(AGENTS_MD)
    body = _section_body(text, "codegraph")
    assert re.search(r"without an MCP client", body, re.I), (
        "## codegraph no longer addresses harnesses without an MCP client"
    )
    assert "use the CLI twins" in body, (
        "## codegraph no longer states the CLI-twins fallback"
    )
    assert "codegraph explore|node|callers|callees|impact|query|affected" in body, (
        "## codegraph no longer lists the CLI twins"
    )
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("|") and "no MCP client" in line
    ]
    assert rows, (
        "the Harness Adapter's per-harness rows lost the no-MCP-client binding "
        "to the codegraph CLI twins"
    )
    assert any("codegraph explore" in row for row in rows), (
        "the no-MCP-client harness row no longer names the codegraph CLI twins"
    )


def test_do_not_track_stated_for_scripted_runs():
    """AC-CG-003: any CI or scripted codegraph run sets `DO_NOT_TRACK=1` — the
    telemetry opt-out is stated, not implied.

    The 20k context-file trim tightened `## codegraph`: it now scopes the
    opt-out to scripted runs and delegates the CI half to the stage-4 PRD the
    section points at. So the claim is asserted where it is stated, and the
    pointer is made load-bearing — deleting the scope from either file fails
    here, and the full "CI or scripted" wording cannot be dropped silently.
    """
    body = _section_body(_read(AGENTS_MD), "codegraph")
    assert "DO_NOT_TRACK=1" in body, (
        "## codegraph no longer states the DO_NOT_TRACK=1 telemetry opt-out"
    )
    assert re.search(r"scripted[^.]*DO_NOT_TRACK=1|DO_NOT_TRACK=1[^.]*scripted", body, re.I), (
        "## codegraph no longer ties DO_NOT_TRACK=1 to scripted runs"
    )

    pointer = re.search(r"docs/prd/[\w./-]+\.md", body)
    assert pointer, "## codegraph no longer points at its stage-4 PRD"
    prd = _read(REPO_ROOT / pointer.group(0))
    assert "CI or scripted" in prd, (
        f"{pointer.group(0)}, which ## codegraph points at for the full scope, no "
        "longer states that the DO_NOT_TRACK=1 opt-out covers CI runs as well as "
        "scripted ones"
    )


def test_codegraph_index_ignored_wholesale(require_tool):
    """AC-CG-004: `.codegraph/` is ignored WHOLESALE (upstream's rule) and git
    tracks nothing under it.

    `.gitignore` carries the single directory rule `.codegraph/` — no
    ignore-then-unignore pair — so the whole local index, including the
    `.codegraph/.gitignore` codegraph writes for itself, stays out of `git status`.
    The tracked-ness half is read from the git index through a `git` subprocess
    behind the ambient preflight; the `codegraph` binary is still never invoked.
    """
    lines = [line.strip() for line in _read(GITIGNORE).splitlines()]
    assert ".codegraph/" in lines, (
        ".gitignore no longer ignores .codegraph/ — the local index would reach "
        "`git status`"
    )
    assert ".codegraph/*" not in lines, (
        ".gitignore enumerates .codegraph/* again; the wholesale directory rule is "
        "what keeps codegraph's own .codegraph/.gitignore out of `git status`"
    )
    assert not (REPO_ROOT / ".codegraph" / ".gitkeep").exists(), (
        "a .codegraph placeholder is back — the directory is ignored wholesale, so "
        "it must ship no tracked file"
    )

    git = require_tool("git")  # the tracked-ness claim is a property of the git index

    ignored = subprocess.run(
        [git, "check-ignore", "-q", ".codegraph/codegraph.db"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ignored.returncode == 0, (
        ".codegraph/codegraph.db is not gitignored — the whole directory must be"
    )

    tracked = subprocess.run(
        [git, "ls-files", "--", ".codegraph"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert tracked.returncode == 0, f"git ls-files failed: {tracked.stderr.strip()}"
    assert tracked.stdout.strip() == "", (
        f"git still tracks {tracked.stdout.split()!r} under .codegraph/ — nothing "
        "under the local index may be committed"
    )


def test_stage3_kb_grounding_pages_and_raw_article_exist():
    """AC-CG-005: the stage-3 grounding exists — the raw CodeGraph article plus
    the three layer-2 kb pages (entity, concept, comparison) that cite it."""
    assert KB_RAW_ARTICLE.is_file(), (
        "kb/raw/articles/codegraph-mcp-code-intelligence.md is missing — the "
        "adoption has no raw source"
    )
    for page in KB_PAGES:
        text = _read(page)
        assert KB_GROUNDING_RAW in text, (
            f"{page.relative_to(REPO_ROOT)} no longer cites {KB_GROUNDING_RAW}"
        )


def test_stage4_and_stage6_doc_pair_tracked_by_prd_md():
    """AC-CG-006: the stage-4 intent / stage-6 reality pair exists, and `PRD.md`
    lists topic 07 (the per-topic link every funnel layer shares)."""
    assert PRD_STAGE4.is_file(), "docs/prd/07-codegraph-adoption.md is missing"
    assert DOC_STAGE6.is_file(), "docs/07-codegraph-adoption.md is missing"
    prd_md = _read(PRD_MD)
    assert "docs/prd/07-codegraph-adoption.md" in prd_md, (
        "PRD.md no longer links the stage-4 CodeGraph PRD"
    )
    assert "docs/07-codegraph-adoption.md" in prd_md, (
        "PRD.md no longer links the stage-6 CodeGraph doc"
    )
