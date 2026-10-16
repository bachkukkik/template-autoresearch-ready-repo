"""Harness-neutrality guard (unit tier). IDs: AC-HRN-001..017.

Locks in the repo's own claim that this template serves Hermes, Claude Code,
opencode and a DeepSeek/OpenAI-compatible harness as equals, with no
Hermes-only assumption baked into the doctrine. Reads `AGENTS.md`'s *Harness
Adapter* — its capability table and its *Per-harness rows* table — plus
`README.md`'s *Harness Support* table, and asserts what is ACTUALLY there.

AC-HRN-001..007 assert the two catalog TABLES. AC-HRN-008..014 assert the
document's behavioural completeness instead: `AGENTS.md` is the one file every
harness reads, so it must never present a Hermes-only mechanism as the only
way to proceed. Each Hermes-only mechanism is paired with the non-Hermes
fallback its own context has to document, and a second invariant holds that a
harness missing a mechanism still has a documented path to every mandated
skill. That is the invariant the original defect — `/goal` offered as the
pipeline entry point with no fallback for the three harnesses lacking slash
commands — would have failed.

AC-HRN-015..017 close three seams. A mandated skill could be named in
`AGENTS.md` §1 and resolve nowhere (AC-HRN-015 — it must resolve to a vendored
`.agents/skills/<name>/SKILL.md` or to a README install-source row carrying an
https URL). The harness set was an exact four, so adding a README row for a
harness `AGENTS.md` did not list tripped a regex instead of reporting drift
(AC-HRN-016 — the four are a MINIMUM, and a README row must pair with an
`AGENTS.md` binding). And the Gemini CLI entry point had to be a symlink to the
one canonical file (AC-HRN-017).

What this guard still cannot reach: it reads the document, not a live client.
A harness whose *behaviour* diverges from the documented binding (an opencode
that ignores `.agents/skills`, a Claude Code whose `Task` tool no longer
exists) is outside a hermetic unit test; this file only proves the document
tells every such harness what to do instead.

Hermetic: file reads and stdlib parsing. No subprocess, no network, no
harness binary. Tables are parsed by header text, never by column index, so a
rewrite that reorders a column still passes while removing a harness binding
fails.
"""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"
README_MD = REPO_ROOT / "README.md"

FENCE_RE = re.compile(r"```.*?```", re.S)
SECTION_SPLIT_RE = re.compile(r"(?m)^##\s+")
TABLE_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_RE = re.compile(r":?-{2,}:?")

# The four harnesses this template must serve at MINIMUM — a FLOOR, not the whole
# set. Codex CLI, Cursor, Gemini CLI and Aider are bound too, and the canonical
# four stay canonical: AC-HRN-004 asserts they are named, AC-HRN-016 asserts a
# harness beyond them is accepted when both documents carry it and reported when
# only the README does. Adding a harness therefore edits two documents, never a
# regex here. The patterns tolerate the spellings the documents actually use.
HARNESS_PATTERNS = {
    "Hermes": re.compile(r"\bhermes\b", re.I),
    "Claude Code": re.compile(r"claude\W{0,2}code", re.I),
    "opencode": re.compile(r"\bopencode\b", re.I),
    "DeepSeek / OpenAI-compatible": re.compile(r"deepseek[^\n|]*openai-compatible", re.I),
}
CANONICAL_HARNESSES = tuple(HARNESS_PATTERNS)

# The binding for a harness nobody columned: a generic/fallback column or row.
GENERIC_RE = re.compile(r"generic\s+fallback|anything\s+else", re.I)

# A README harness label pairs with a name in AGENTS.md — the two documents are
# one binding, not two lists. Link syntax and parentheticals are stripped, and a
# label carrying alternatives ("DeepSeek / OpenAI-compatible") pairs on its first
# alternative.
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
PARENTHETICAL_RE = re.compile(r"\([^)]*\)")

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


