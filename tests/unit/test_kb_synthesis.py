"""KB synthesis tier — layer-2 pages: counts, index, wikilinks, sources, tags. IDs: AC-EXC-02N."""
import re
from pathlib import Path

KB = Path(__file__).resolve().parents[2] / "kb"
PAGE_DIRS = ("concepts", "entities", "comparisons", "queries")


def _layered_pages():
    """All layer-2 pages across concepts/, entities/, comparisons/, queries/."""
    return [p for d in PAGE_DIRS for p in sorted((KB / d).glob("*.md"))]


def _split_frontmatter(text):
    """Split a page into (frontmatter-fields, body)."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    assert m, "file has no YAML frontmatter"
    fields = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, m.group(2)


def _resolve_wikilink(target):
    """Resolve a [[target]] to a kb/ file: strip kb/, honor paths, else try subdirs."""
    t = target.strip()
    if t.startswith("kb/"):
        t = t[len("kb/"):]
    if "/" in t:
        return (KB / (t if t.endswith(".md") else t + ".md")).exists()
    if t.endswith(".md"):
        t = t[:-3]
    return any((KB / d / f"{t}.md").exists() for d in PAGE_DIRS)


def test_layer2_page_counts():
    """AC-EXC-021: at least 8 concepts, 2 entities, and 4 comparisons exist."""
    assert len(list((KB / "concepts").glob("*.md"))) >= 8
    assert len(list((KB / "entities").glob("*.md"))) >= 2
    assert len(list((KB / "comparisons").glob("*.md"))) >= 4


def test_all_pages_indexed():
    """AC-EXC-022: every layer-2 page is listed in kb/index.md by relative path."""
    index = (KB / "index.md").read_text()
    for path in _layered_pages():
        rel = path.relative_to(KB).as_posix()
        assert rel in index, f"{path}: {rel!r} missing from kb/index.md"


def test_no_broken_wikilinks():
    """AC-EXC-023: every [[target]] in layer-2 pages resolves to a file under kb/."""
    for path in _layered_pages():
        for target in re.findall(r"\[\[([^\]]+)\]\]", path.read_text()):
            assert _resolve_wikilink(target), f"{path}: broken wikilink [[{target}]]"


def test_sources_and_tags():
    """AC-EXC-024: pages cite a raw source (frontmatter or footer) and use only SCHEMA tags."""
    schema = (KB / "SCHEMA.md").read_text()
    for path in _layered_pages():
        text = path.read_text()
        fields, body = _split_frontmatter(text)
        assert "raw/" in fields.get("sources", "") or "raw/" in body, (
            f"{path}: no citation to a kb/raw/ source"
        )
        assert "tags" in fields, f"{path}: missing frontmatter key 'tags'"
        m = re.search(r"\[(.*)\]", fields["tags"])
        assert m, f"{path}: tags not a list"
        for tag in m.group(1).split(","):
            tag = tag.strip()
            assert tag, f"{path}: empty tag"
            assert re.search(rf"\b{re.escape(tag)}\b", schema), (
                f"{path}: tag {tag!r} not in SCHEMA.md taxonomy"
            )