"""Stage-6 documentary-invariant guard (unit tier). IDs: AC-DOC-001..016.

Enforces the invariants this repo states but only partly checks in CI: the
stage-6 section template (`coding-agents-docs-guideline`), the
What Fails -> Resolution parity doctrine, the three catalog tables
(`docs/README.md`, `docs/gaps/README.md`, `PRD.md`) and cross-layer `NN`
alignment. Hermetic: file reads and stdlib parsing only.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
PRD_MD = REPO_ROOT / "PRD.md"
GAPS = DOCS / "gaps"
GAPS_ARCHIVE = GAPS / "_archive"

# The eight stage-6 sections, in the order the `coding-agents-docs-guideline`
# skill fixes them. None may be missing, renamed, merged or reordered.
TEMPLATE_SECTIONS = (
    "What",
    "Why",
    "How",
    "Verification",
    "What Works",
    "What Fails",
    "Resolution",
    "Verdict",
)

NN_FILE_RE = re.compile(r"^(\d{2})-.*\.md$")
FENCE_RE = re.compile(r"```.*?```", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
SECTION_SPLIT_RE = re.compile(r"^##\s+", re.M)
BULLET_RE = re.compile(r"^-\s+", re.M)
LINK_RE = re.compile(r"\]\(([^)]+)\)")


# --- text parsing ----------------------------------------------------------


def strip_fenced_blocks(text):
    """Remove fenced code blocks so headings inside a ``` fence are invisible.

    A stage-6 doc legitimately illustrates literal headings inside a fence
    (docs/05 carries `# tiers 1+2 (no container)`), so every heading parse
    runs on the stripped text.
    """
    return FENCE_RE.sub("", text)


def parse_headings(text):
    """(level, title) for every ATX heading outside a fenced code block."""
    return [
        (len(m.group(1)), m.group(2).strip())
        for m in HEADING_RE.finditer(strip_fenced_blocks(text))
    ]


def parse_sections(text):
    """The level-2 section titles of a stage-6 doc, in document order."""
    return [title for level, title in parse_headings(text) if level == 2]


def _section_body(text, title):
    """Body of the `## <title>` section, up to the next level-2 heading."""
    parts = SECTION_SPLIT_RE.split(strip_fenced_blocks(text))
    for part in parts[1:]:
        name, _, body = part.partition("\n")
        if name.strip() == title:
            return body
    return None


def parse_table_rows(text):
    """Real markdown table rows, as the list of link targets each row carries.

    A row is a line starting with `|`, outside a fenced code block, that
    contains a markdown link `](`. Prose and bullet lists are never rows —
    `docs/gaps/README.md` names withdrawn gap files in a bullet list, and
    parsing that as rows would flag the repo's own intended state.
    """
    rows = []
    for line in strip_fenced_blocks(text).splitlines():
        if not line.startswith("|"):
            continue
        links = LINK_RE.findall(line)
        if links:
            rows.append(links)
    return rows


def _basename(link):
    """The file name a markdown link target points at, anchor stripped."""
    return link.split("#", 1)[0].rsplit("/", 1)[-1]


def _nn_of(filename):
    """The two-digit `NN` a funnel file name carries."""
    match = NN_FILE_RE.match(filename)
    assert match, f"{filename} is not a NN-slug.md file name"
    return match.group(1)


# --- findings helpers (empty list == conformant) ---------------------------


def check_section_order(text):
    """Findings for one stage-6 doc: its `## ` sections must be exactly the
    eight template sections, in template order, none duplicated."""
    found = parse_sections(text)
    findings = []
    missing = [s for s in TEMPLATE_SECTIONS if s not in found]
    if missing:
        findings.append(f"missing section(s): {missing}")
    extra = [s for s in found if s not in TEMPLATE_SECTIONS]
    if extra:
        findings.append(f"unexpected section(s): {extra}")
    present = [s for s in found if s in TEMPLATE_SECTIONS]
    expected = [s for s in TEMPLATE_SECTIONS if s in found]
    if present != expected:
        findings.append(f"sections out of order or duplicated: {present}")
    return findings


def check_fails_resolution_parity(text):
    """Findings for one stage-6 doc: `## What Fails` and `## Resolution` must
    carry the SAME number of top-level bullets — one resolution per failure,
    same order. Strict equality, not a subset check."""
    fails_body = _section_body(text, "What Fails")
    resolution_body = _section_body(text, "Resolution")
    if fails_body is None or resolution_body is None:
        return ["What Fails or Resolution section not found — parity not checked"]
    fails = len(BULLET_RE.findall(fails_body))
    resolutions = len(BULLET_RE.findall(resolution_body))
    if fails != resolutions:
        return [f"What Fails has {fails} bullet(s) but Resolution has {resolutions}"]
    return []


def check_catalog_rows(readme_text, expected_files, label):
    """Findings for a catalog table: every expected file has exactly one row,
    and every row's first link resolves to an expected file."""
    expected = set(expected_files)
    targets = [links[0] for links in parse_table_rows(readme_text)]
    findings = []
    for name in sorted(expected):
        count = sum(1 for target in targets if _basename(target) == name)
        if count != 1:
            findings.append(f"{label}: {name} has {count} row(s), expected exactly 1")
    for target in targets:
        if _basename(target) not in expected:
            findings.append(
                f"{label}: row points at {target!r}, which is not a catalogued file"
            )
    return findings


