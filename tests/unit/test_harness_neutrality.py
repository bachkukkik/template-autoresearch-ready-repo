"""Harness-neutrality guard (unit tier). IDs: AC-HRN-001..007.

Locks in the repo's own claim that this template serves Hermes, Claude Code,
opencode and a DeepSeek/OpenAI-compatible harness as equals, with no
Hermes-only assumption baked into the doctrine. Reads `AGENTS.md`'s *Harness
Adapter* — its capability table and its *Per-harness rows* table — plus
`README.md`'s *Harness Support* table, and asserts what is ACTUALLY there.

Hermetic: two file reads and stdlib parsing. No subprocess, no network, no
harness binary. Tables are parsed by header text, never by column index, so a
rewrite that reorders a column still passes while removing a harness binding
fails.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"
README_MD = REPO_ROOT / "README.md"

FENCE_RE = re.compile(r"```.*?```", re.S)
SECTION_SPLIT_RE = re.compile(r"(?m)^##\s+")
TABLE_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_RE = re.compile(r":?-{2,}:?")

# The four harnesses this template must serve as equals. The patterns tolerate
# the spellings the documents actually use.
HARNESS_PATTERNS = {
    "Hermes": re.compile(r"\bhermes\b", re.I),
    "Claude Code": re.compile(r"claude\W{0,2}code", re.I),
    "opencode": re.compile(r"\bopencode\b", re.I),
    "DeepSeek / OpenAI-compatible": re.compile(r"deepseek[^\n|]*openai-compatible", re.I),
}
CANONICAL_HARNESSES = tuple(HARNESS_PATTERNS)

# The binding for a harness nobody columned: a generic/fallback column or row.
GENERIC_RE = re.compile(r"generic\s+fallback|anything\s+else", re.I)

# A harness name the two catalog tables may legitimately carry beyond the
# canonical four — used by AC-HRN-004 to catch a row the adapter does not know.
KNOWN_HARNESS_LABEL_RE = re.compile(
    r"hermes|claude\W{0,2}code|\bopencode\b|copilot|deepseek[^\n|]*openai-compatible"
    r"|anything\s+else|generic\s+fallback",
    re.I,
)

# Capability rows in the adapter's capability table.
ENTRY_FILE_ROW_RE = re.compile(r"entry\s+instruction\s+file", re.I)
REPO_SKILLS_ROW_RE = re.compile(r"repo-scoped\s+skills", re.I)
HOST_SKILLS_ROW_RE = re.compile(r"host-level\s+skills", re.I)
PIPELINE_ROW_RE = re.compile(r"pipeline\s+invocation", re.I)

# What an entry-instruction-file binding may name.
ENTRY_FILE_RE = re.compile(r"AGENTS\.md|CLAUDE\.md|copilot-instructions\.md")
# The fallback for a harness with no skill mechanism.
INLINE_SKILL_RE = re.compile(r"inline[^\n|]*SKILL\.md", re.I)
# A harness with no slash command prompts the documented phases instead.
PROMPT_PHASES_RE = re.compile(r"prompt the phase", re.I)

# Each harness's host-level skills home, where the adapter names one.
HOST_SKILL_HOMES = {
    "Hermes": "~/.hermes/skills",
    "Claude Code": "~/.claude/skills",
    "opencode": "~/.config/opencode/skills",
}
# Harnesses with no host-level skill home bind the inline fallback instead.
HARNESSES_WITHOUT_HOST_SKILLS = ("DeepSeek / OpenAI-compatible",)


# --- parsing ---------------------------------------------------------------


def strip_fenced_blocks(text):
    """Remove fenced code blocks so a `|` table inside a fence is invisible."""
    return FENCE_RE.sub("", text)


def section(text, title):
    """Body of the `## <title>` section, up to the next level-2 heading."""
    for part in SECTION_SPLIT_RE.split(strip_fenced_blocks(text))[1:]:
        head, _, body = part.partition("\n")
        if head.strip() == title:
            return body
    return None


def parse_tables(text):
    """Every markdown table outside a fence, as {headers, rows} dicts.

    Each row is keyed by its HEADER text (plus `__label__` for its first
    cell), so a caller resolves a cell by what the column means and never by
    where it sits. A `\\|` inside a cell does not split the row.
    """
    tables = []
    current = None
    for line in strip_fenced_blocks(text).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            current = None
            continue
        cells = [c.strip() for c in TABLE_SPLIT_RE.split(stripped[1:-1])]
        if cells and all(SEPARATOR_RE.fullmatch(c) for c in cells):
            continue  # the |---|---| separator row
        if current is None:
            current = {"headers": cells, "rows": []}
            tables.append(current)
            continue
        row = {"__label__": cells[0]}
        for header, cell in zip(current["headers"], cells):
            row[header] = cell
        current["rows"].append(row)
    return tables


def _search(pattern, text):
    """`re.search` that accepts a compiled pattern or a pattern string."""
    if hasattr(pattern, "search"):
        return pattern.search(text)
    return re.compile(pattern, re.I).search(text)


def bindings(tables, harness_pattern, capability_pattern):
    """Every cell the given tables bind to one harness for one capability.

    Tolerates both orientations the adapter uses: harness-per-COLUMN (the
    capability table) and harness-per-ROW (the *Per-harness rows* table).
    Column order is irrelevant — lookups go by header text.
    """
    found = []
    for table in tables:
        headers = table["headers"]
        # Orientation A — the harness names a COLUMN.
        harness_columns = [h for h in headers if _search(harness_pattern, h)]
        for column in harness_columns:
            for row in table["rows"]:
                if _search(capability_pattern, row["__label__"]):
                    found.append(row.get(column, ""))
        # Orientation B — the harness names a ROW.
        for row in table["rows"]:
            if not _search(harness_pattern, row["__label__"]):
                continue
            for column in headers:
                if _search(capability_pattern, column):
                    found.append(row.get(column, ""))
    return [cell for cell in found if cell]


def missing_harnesses(text, required=CANONICAL_HARNESSES):
    """The canonical harnesses a piece of text never names. Empty == all named."""
    return [name for name in required if not HARNESS_PATTERNS[name].search(text)]


def _adapter():
    text = AGENTS_MD.read_text(encoding="utf-8")
    adapter = section(text, "Harness Adapter")
    assert adapter, "AGENTS.md has no '## Harness Adapter' section"
    return text, adapter


# --- tests -----------------------------------------------------------------


def test_harness_adapter_names_all_four_harnesses():
    """AC-HRN-001: `AGENTS.md`'s Harness Adapter names all four harnesses the
    template must serve — Hermes, Claude Code, opencode and
    DeepSeek/OpenAI-compatible — plus a generic/fallback column or row."""
    _, adapter = _adapter()
    missing = missing_harnesses(adapter)
    assert missing == [], (
        f"the Harness Adapter never names: {missing} — every harness this "
        "template serves must have a binding there"
    )
    assert GENERIC_RE.search(adapter), (
        "the Harness Adapter has no generic/fallback column or row, so a harness "
        "nobody columned has no binding at all"
    )


def test_harness_adapter_binds_entry_file_and_host_skills():
    """AC-HRN-002: the adapter binds, for each of the four harnesses, the entry
    instruction file and the host-level skills capability; a harness with no
    skill mechanism is bound to the inline-`SKILL.md` fallback."""
    _, adapter = _adapter()
    tables = parse_tables(adapter)
    assert len(tables) >= 2, (
        f"parsed {len(tables)} table(s) out of the Harness Adapter — the "
        "capability table and the *Per-harness rows* table are both expected"
    )

    for name, pattern in HARNESS_PATTERNS.items():
        entries = bindings(tables, pattern, ENTRY_FILE_ROW_RE)
        assert entries, f"no entry-instruction-file binding for {name}"
        assert any(ENTRY_FILE_RE.search(cell) for cell in entries), (
            f"{name}'s entry-instruction-file binding names no known entry file: {entries}"
        )
        host = bindings(tables, pattern, HOST_SKILLS_ROW_RE)
        assert host, f"no host-level-skills binding for {name}"

    # The three harnesses with a host-level skills home name it.
    for name, home in HOST_SKILL_HOMES.items():
        host = bindings(tables, HARNESS_PATTERNS[name], HOST_SKILLS_ROW_RE)
        assert any(home in cell for cell in host), (
            f"{name}'s host-level-skills binding does not name {home}: {host}"
        )

    # The harness with no skill mechanism falls back to an inlined SKILL.md.
    inline = []
    for pattern in (GENERIC_RE.pattern, *(HARNESS_PATTERNS[n].pattern for n in HARNESSES_WITHOUT_HOST_SKILLS)):
        inline += bindings(tables, pattern, REPO_SKILLS_ROW_RE)
    assert any(INLINE_SKILL_RE.search(cell) for cell in inline), (
        "the adapter never states the inline-`SKILL.md` fallback for a harness "
        f"with no skill mechanism: {inline}"
    )


def test_no_harness_is_required_to_have_a_slash_command():
    """AC-HRN-003: the doctrine states the canonical cross-harness contract is
    the `sub1`-`sub4` phase blocks + the phase table, and that `/goal` is
    Hermes-only — no harness is required to have a slash command."""
    text, adapter = _adapter()
    paragraphs = [
        part
        for part in re.split(r"\n\s*\n", strip_fenced_blocks(text))
        if "canonical cross-harness contract" in part
    ]
    assert paragraphs, "AGENTS.md never states the canonical cross-harness contract"
    assert any("sub1" in part and "phase table" in part for part in paragraphs), (
        "the cross-harness contract sentence does not name the `sub1`-`sub4` "
        f"phase blocks and the phase table: {paragraphs}"
    )

    tables = parse_tables(adapter)
    hermes = bindings(tables, HARNESS_PATTERNS["Hermes"], PIPELINE_ROW_RE)
    assert any("/goal" in cell for cell in hermes), hermes
    assert any("hermes-only" in cell.lower() for cell in hermes), (
        f"the Harness Adapter does not mark /goal Hermes-only: {hermes}"
    )

    for name in ("Claude Code", "opencode", "DeepSeek / OpenAI-compatible"):
        cells = bindings(tables, HARNESS_PATTERNS[name], PIPELINE_ROW_RE)
        assert cells, f"no pipeline-invocation binding for {name}"
        for cell in cells:
            assert "/goal" not in cell, f"{name} is bound to the Hermes-only /goal: {cell}"
            assert PROMPT_PHASES_RE.search(cell), (
                f"{name}'s pipeline invocation neither has a slash command nor "
                f"prompts the documented phases: {cell}"
            )


def test_readme_harness_support_names_the_same_four():
    """AC-HRN-004: `README.md`'s *Harness Support* table names the same four
    harnesses the adapter does, so the two documents cannot drift apart."""
    readme = strip_fenced_blocks(README_MD.read_text(encoding="utf-8"))
    harness_tables = [
        table
        for table in parse_tables(readme)
        if any(re.fullmatch(r"harness", header, re.I) for header in table["headers"])
    ]
    assert len(harness_tables) == 1, (
        f"expected exactly one table with a `Harness` column in README.md, "
        f"found {len(harness_tables)}"
    )
    rows = harness_tables[0]["rows"]
    assert rows, "README.md's Harness Support table has no rows"
    labels = "\n".join(row["__label__"] for row in rows)

    missing = missing_harnesses(labels)
    assert missing == [], (
        f"README.md's Harness Support table never names: {missing} — the doc pair "
        "must name the same harnesses as the Harness Adapter"
    )
    assert GENERIC_RE.search(labels), (
        "README.md's Harness Support table has no generic/fallback row"
    )
    unknown = [
        row["__label__"]
        for row in rows
        if not KNOWN_HARNESS_LABEL_RE.search(row["__label__"])
    ]
    assert unknown == [], (
        f"README.md names harness row(s) the Harness Adapter does not know: "
        f"{unknown} — add each to AGENTS.md too, or the pair has drifted"
    )


def test_name_scan_reports_a_removed_harness():
    """AC-HRN-005: negative control — the harness-name scan reports a harness a
    document stopped naming: a synthetic copy with opencode removed must be
    reported, and dropping the whole *Per-harness rows* table must be too."""
    _, adapter = _adapter()
    assert missing_harnesses(adapter) == [], "the real adapter already fails AC-HRN-001"

    without = re.sub(r"opencode", "vendor-x", adapter, flags=re.I)
    assert missing_harnesses(without) == ["opencode"], (
        "the name scan passed a synthetic adapter with opencode removed"
    )

    table_start = adapter.find("| Harness |")
    assert table_start > 0, "the *Per-harness rows* table header moved — update this test"
    without_table = adapter[:table_start]
    reported = missing_harnesses(without_table)
    assert "opencode" in reported and "DeepSeek / OpenAI-compatible" in reported, (
        f"the name scan passed an adapter with the per-harness table removed: {reported}"
    )


def test_binding_lookup_reports_a_removed_host_skill_binding():
    """AC-HRN-006: negative control — the capability lookup reports a harness
    whose host-level skills binding a document dropped."""
    _, adapter = _adapter()
    tables = parse_tables(adapter)
    good = bindings(tables, HARNESS_PATTERNS["opencode"], HOST_SKILLS_ROW_RE)
    assert any("~/.config/opencode/skills" in cell for cell in good), good

    stripped = adapter.replace("~/.config/opencode/skills/", "somewhere-else")
    after = bindings(parse_tables(stripped), HARNESS_PATTERNS["opencode"], HOST_SKILLS_ROW_RE)
    assert after and not any("~/.config/opencode/skills" in cell for cell in after), (
        f"the binding lookup passed a document with the host-skills home removed: {after}"
    )


def test_table_parser_is_tolerant_but_not_blind():
    """AC-HRN-007: negative control — the table parser resolves cells by header
    name (column order irrelevant) and yields no binding when the harness
    column is gone, so every lookup above can actually fail."""
    reordered = (
        "| Capability | Generic fallback | Hermes |\n"
        "|---|---|---|\n"
        "| Pipeline invocation | do it inline | `/goal` (Hermes-only) |\n"
    )
    tables = parse_tables(reordered)
    assert any("/goal" in cell for cell in bindings(tables, HARNESS_PATTERNS["Hermes"], PIPELINE_ROW_RE))
    assert any(
        "inline" in cell for cell in bindings(tables, GENERIC_RE.pattern, PIPELINE_ROW_RE)
    )

    no_harness_column = (
        "| Capability | Note |\n|---|---|\n| Pipeline invocation | prompt the phases in order |\n"
    )
    assert bindings(parse_tables(no_harness_column), HARNESS_PATTERNS["Hermes"], PIPELINE_ROW_RE) == [], (
        "the binding lookup invented a binding with no harness column or row present"
    )