def harness_key(label):
    """The name a README harness label must be paired with in AGENTS.md.

    Link syntax and parentheticals are dropped and a label with alternatives
    pairs on its first alternative, so `[Gemini CLI](url)`,
    `Codex CLI` and `DeepSeek / OpenAI-compatible` reduce to `Gemini CLI`,
    `Codex CLI` and `DeepSeek`.
    """
    text = MARKDOWN_LINK_RE.sub(r"\1", label)
    text = text.split("/", 1)[0]
    text = PARENTHETICAL_RE.sub(" ", text).replace("`", " ")
    return re.sub(r"\s+", " ", text).strip()


def readme_harness_labels(readme_text):
    """The row labels of README.md's *Harness Support* table.

    Located by the `Harness` column header, never by position, and read off the
    fence-stripped text so a table inside a ``` fence is invisible.
    """
    readme = strip_fenced_blocks(readme_text)
    tables = [
        table
        for table in parse_tables(readme)
        if any(re.fullmatch(r"harness", header, re.I) for header in table["headers"])
    ]
    assert len(tables) == 1, (
        f"expected exactly one table with a `Harness` column in README.md, "
        f"found {len(tables)}"
    )
    return [row["__label__"] for row in tables[0]["rows"]]


def unpaired_harnesses(agents_text, labels):
    """README harness labels that AGENTS.md does not also name. Empty == paired.

    The pairing is the drift guard: a harness may be ADDED — the canonical four
    are a floor, not a closed set — but it must be added to both documents. A
    generic/fallback row is not a harness name and is skipped.
    """
    findings = []
    for label in labels:
        if not label.strip() or GENERIC_RE.search(label):
            continue
        key = harness_key(label)
        if not key:
            continue
        if not re.search(r"\b" + re.escape(key) + r"\b", agents_text, re.I):
            findings.append(
                f"{label!r} carries a row in README.md's Harness Support table but "
                "AGENTS.md never names it — add the harness to AGENTS.md too (a "
                "README-only row is drift), or drop the row"
            )
    return findings


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
    """AC-HRN-004: every harness in `README.md`'s *Harness Support* table is
    also named in `AGENTS.md`'s adapter — the canonical four are a floor, not
    a closed set, but a README-only row means the pair has drifted."""
    readme = strip_fenced_blocks(README_MD.read_text(encoding="utf-8"))
    labels = readme_harness_labels(readme)
    assert labels, "README.md's Harness Support table has no rows"
    joined = "\n".join(labels)

    missing = missing_harnesses(joined)
    assert missing == [], (
        f"README.md's Harness Support table never names: {missing} — the doc pair "
        "must name the same harnesses as the Harness Adapter"
    )
    assert GENERIC_RE.search(joined), (
        "README.md's Harness Support table has no generic/fallback row"
    )
    agents_text = _agents_text()
    unknown = unpaired_harnesses(agents_text, labels)
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