def check_nn_consistency(live_gaps, archived_gaps, topic_nns):
    """Findings for cross-layer `NN` alignment.

    `live_gaps`/`archived_gaps` map file name -> text. Every `NN` used under
    `docs/gaps/` must have a topic file in `docs/` or `docs/prd/`. `NN`s among
    LIVE gaps must be unique. A gap `NN` held by both a live and an archived
    file is allowed only when the archived occupant is a withdrawn tombstone.
    Archive-internal multiplicity is documented practice and is not flagged.
    """
    findings = []
    for name, text in sorted({**live_gaps, **archived_gaps}.items()):
        nn = _nn_of(name)
        if nn not in topic_nns:
            findings.append(f"{name}: NN {nn} has no docs/ or docs/prd/ topic file")
    seen = {}
    for name in sorted(live_gaps):
        nn = _nn_of(name)
        if nn in seen:
            findings.append(f"live gaps {seen[nn]} and {name} both use NN {nn}")
        seen[nn] = name
    for name in sorted(live_gaps):
        nn = _nn_of(name)
        for archived_name, archived_text in sorted(archived_gaps.items()):
            if _nn_of(archived_name) == nn and "**Status:** withdrawn" not in archived_text:
                findings.append(
                    f"live {name} and archived {archived_name} both use NN {nn}, "
                    "but the archived occupant is not a withdrawn tombstone"
                )
    return findings


# --- filesystem access (tests only) ---------------------------------------


def _nn_files(directory):
    """Sorted `NN-slug.md` names in a directory."""
    return sorted(p.name for p in directory.glob("*.md") if NN_FILE_RE.match(p.name))


def _stage6_docs():
    """(name, text) for every `docs/NN-slug.md` — the empirical layer."""
    return [(name, (DOCS / name).read_text(encoding="utf-8")) for name in _nn_files(DOCS)]


def _live_gap_files():
    """(name, text) for every live `docs/gaps/NN-*.md`."""
    return [(n, (GAPS / n).read_text(encoding="utf-8")) for n in _nn_files(GAPS)]


def _archived_gap_files():
    """(name, text) for every `docs/gaps/_archive/NN-*.md`, tombstones included."""
    return [
        (n, (GAPS_ARCHIVE / n).read_text(encoding="utf-8"))
        for n in _nn_files(GAPS_ARCHIVE)
    ]


# --- tests -----------------------------------------------------------------


