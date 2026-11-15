"""Relative-link guard for the tracked markdown corpus. ID: AC-FUN-005.

Every tracked `.md` file's relative links must point at a path that exists:
`[text](path)` and `[text](path#anchor)`. A link that references a file nobody
moved is how a doctrine set rots silently — the prose still reads correctly while
the reader lands nowhere. `docs/prd/03-funnel-kb-governance.md` owns the rule.

Scope, and why each exclusion exists:

- `kb/_archive/` — superseded records frozen as they were archived; a link into a
  tree that has since moved is part of the record, not a defect to fix (funnel
  rule 5: archive, never rewrite history).
- `docs/gaps/_archive/` is **not** skipped. A closed gap is retained, never
  deleted, its path structure preserved (funnel rule 7; `docs/gaps/README.md`) —
  but retention is not link immutability: its references to the codebase and to
  other docs stay maintained, so a stale one is a real defect and this check
  reports it. (Nine of the first run's findings were archived gaps.)
- `kb/raw/` — immutable source material, add-only (funnel rule 3); a broken link
  in an ingested source cannot be edited away.
- `kb/` outside `kb/raw/` — layer-2 pages are `llm-wiki` output, never
  hand-written (funnel rule 4), so this check skips them rather than demanding an
  edit the doctrine forbids. Fix those by re-running `llm-wiki` on `./kb/`.
- `scratchpads/` — gitignored scratch space, never cited (rule 6).

Also skipped, because they are not file paths: HTML comments (`<!-- ... -->`),
fenced code blocks, inline code spans, `http(s)://` / `mailto:` / `ftp:` /
`data:` targets, and pure `#anchor` links. **Anchors are not validated** — only
the path is — so a heading may be renamed without breaking this test.

Deliberately NOT handled — a link in one of these forms goes unchecked, or is
compared literally instead of decoded:

- reference-style links (`[text][ref]` plus a `[ref]: path` definition);
- the **outer** target of an image inside a link — in
  `[![alt](img.png)](target.png)` the inner `img.png` is checked, `target.png`
  is not;
- an angle-bracket path that contains spaces (`[text](<a b.md>)`);
- a single-quoted title (`[text](path 'title')`);
- percent-encoded paths — `[text](a%20b.md)` is compared against the literal
  `a%20b.md`, never decoded to `a b.md`;
- a `?query` suffix — only `#anchor` is stripped, so `[text](page.md?v=1)` is
  reported as a missing file;
- a link-like string inside a 4-space indented code block — only ``` / ~~~
  fences are recognised, so indented code is scanned as prose.

A path quoted in a code span is never checked either — do not rely on this gate
for any of the forms above.

Hermetic: file reads and one `git ls-files`, run only when `root` is itself a
checkout (`.git` present) and falling back to a directory walk otherwise, so a
`tmp_path` that merely sits inside some other repo cannot return that repo's
files. Read-only.
"""
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = (
    "kb/_archive/",
    "kb/raw/",
    "scratchpads/",
)

# Targets that are not relative paths into this tree.
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "data:", "//")

FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")
# `<!-- ... -->` — a link written inside a comment is not a live reference.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# `[text](target)` and `![alt](target)`, with an optional "title".
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")


def strip_html_comments(text):
    """Blank out each `<!-- ... -->` span, keeping its newlines so line numbers hold."""
    return HTML_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def iter_link_targets(text):
    """(line_number, target) for every link/image outside fenced and inline code."""
    in_fence = False
    for number, raw in enumerate(strip_html_comments(text).splitlines(), 1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_RE.finditer(INLINE_CODE_RE.sub("", raw)):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            yield number, target


def broken_links(root, files):
    """[(repo-relative file, line, target)] for relative links whose path is absent."""
    findings = []
    for path in files:
        for number, target in iter_link_targets(path.read_text(encoding="utf-8")):
            if target.startswith("#") or target.startswith(EXTERNAL_PREFIXES):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            if target_path.startswith("/"):
                resolved = Path(os.path.normpath(root / target_path.lstrip("/")))
            else:
                resolved = Path(os.path.normpath(path.parent / target_path))
            if not resolved.exists():
                findings.append((path.relative_to(root).as_posix(), number, target))
    return findings


def _tracked(root):
    """Every tracked `.md`, or a directory walk when `root` is not a checkout."""
    if not (root / ".git").exists():
        # Asked of a plain directory, `git ls-files` walks up to the enclosing
        # repo and returns THAT repo's files — never what this check owns.
        return sorted(root.rglob("*.md"))
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0:
        return [root / name for name in proc.stdout.split("\0") if name]
    return sorted(root.rglob("*.md"))


def markdown_files(root):
    """The tracked markdown files this check owns, after the documented skips."""
    files = []
    for path in _tracked(root):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(skip) for skip in SKIP_DIRS):
            continue
        # llm-wiki layer-2 pages (kb/ outside kb/raw/) are generated, never edited.
        if rel.startswith("kb/") and not rel.startswith("kb/raw/"):
            continue
        files.append(path)
    return files


def test_relative_markdown_links_resolve():
    """AC-FUN-005: every relative link in a tracked `.md` points at a path that
    exists. Anchors are not validated; the skips are documented in the module
    docstring."""
    files = markdown_files(REPO_ROOT)
    assert len(files) > 20, f"only {len(files)} markdown files scanned — scan is wrong"
    findings = broken_links(REPO_ROOT, files)
    assert findings == [], "broken relative markdown links:\n" + "\n".join(
        f"{name}:{line}: {target}" for name, line, target in findings
    )


def test_link_checker_ignores_commented_out_links(tmp_path):
    """AC-FUN-005: a link inside an HTML comment is not reported — a commented-out
    link is documentation, not a live reference; multi-line comments count too."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Doc\n"
        "\n"
        "<!-- [gone](commented-out.md) -->\n"
        "<!--\n"
        "[also-gone](multiline.md)\n"
        "-->\n"
        "[still-gone](real.md)\n",
        encoding="utf-8",
    )
    findings = broken_links(tmp_path, [doc])
    assert [target for _, _, target in findings] == ["real.md"], findings
    assert findings[0][:2] == ("doc.md", 7)  # line numbers survive the stripping


def test_link_checker_reports_a_broken_link(tmp_path):
    """AC-FUN-005: negative control — a missing target is reported with file:line;
    an existing one, an anchor, and an external URL are not."""
    (tmp_path / "present.md").write_text("# Present\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Doc\n"
        "\n"
        "[ok](present.md#a-heading)\n"
        "[gone](missing.md)\n"
        "[anchor](#doc)\n"
        "[site](https://example.com/missing.md)\n"
        "`[inline](missing-again.md)`\n"
        "```\n"
        "[fenced](missing-too.md)\n"
        "```\n",
        encoding="utf-8",
    )
    findings = broken_links(tmp_path, [doc])
    assert [target for _, _, target in findings] == ["missing.md"], findings
    assert findings[0][:2] == ("doc.md", 4)


def test_link_checker_skips_archive_and_generated_kb(tmp_path):
    """AC-FUN-005: the documented skips hold — archived records, immutable
    `kb/raw/`, and generated `kb/` layer-2 pages are not scanned."""
    for rel in ("kb/_archive/k.md", "kb/raw/source.md", "kb/concepts/concept.md",
                "scratchpads/n.md", "docs/keep.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[gone](missing.md)\n", encoding="utf-8")

    scanned = {p.relative_to(tmp_path).as_posix() for p in markdown_files(tmp_path)}
    assert scanned == {"docs/keep.md"}, scanned
