"""Corpus-integrity tier — raw sources: frontmatter, sha stamps, counts. IDs: AC-EXC-0NN."""
import hashlib
import re
from pathlib import Path

KB = Path(__file__).resolve().parents[2] / "kb"
REQUIRED_KEYS = ("source_url", "ingested", "sha256")


def _raw_files():
    """All raw sources: transcripts plus articles (sorted for determinism)."""
    return sorted((KB / "raw/transcripts").glob("*.txt")) + sorted(
        (KB / "raw/articles").glob("*.md")
    )


def _split_frontmatter(text):
    """Split a raw source into (frontmatter-fields, body). Body is used for sha."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    assert m, "file has no YAML frontmatter"
    fields = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, m.group(2)


def test_transcripts_frontmatter_and_sha():
    """AC-EXC-001: transcripts carry source_url/ingested/sha256 and the sha matches body.strip()."""
    for path in sorted((KB / "raw/transcripts").glob("*.txt")):
        fields, body = _split_frontmatter(path.read_text())
        for key in REQUIRED_KEYS:
            assert key in fields, f"{path}: missing frontmatter key {key!r}"
        digest = hashlib.sha256(body.strip().encode()).hexdigest()
        assert fields["sha256"] == digest, f"{path}: sha256 drift"


def test_articles_frontmatter_and_sha():
    """AC-EXC-002: articles carry source_url/ingested/sha256 and the sha matches body.strip()."""
    for path in sorted((KB / "raw/articles").glob("*.md")):
        fields, body = _split_frontmatter(path.read_text())
        for key in REQUIRED_KEYS:
            assert key in fields, f"{path}: missing frontmatter key {key!r}"
        digest = hashlib.sha256(body.strip().encode()).hexdigest()
        assert fields["sha256"] == digest, f"{path}: sha256 drift"


def test_raw_source_counts():
    """AC-EXC-003: at least 11 transcripts and at least 2 articles exist."""
    assert len(list((KB / "raw/transcripts").glob("*.txt"))) >= 11
    assert len(list((KB / "raw/articles").glob("*.md"))) >= 2


def test_raw_frontmatter_values():
    """AC-EXC-011: frontmatter values are non-empty; ingested is ISO; source_url is http(s)."""
    for path in _raw_files():
        fields, _ = _split_frontmatter(path.read_text())
        for value in fields.values():
            assert isinstance(value, str) and value.strip(), f"{path}: empty frontmatter value"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields["ingested"]), (
            f"{path}: ingested {fields['ingested']!r} is not an ISO date"
        )
        assert fields["source_url"].startswith(("http://", "https://")), (
            f"{path}: source_url {fields['source_url']!r} is not http(s)"
        )