def test_stage6_section_order():
    """AC-DOC-001: every `docs/NN-slug.md` carries exactly the eight template
    sections, in order, none missing, renamed or merged."""
    docs = _stage6_docs()
    assert docs, "no docs/NN-slug.md files found"
    for name, text in docs:
        assert parse_sections(text), (
            f"docs/{name}: parsed no level-2 headings — the heading parser or the "
            "fence strip is broken"
        )
        findings = check_section_order(text)
        assert findings == [], f"docs/{name}: {'; '.join(findings)}"


def test_fails_resolution_parity():
    """AC-DOC-002: in every `docs/NN-slug.md`, `## What Fails` and
    `## Resolution` carry the same number of top-level bullets."""
    docs = _stage6_docs()
    total_fails = 0
    for name, text in docs:
        fails_body = _section_body(text, "What Fails")
        assert fails_body is not None, f"docs/{name}: no ## What Fails section"
        total_fails += len(BULLET_RE.findall(fails_body))
        findings = check_fails_resolution_parity(text)
        assert findings == [], f"docs/{name}: {'; '.join(findings)}"
    assert total_fails > 0, "counted no failure bullets at all — the counter is broken"


def test_docs_readme_status_rows():
    """AC-DOC-003: every `docs/NN-slug.md` has exactly one row in
    `docs/README.md`'s Status Docs table, and every row resolves to a doc."""
    docs = _stage6_docs()
    assert docs, "no docs/NN-slug.md files found"
    readme_text = (DOCS / "README.md").read_text(encoding="utf-8")
    findings = check_catalog_rows(
        readme_text, [name for name, _ in docs], "docs/README.md"
    )
    assert findings == [], "; ".join(findings)


def test_gaps_readme_open_rows():
    """AC-DOC-004: every live `docs/gaps/NN-*.md` has a row in
    `docs/gaps/README.md`'s open-gaps table, and every row resolves to a live
    gap file. The live set may legitimately be empty — the archive still proves
    the scan reached real files."""
    live = _live_gap_files()
    archived = _archived_gap_files()
    assert archived, "no docs/gaps/_archive/NN-*.md found — the directory scan is wrong"
    readme_text = (GAPS / "README.md").read_text(encoding="utf-8")
    assert "## Open gaps" in readme_text, (
        "docs/gaps/README.md has no '## Open gaps' section — wrong file or wrong parse"
    )
    findings = check_catalog_rows(readme_text, [n for n, _ in live], "docs/gaps/README.md")
    assert findings == [], "; ".join(findings)


def test_prd_quick_reference_rows():
    """AC-DOC-005: every `docs/prd/NN-*.md` appears in `PRD.md`'s Quick
    Reference table, and every row there resolves to an existing file."""
    prd_files = _nn_files(DOCS / "prd")
    assert prd_files, "no docs/prd/NN-*.md files found"
    findings = check_catalog_rows(
        PRD_MD.read_text(encoding="utf-8"), prd_files, "PRD.md Quick Reference"
    )
    assert findings == [], "; ".join(findings)


def test_cross_layer_nn_consistency():
    """AC-DOC-006: every `NN` used under `docs/gaps/` — live or archived — has
    a topic file in `docs/` or `docs/prd/`; live `NN`s are unique; a live and
    an archived file may share a number only via a withdrawn tombstone."""
    live = dict(_live_gap_files())
    archived = dict(_archived_gap_files())
    assert archived, "no docs/gaps/_archive/NN-*.md found — the directory scan is wrong"
    doc_names = _nn_files(DOCS)
    prd_names = _nn_files(DOCS / "prd")
    assert doc_names and prd_names, (
        "the topic-file scan found no docs/NN-*.md or no docs/prd/NN-*.md — "
        "the NN check would pass on an empty topic set"
    )
    topic_nns = {_nn_of(n) for n in doc_names} | {_nn_of(n) for n in prd_names}
    findings = check_nn_consistency(live, archived, topic_nns)
    assert findings == [], "; ".join(findings)