# --- fallback completeness: behavioural document, not catalog tables --------
#
# AC-HRN-008..014 stop asserting the catalog TABLES and assert the document
# every harness actually reads. The invariant: a Hermes-only mechanism must
# never be presented as the only way to proceed — wherever `AGENTS.md` names
# one, the same context must also document the non-Hermes fallback.
#
# The pairs below are DERIVED from AGENTS.md (grep the literal mechanism, then
# the literal fallback the file states beside it), not assumed. An entry whose
# mechanism no longer occurs anywhere is itself reported (AC-HRN-009), so a
# pair this document stops supporting is dropped deliberately rather than
# passing vacuously.
HERMES_ONLY_MECHANISMS = (
    {
        "id": "goal-slash-command",
        "mechanism": re.compile(r"/goal"),
        "fallback": re.compile(r"sub[1-4]\b|phase table|prompt the phase", re.I),
        "fallback_label": "the `sub1`-`sub4` phase blocks / the phase table",
    },
    {
        "id": "hermes-plans-scratch-space",
        "mechanism": re.compile(r"~/\.hermes/plans"),
        "fallback": re.compile(r"scratchpads/"),
        "fallback_label": "`scratchpads/` (gitignored)",
    },
    {
        "id": "hermes-delegation",
        "mechanism": re.compile(r"delegate_task|\bkanban\b"),
        "fallback": re.compile(r"do the work inline|run the documented phase order inline"),
        "fallback_label": "do the work inline, in the documented phase order",
    },
    {
        "id": "hermes-codegraph-wiring",
        "mechanism": re.compile(r"\$HERMES_HOME|mcp-codegraph"),
        "fallback": re.compile(r"codegraph serve --mcp|CLI twins|no MCP", re.I),
        "fallback_label": "any MCP client (`codegraph serve --mcp`) or the CLI twins",
    },
    {
        # The Hermes-only part is the native SLASH form. The `llm-wiki` skill
        # itself is harness-neutral, so a bare mention of it is not a mechanism.
        "id": "llm-wiki-native-invocation",
        "mechanism": re.compile(r"`/llm-wiki"),
        "fallback": re.compile(r"inline[^\n]*SKILL\.md"),
        "fallback_label": "inline the skill's `SKILL.md`",
    },
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def blank_fenced_blocks(text):
    """Replace every fenced block with blank lines of the same shape.

    `strip_fenced_blocks` removes the fence and everything in it, which shifts
    every following line number. A finding that names the line it came from
    needs the numbering intact, so this variant blanks the content and keeps
    the newlines.
    """
    return FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _is_table_row(line):
    """True when `line` is a markdown table row (not the |---|---| separator)."""
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    cells = [c.strip() for c in TABLE_SPLIT_RE.split(stripped[1:-1])]
    return not (cells and all(SEPARATOR_RE.fullmatch(c) for c in cells))


def _section_spans(lines):
    """(start, end, title) for every `## ` section of an already-blanked text."""
    heads = [
        (i, line[3:].strip())
        for i, line in enumerate(lines)
        if re.match(r"^##\s+", line)
    ]
    return [
        (i, heads[n + 1][0] if n + 1 < len(heads) else len(lines), title)
        for n, (i, title) in enumerate(heads)
    ]


def heading_region(text, title, level=2):
    """Body of the heading whose text is `title` at `level`, up to the next
    heading of the same or a higher level. Handles any level, so a `### `
    subsection is addressable where `section()` (level 2 only) is not."""
    lines = blank_fenced_blocks(text).splitlines()
    heads = [
        (i, len(m.group(1)), m.group(2).strip())
        for i, line in enumerate(lines)
        if (m := HEADING_RE.match(line))
    ]
    for i, head_level, head_text in heads:
        if head_level != level or head_text != title:
            continue
        end = next(
            (j for j, other_level, _ in heads if j > i and other_level <= level),
            len(lines),
        )
        return "\n".join(lines[i:end])
    return None


def mechanism_occurrences(text, mechanism):
    """Every occurrence of `mechanism` outside a fenced block, one per line.

    Each occurrence is a dict with the line number, the line, `row` (the line
    itself when it is a markdown table row, else None), `section` (the body of
    the enclosing `## ` section) and `section_title`. A command inside a fence
    is not an occurrence: a fenced block is an invocation, not a statement
    that the capability is reachable without Hermes.
    """
    lines = blank_fenced_blocks(text).splitlines()
    spans = _section_spans(lines)
    found = []
    for n, line in enumerate(lines):
        if not mechanism.search(line):
            continue
        span = next(((s, e, t) for s, e, t in spans if s <= n < e), None)
        if span is None:  # before the first `## ` heading
            first = spans[0][0] if spans else len(lines)
            body, title = "\n".join(lines[:first]), "(preamble)"
        else:
            body, title = "\n".join(lines[span[0]:span[1]]), span[2]
        found.append(
            {
                "line": n + 1,
                "text": line,
                "row": line if _is_table_row(line) else None,
                "section": body,
                "section_title": title,
            }
        )
    return found


def _searched_contexts(occurrence):
    """The contexts an occurrence's fallback may live in, most precise first."""
    contexts = []
    if occurrence["row"]:
        contexts.append(("its table row", occurrence["row"]))
    contexts.append((f"section '{occurrence['section_title']}'", occurrence["section"]))
    return contexts


def check_fallback_completeness(text, mechanisms=HERMES_ONLY_MECHANISMS):
    """Findings for one instruction document. Empty list == conformant.

    Two invariants: (1) every mechanism the table names occurs at least once
    outside a fence, so no pair is asserted against text that is not there;
    (2) every occurrence sits in a context that also documents the non-Hermes
    fallback — its own table row, or the enclosing `## ` section. Contexts are
    read off the fence-blanked text, so a fallback that exists only inside a
    ``` fence does not count.
    """
    findings = []
    for spec in mechanisms:
        occurrences = mechanism_occurrences(text, spec["mechanism"])
        if not occurrences:
            findings.append(
                f"{spec['id']}: the mechanism {spec['mechanism'].pattern!r} no "
                "longer occurs outside a fence in this document — drop the pair "
                "(or restore the text); asserting it asserts nothing"
            )
            continue
        for occurrence in occurrences:
            contexts = _searched_contexts(occurrence)
            if any(spec["fallback"].search(body) for _, body in contexts if body):
                continue
            searched = " or ".join(label for label, _ in contexts)
            findings.append(
                f"{spec['id']} at line {occurrence['line']}: "
                f"{occurrence['text'].strip()[:70]!r} — {searched} documents no "
                f"non-Hermes fallback ({spec['fallback_label']})"
            )
    return findings


# A statement that skill gates bind every harness; the waiver; and the escape
# a harness with no skill mechanism uses. All three must meet in one prose
# block for the gate to have a documented path.
GATE_STATEMENT_RE = re.compile(
    r"skill\s+gates?\s+are\s+absolute|skill\s+resolution\s+is\s+a\s+capability"
    r"|mandated\s+skill",
    re.I,
)
GATE_WAIVER_RE = re.compile(r"never\s+waives?\s+the\s+(?:rule|gate)", re.I)
SKILL_ESCAPE_RE = re.compile(r"SKILL\.md")


def prose_blocks(text):
    """The blank-line-separated blocks of a document, fences blanked."""
    return [
        block.strip()
        for block in re.split(r"\n\s*\n", blank_fenced_blocks(text))
        if block.strip()
    ]


def escaping_blocks(text):
    """Prose blocks that tie a skill-gate statement to the inline-`SKILL.md`
    escape: the gate, the waiver, and the escape in one place."""
    return [
        block
        for block in prose_blocks(text)
        if GATE_STATEMENT_RE.search(block)
        and GATE_WAIVER_RE.search(block)
        and SKILL_ESCAPE_RE.search(block)
    ]


def check_skill_gate_escape(text):
    """Findings for one instruction document. Empty list == conformant.

    The document must state, outside any fence, that a harness missing a
    mechanism never waives a skill gate, AND name the escape — the skill's
    `SKILL.md` pasted or inlined into the prompt. That escape is the only
    documented path to a mandated skill for a harness with neither a
    host-level skills directory nor a slash command (funnel rule 8, §1).
    """
    findings = []
    escaping = escaping_blocks(text)
    if escaping:
        return findings

    waivers = [b for b in prose_blocks(text) if GATE_WAIVER_RE.search(b)]
    if not waivers:
        findings.append(
            "no prose block states that a missing harness mechanism never "
            "waives the rule or the gate — a harness that lacks a tool has no "
            "documented obligation left"
        )
        return findings
    for block in waivers:
        if not SKILL_ESCAPE_RE.search(block):
            findings.append(
                f"the waiver {block[:70]!r} names no escape — a harness with no "
                "host-level skills directory and no slash command has no "
                "documented path to a mandated skill; name the skill's "
                "`SKILL.md` inlined into the prompt"
            )
        elif not GATE_STATEMENT_RE.search(block):
            findings.append(
                f"the waiver {block[:70]!r} names no skill gate — it does not say "
                "which skill gates stay absolute without a harness mechanism"
            )
    return findings


def _agents_text():
    return AGENTS_MD.read_text(encoding="utf-8")


def mechanism_by_id(mechanism_id):
    """The `HERMES_ONLY_MECHANISMS` entry with this id.

    A negative control runs the check against a synthetic document that carries
    one mechanism only, so it scopes the check to that mechanism — otherwise
    invariant (1) would report every pair the synthetic text legitimately lacks.
    """
    for spec in HERMES_ONLY_MECHANISMS:
        if spec["id"] == mechanism_id:
            return spec
    raise AssertionError(f"no mechanism {mechanism_id!r} in HERMES_ONLY_MECHANISMS")


GOAL_ONLY = (mechanism_by_id("goal-slash-command"),)


# --- tests: fallback completeness ------------------------------------------


def test_no_hermes_mechanism_is_presented_without_a_fallback():
    """AC-HRN-008: every Hermes-only mechanism `AGENTS.md` names sits in a
    context that also documents its non-Hermes fallback — its own table row, or
    its enclosing `## ` section. Non-vacuous: each mechanism in the table has
    at least one occurrence outside a fence, and every occurrence is examined.
    """
    text = _agents_text()
    counts = {
        spec["id"]: len(mechanism_occurrences(text, spec["mechanism"]))
        for spec in HERMES_ONLY_MECHANISMS
    }
    assert counts, "HERMES_ONLY_MECHANISMS is empty — the guard asserts nothing"
    unoccurring = sorted(name for name, n in counts.items() if n == 0)
    assert unoccurring == [], (
        f"{unoccurring} match no line in AGENTS.md — the guard would pass "
        f"vacuously; occurrences examined per mechanism: {counts}"
    )

    findings = check_fallback_completeness(text)
    assert findings == [], (
        f"{len(findings)} of {sum(counts.values())} occurrence(s) lack a "
        f"documented fallback: {'; '.join(findings)}"
    )


def test_mechanism_table_is_derived_from_this_document():
    """AC-HRN-009: the mechanism table is derived, not asserted — a mechanism
    the document does not carry is REPORTED, so an unsupported pair is dropped
    deliberately instead of passing vacuously."""
    text = _agents_text()
    assert [spec["id"] for spec in HERMES_ONLY_MECHANISMS], (
        "the mechanism table is empty"
    )

    invented = (
        {
            "id": "not-in-this-document",
            "mechanism": re.compile(r"~/\.hermes/teleport"),
            "fallback": re.compile(r"scratchpads/"),
            "fallback_label": "`scratchpads/`",
        },
    )
    findings = check_fallback_completeness(text, invented)
    assert findings, "the check passed a mechanism the document does not carry"
    assert any("not-in-this-document" in finding for finding in findings), findings

    # The same call with the real table is the conformant case (AC-HRN-008).
    assert check_fallback_completeness(text) == []


def test_missing_mechanism_never_waives_a_skill_gate():
    """AC-HRN-010: `AGENTS.md` states, outside any fence, that a missing
    harness mechanism never waives a skill gate, and names the escape — the
    skill's `SKILL.md` pasted/inlined into the prompt. One such statement sits
    with the mandated-skills table (§1), so a harness with neither a host-level
    skills directory nor a slash command still has a documented path to every
    mandated skill."""
    text = _agents_text()
    findings = check_skill_gate_escape(text)
    assert findings == [], "; ".join(findings)

    escaping = escaping_blocks(text)
    assert escaping, (
        "no prose block ties a skill gate to the inline-`SKILL.md` escape"
    )

    region = heading_region(text, "1. Mandated Skills", level=3)
    assert region, "AGENTS.md has no '### 1. Mandated Skills' heading"
    assert escaping_blocks(region), (
        "the mandated-skills subsection never states the inline-`SKILL.md` "
        "escape, so a harness with no host-level skills dir has no documented "
        "path to a mandated skill there"
    )


def test_fallback_check_reports_a_deleted_fallback():
    """AC-HRN-011: negative control — a `/goal` mechanism whose fallback was
    deleted is reported, both in synthetic text and in the real `AGENTS.md`
    with its fallback markers blanked out."""
    real = _agents_text()
    assert check_fallback_completeness(real) == [], (
        "the real AGENTS.md already fails AC-HRN-008"
    )

    synthetic = (
        "## The `/goal` Orchestration Workflow\n\n"
        "Every substantive request is driven through the `/goal` pipeline.\n"
    )
    findings = check_fallback_completeness(synthetic, GOAL_ONLY)
    assert findings, "the fallback check passed `/goal` with no fallback anywhere"
    assert any("goal-slash-command" in f and "line 1" in f for f in findings), findings

    blanked = re.sub(
        r"sub[1-4]|phase table|prompt the phase[s]?", "REMOVED", real, flags=re.I
    )
    after = check_fallback_completeness(blanked)
    assert after, "the fallback check passed AGENTS.md with its `/goal` fallback blanked"
    reported_lines = sorted(
        int(m.group(1))
        for f in after
        if (m := re.search(r"at line (\d+)", f)) and "goal-slash-command" in f
    )
    # Recomputed for the 20k context-file trim (2026-09-21): the `/goal` cluster
    # moved up when the doctrine was compressed, so the six occurrences now sit
    # at these lines. The assertion is unchanged in intent — it still pins EVERY
    # `/goal` occurrence, so a dropped or added one fails here.
    # Recomputed again for the Lifecycle restructure (2026-10-16): the upstream
    # Lifecycle section replaced the `/goal`-only cluster, so the occurrence set
    # is now five lines (adapter row, D1 row, kickoff line, the no-/goal heading
    # and its paragraph). Same intent — every occurrence is pinned.
    assert reported_lines == [108, 148, 153, 198, 200], (
        f"the blanked copy should report every `/goal` occurrence, got {reported_lines}"
    )


def test_fallback_check_ignores_a_fenced_fallback():
    """AC-HRN-012: negative control — a fallback that exists only inside a
    ``` fence does not satisfy the check. A fenced block is a command to run,
    not a statement that the capability is reachable without Hermes."""
    text = (
        "## The `/goal` Orchestration Workflow\n\n"
        "Every substantive request is driven through the `/goal` pipeline.\n\n"
        "```\n"
        "sub1 sub2 sub3 sub4 — the phase table\n"
        "```\n"
    )
    findings = check_fallback_completeness(text, GOAL_ONLY)
    assert findings, "a fallback inside a fence satisfied the check"
    assert any("goal-slash-command" in f for f in findings), findings

    # The same text with the fallback in prose passes, so the fence — not the
    # absence of any fallback — is what failed above.
    good = text.replace(
        "```\nsub1 sub2 sub3 sub4 — the phase table\n```\n",
        "Prompt the phase blocks in order: `sub1`-`sub4`.\n",
    )
    assert check_fallback_completeness(good, GOAL_ONLY) == [], check_fallback_completeness(
        good, GOAL_ONLY
    )


def test_skill_gate_check_reports_a_waiver_with_no_escape():
    """AC-HRN-013: negative control — a document that states a missing tool
    never waives the gate but never names the `SKILL.md` escape is reported,
    as is one that carries no waiver at all."""
    findings = check_skill_gate_escape(
        "Skill gates are absolute. A missing tool never waives the gate.\n"
    )
    assert findings, "the skill-gate check passed a waiver with no `SKILL.md` escape"
    assert any("SKILL.md" in f for f in findings), findings

    none = check_skill_gate_escape("Skill gates are absolute. Do the work.\n")
    assert none, "the skill-gate check passed a document with no waiver statement"
    assert any("never waives" in f for f in none), none

    # The fence does not rescue a waiver either: the escape must be in prose.
    fenced = check_skill_gate_escape(
        "Skill gates are absolute. A missing tool never waives the gate.\n\n"
        "```\n"
        "paste the skill's SKILL.md into the prompt\n"
        "```\n"
    )
    assert fenced, "a fenced `SKILL.md` escape satisfied the skill-gate check"

    good = (
        "**Skill resolution is a capability, not a directory.** A mandated skill "
        "resolves from wherever the harness provides it, or, last resort, the "
        "skill's `SKILL.md` inlined into the prompt. A missing tool never waives "
        "the gate.\n"
    )
    assert check_skill_gate_escape(good) == [], check_skill_gate_escape(good)


def test_fallback_check_scopes_to_the_occurrence_context():
    """AC-HRN-014: negative control — a fallback in a DIFFERENT section does
    not cover an occurrence. The context is the occurrence's own table row or
    its enclosing `## ` section, so a fallback cannot be parked out of reach."""
    text = (
        "## The `/goal` Orchestration Workflow\n\n"
        "Every substantive request is driven through the `/goal` pipeline.\n\n"
        "## Elsewhere\n\n"
        "Prompt the phase blocks `sub1`-`sub4`, or work from the phase table.\n"
    )
    findings = check_fallback_completeness(text, GOAL_ONLY)
    assert findings, "a fallback in another section covered the `/goal` occurrence"
    assert any("goal-slash-command" in f and "line 3" in f for f in findings), findings
    assert not any("Elsewhere" in f and "no non-Hermes fallback" in f for f in findings), findings

    # And a row-scoped occurrence is satisfied by its own row.
    row = (
        "| Pipeline invocation | `/goal <request>` (Hermes-only) | prompt the phases in order |\n"
    )
    assert check_fallback_completeness(row, GOAL_ONLY) == [], check_fallback_completeness(
        row, GOAL_ONLY
    )


# --- mandated-skill reachability & the canonical-set floor -------------------
#
# AC-HRN-015..017 close the three seams left after the fallback-completeness
# block. A mandated skill could be named in `AGENTS.md` §1 and resolve nowhere
# (015); the harness set was read as an exact four rather than a floor (016);
# and the Gemini CLI entry point had to be a symlink, not a fork (017).

MANDATED_SKILLS_HEADING = "1. Mandated Skills"
MANDATED_LIST_RE = re.compile(r"Load on EVERY task:(.*?)(?:\.\s|\.$)", re.S)
BACKTICK_RE = re.compile(r"`([^`]+)`")
HTTP_SOURCE_RE = re.compile(r"https?://")


def mandated_skills(text):
    """The skill names `AGENTS.md` §1 names in its *Load on EVERY task* list.

    Read off the `### 1. Mandated Skills` region, so a skill named anywhere else
    in the file does not count, and restricted to that one sentence's backticked
    tokens: a token that is a path (`.agents/skills/`) or a file (`SKILL.md`) is
    not a skill NAME and is dropped.
    """
    region = heading_region(text, MANDATED_SKILLS_HEADING, level=3)
    assert region, f"AGENTS.md has no '### {MANDATED_SKILLS_HEADING}' heading"
    match = MANDATED_LIST_RE.search(region)
    assert match, "the mandated-skills subsection states no 'Load on EVERY task' list"
    return [
        token
        for token in BACKTICK_RE.findall(match.group(1))
        if "/" not in token and "." not in token
    ]


def readme_skill_sources(readme_text):
    """{skill name: source cell} for `README.md` § *Skills*' install table.

    Located by its `Skill` + `Source` headers, never by position, so the table
    can move or grow a column without blinding the check.
    """
    sources = {}
    for table in parse_tables(strip_fenced_blocks(readme_text)):
        headers = table["headers"]
        if not any(re.fullmatch(r"skill", h, re.I) for h in headers):
            continue
        source_col = next((h for h in headers if re.search(r"source", h, re.I)), None)
        if source_col is None:
            continue
        for row in table["rows"]:
            name = row["__label__"].strip().strip("`").strip()
            if name:
                sources[name] = row.get(source_col, "")
    return sources


def skill_resolution_findings(skills, repo_root, sources):
    """Findings for a mandated-skill list. Empty list == every skill resolves.

    A skill resolves when it is vendored — `.agents/skills/<name>/SKILL.md`
    travels with the repo — OR when a `README.md` § *Skills* row names it with an
    install-source URL. Either is reachable from a fresh clone.
    """
    findings = []
    for name in skills:
        if (repo_root / ".agents" / "skills" / name / "SKILL.md").is_file():
            continue
        if HTTP_SOURCE_RE.search(sources.get(name, "")):
            continue
        findings.append(
            f"{name!r} is mandated by AGENTS.md §1 but resolves nowhere: no "
            f".agents/skills/{name}/SKILL.md travels with the repo and README.md "
            "§ Skills carries no install-source URL for it"
        )
    return findings


def test_every_mandated_skill_resolves_without_network_archaeology():
    """AC-HRN-015: every skill `AGENTS.md` §1 mandates resolves to a vendored
    `.agents/skills/<name>/SKILL.md` or to a `README.md` § *Skills* row carrying
    an install-source URL, so a clone can satisfy every gate. Negative control: a
    synthetic mandated skill with neither is reported."""
    text = _agents_text()
    skills = mandated_skills(text)
    assert len(skills) >= 5, (
        f"parsed only {len(skills)} mandated skill(s) out of §1: {skills} — the "
        "list parse is broken, or the section shrank to near nothing"
    )
    sources = readme_skill_sources(README_MD.read_text(encoding="utf-8"))
    assert sources, "README.md § Skills has no Skill/Source install table"
    findings = skill_resolution_findings(skills, REPO_ROOT, sources)
    assert findings == [], "; ".join(findings)

    ghost = skill_resolution_findings(["ghost-skill"], REPO_ROOT, sources)
    assert ghost, "the resolution check passed a skill that resolves nowhere"
    assert any("ghost-skill" in f for f in ghost), ghost


def test_canonical_harness_set_is_a_minimum_not_a_closed_set():
    """AC-HRN-016: the canonical four are a FLOOR. A harness named in BOTH
    `AGENTS.md` and `README.md` pairs and is accepted; the same harness with a
    README-only row is reported as drift — so adding a harness edits two
    documents, never a test regex."""
    agents_text = _agents_text()
    readme = strip_fenced_blocks(README_MD.read_text(encoding="utf-8"))
    labels = readme_harness_labels(readme)
    assert missing_harnesses(agents_text) == [], (
        "the canonical four are no longer all named — AC-HRN-016's floor is broken"
    )
    assert unpaired_harnesses(agents_text, labels) == [], (
        "the real README ↔ AGENTS.md pair already drifted (AC-HRN-004)"
    )

    # A synthetic FIFTH harness named in both documents pairs and passes.
    fifth = "Zed IDE"
    paired = unpaired_harnesses(
        agents_text + f"\n{fifth} is a bound harness in this adapter.\n",
        labels + [fifth],
    )
    assert paired == [], (
        f"a fifth harness named in both documents was reported as drift: {paired} — "
        "the canonical set is being read as a closed set"
    )

    # The same harness, README-only, is still drift.
    findings = unpaired_harnesses(agents_text, labels + [fifth])
    assert any(fifth in f for f in findings), (
        "a README-only harness row passed the pairing check"
    )


def test_gemini_cli_entry_point_symlinks_to_agents_md():
    """AC-HRN-017: the Gemini CLI entry point (`GEMINI.md`, its default context
    file) is a symlink resolving to the one canonical `AGENTS.md`, not a copy."""
    path = REPO_ROOT / "GEMINI.md"
    assert os.path.islink(path), (
        "GEMINI.md is not a symlink — Gemini CLI would read a forked copy of the "
        "doctrine instead of the file the context budget is measured on"
    )
    assert os.path.exists(path), "GEMINI.md is a dangling symlink"
    assert path.resolve() == AGENTS_MD.resolve(), (
        f"GEMINI.md resolves to {path.resolve()}, not to {AGENTS_MD}"
    )
    assert path.read_text(encoding="utf-8") == AGENTS_MD.read_text(encoding="utf-8"), (
        "GEMINI.md resolves to AGENTS.md but reads back different bytes"
    )