def test_fenced_code_is_stripped_before_headings():
    """AC-DOC-007: a heading inside a ``` fence is not read as a section. The
    canary is the real `# tiers 1+2 (no container)` line in docs/05."""
    canary = "# tiers 1+2 (no container)"
    text = (DOCS / "05-mcp-rest-service.md").read_text(encoding="utf-8")
    assert canary in text, "the docs/05 fence canary moved — update this test"
    assert HEADING_RE.match(canary), "the canary is not heading-shaped; test is toothless"
    assert canary not in strip_fenced_blocks(text), "the fence strip left the canary in"
    parsed = parse_sections(text)
    assert "tiers 1+2 (no container)" not in parsed
    assert parsed == list(TEMPLATE_SECTIONS)

    # Both `#` and `##` are handled by the strip.
    synthetic = "## What\n\n## Why\n\n```\n# fake one\n## What\n```\n"
    assert parse_sections(synthetic) == ["What", "Why"]


def test_section_order_reports_a_missing_section():
    """AC-DOC-011: negative control — the section-order check reports a
    synthetic doc that is missing `## Verdict`."""
    findings = check_section_order("\n".join(f"## {s}" for s in TEMPLATE_SECTIONS[:-1]))
    assert findings, "section-order check passed a doc with no Verdict section"
    assert any("Verdict" in f for f in findings), findings
    good = "\n".join(f"## {s}" for s in TEMPLATE_SECTIONS)
    assert check_section_order(good) == []


def test_parity_reports_two_failures_one_resolution():
    """AC-DOC-012: negative control — the parity check reports a synthetic doc
    with two failures and one resolution."""
    bad = "## What Fails\n- a\n- b\n\n## Resolution\n- a\n"
    findings = check_fails_resolution_parity(bad)
    assert findings, "parity check passed two failures against one resolution"
    assert "2" in findings[0] and "1" in findings[0], findings
    good = "## What Fails\n- a\n- b\n\n## Resolution\n- a\n- b\n"
    assert check_fails_resolution_parity(good) == []


def test_catalog_reports_a_doc_with_no_row():
    """AC-DOC-013: negative control — the row checker reports a catalogued doc
    that has no row."""
    findings = check_catalog_rows(
        "| 02 | [X](02-x.md) |\n", ["02-x.md", "09-ghost.md"], "synthetic"
    )
    assert findings, "row checker passed a doc with no row"
    assert any("09-ghost.md" in f for f in findings), findings


def test_catalog_reports_a_row_with_no_doc():
    """AC-DOC-014: negative control — the row checker reports a row pointing at
    a file that does not exist."""
    findings = check_catalog_rows("| 09 | [Ghost](09-ghost.md) |\n", [], "synthetic")
    assert findings, "row checker passed a row with no file"
    assert any("09-ghost.md" in f for f in findings), findings


def test_nn_check_reports_a_gap_with_no_topic_file():
    """AC-DOC-015: negative control — the `NN` checker reports a gap whose
    number has no topic file under `docs/` or `docs/prd/`."""
    findings = check_nn_consistency({"09-ghost.md": "**Status:** open\n"}, {}, {"02", "03"})
    assert findings, "NN check passed a gap with no topic file"
    assert any("09" in f for f in findings), findings
    assert check_nn_consistency({}, {"03-x.md": "**Status:** withdrawn\n"}, {"03"}) == []


def test_row_parser_ignores_prose_and_fences():
    """AC-DOC-016: negative control — rows are real `|` table lines with a
    link; the prose bullet naming archived gap files is not a row, and neither
    is a table inside a fence."""
    text = (
        "## Open gaps\n\n"
        "| # | Gap |\n|---|---|\n"
        "| 09 | [Ghost](09-ghost.md) |\n\n"
        "- **Archived** — `02-foo.md`, [`03-bar.md`](_archive/03-bar.md)\n\n"
        "```\n| 08 | [Fenced](08-fenced.md) |\n```\n"
    )
    assert parse_table_rows(text) == [["09-ghost.md"]]
    findings = check_catalog_rows(text, [], "synthetic")
    assert any("09-ghost.md" in f for f in findings), findings
    assert not any("03-bar.md" in f for f in findings), findings
    assert not any("08-fenced.md" in f for f in findings), findings
