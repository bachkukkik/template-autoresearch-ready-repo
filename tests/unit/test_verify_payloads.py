"""A `_Verify:` payload must cite a test that carries its AC id (unit tier).

Register rule VD-09 (`docs/prd/28-veteran-layer.md`): *a pointer is not
proof: the verifier must cite the same AC id.* This module reads every
`docs/prd/NN-*.md`, finds each `_Verify:` payload, and — when the payload
names both a test file and an AC id — requires the file to exist and every
cited id (ranges expanded) to appear in one of the cited files. A payload
that names only a CI job, or no AC id, states a claim a test cannot carry
and is out of scope. A retired passage between `~~` markers is not live, a
marker quoted in backticks is prose, and a suffixed id is its own id.

IDs: AC-VET-009. Hermetic: stdlib and tracked-file reads only.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRD_GLOB = "[0-9][0-9]-*.md"
MARKER = "_Verify:"
TEST_RE = re.compile(r"tests/[\w/.-]+\.(?:py|bats|sh)")
# An id may carry a lowercase letter suffix (`AC-VET-009b`), which is a
# distinct id: the suffix is never dropped.
AC_RE = re.compile(r"AC-[A-Z]+-\d{3}[a-z]?")
RANGE_RE = re.compile(r"AC-([A-Z]+)-(\d{3})\.\.(\d{3})")
# A payload ends at a blank line, or at a line whose first non-space
# character opens a bullet, a table row or a heading — indented or not.
STOPS = ("- ", "* ", "|", "#")
STRIKE = "~~"
# A scan that saw fewer payloads than this read nothing, so it proves nothing.
MIN_PAYLOADS = 20
# Likewise for the files: a PRD skipped by the glob hides all its payloads.
MIN_PRDS = 25


# --- payload extraction ----------------------------------------------------


def struck_spans(text):
    """Character spans between paired `~~` markers: retired passages."""
    spans, opening = [], None
    for match in re.finditer(re.escape(STRIKE), text):
        if opening is None:
            opening = match.start()
        else:
            spans.append((opening, match.end()))
            opening = None
    return spans


def line_starts(text):
    """Character offset at which each line of `text` begins."""
    starts, offset = [0], 0
    for line in text.splitlines(keepends=True):
        offset += len(line)
        starts.append(offset)
    return starts


def is_struck(spans, offset):
    """True when a character offset falls inside a retired passage."""
    return any(start <= offset < end for start, end in spans)


def marker_column(line):
    """Column just past a bare `_Verify:` marker; None when there is none.

    A marker preceded by a backtick sits in a code span: the line discusses
    the convention rather than carrying a payload.
    """
    at = line.find(MARKER)
    while at != -1:
        if at == 0 or line[at - 1] != "`":
            return at + len(MARKER)
        at = line.find(MARKER, at + len(MARKER))
    return None


def payloads(text):
    """Every live `_Verify:` payload: `{"line": N, "text": ...}`.

    A payload runs from a bare marker to the end of its paragraph or bullet.
    One inside a struck-through passage is retired, so it is not returned.
    """
    lines = text.splitlines()
    starts = line_starts(text)
    spans = struck_spans(text)
    found = []
    for index, line in enumerate(lines):
        column = marker_column(line)
        if column is None:
            continue
        if is_struck(spans, starts[index] + column):
            continue
        body = [line[column:]]
        for follow in lines[index + 1:]:
            if not follow.strip() or follow.lstrip().startswith(STOPS):
                break
            body.append(follow)
        found.append({"line": index + 1,
                      "text": " ".join(part.strip() for part in body)})
    return found


# --- citation extraction ---------------------------------------------------


def expand_ids(text):
    """Every AC id a payload cites, with `AC-X-001..003` ranges expanded."""
    ids = set(AC_RE.findall(text))
    for prefix, first, last in RANGE_RE.findall(text):
        for number in range(int(first), int(last) + 1):
            ids.add(f"AC-{prefix}-{number:03d}")
    return ids


def citations(text):
    """(test paths, AC ids) that one payload cites."""
    return TEST_RE.findall(text), expand_ids(text)


def carries(text, ac):
    """True when `text` names `ac` itself, not as a prefix of a longer id."""
    return re.search(re.escape(ac) + r"(?![a-z0-9])", text) is not None


def resolve_citation(path, root):
    """Absolute target of a cited path, or None when it leaves the root."""
    base = Path(root).resolve()
    target = (base / path).resolve()
    if base != target and base not in target.parents:
        return None
    return target


# --- findings (empty list == conformant) -----------------------------------


def check_document(name, text, root=REPO_ROOT):
    """Findings for one PRD's payloads, naming the PRD, line and subject."""
    findings = []
    for payload in payloads(text):
        files, ids = citations(payload["text"])
        if not files or not ids:
            continue
        where = f"{name}:{payload['line']}"
        corpus = []
        for path in files:
            target = resolve_citation(path, root)
            if target is None:
                findings.append(
                    f"{where}: {path} resolves outside the repo root"
                )
                continue
            if not target.is_file():
                findings.append(f"{where}: {path} does not exist")
                continue
            corpus.append(target.read_text(encoding="utf-8",
                                           errors="replace"))
        # A missing path is reported above; an id it cannot carry is not a
        # second finding for the same defect.
        if not corpus:
            continue
        text_of_files = "\n".join(corpus)
        for ac in sorted(ids):
            if not carries(text_of_files, ac):
                findings.append(
                    f"{where}: {ac} is cited but absent "
                    f"from {', '.join(files)}"
                )
    return findings


def documents(root=REPO_ROOT):
    """Every `docs/prd/NN-*.md`, as (name, text) pairs."""
    return [(path.name, path.read_text(encoding="utf-8"))
            for path in sorted((root / "docs" / "prd").glob(PRD_GLOB))]


def tree_payloads(root=REPO_ROOT):
    """Every live payload in `docs/prd/`, as (name, payload) pairs."""
    return [(name, payload) for name, text in documents(root)
            for payload in payloads(text)]


def check_tree(root=REPO_ROOT):
    """Findings for every PRD payload in `docs/prd/`."""
    findings = []
    for name, text in documents(root):
        findings.extend(check_document(name, text, root=root))
    return findings


# --- tests -----------------------------------------------------------------


def test_every_verify_payload_cites_a_test_carrying_its_ac():
    """AC-VET-009: each payload names a test file that exists and carries
    every AC id the payload cites, across every PRD this tree ships."""
    shipped = list((REPO_ROOT / "docs" / "prd").glob(PRD_GLOB))
    read = documents()
    assert len(read) == len(shipped), (
        f"read {len(read)} of {len(shipped)} PRD file(s)"
    )
    assert len(read) >= MIN_PRDS, f"only {len(read)} PRD(s) parsed"
    assert len(tree_payloads()) >= MIN_PAYLOADS, (
        "too few payloads parsed — the marker or the path is wrong"
    )
    findings = check_tree()
    assert findings == [], "; ".join(findings)


def test_a_cited_file_that_does_not_exist_is_reported(tmp_path):
    """AC-VET-009: negative control — a cited test path absent from the
    tree is reported once, naming the PRD and the path."""
    findings = check_document(
        "01-x.md", "_Verify:_ `tests/unit/test_ghost.py` (AC-X-001).",
        root=tmp_path)
    assert len(findings) == 1, findings
    assert "01-x.md" in findings[0], findings
    assert "test_ghost.py" in findings[0], findings


def test_a_cited_path_outside_the_root_is_reported(tmp_path):
    """AC-VET-009: negative control — a citation that climbs out of the
    root is reported instead of being read."""
    findings = check_document(
        "01-x.md", "_Verify:_ `tests/../../../../outside.py` (AC-X-001).",
        root=tmp_path)
    assert findings, "a citation escaping the root passed"
    assert "outside the repo root" in findings[0], findings


def test_a_letter_suffixed_id_is_checked_verbatim(tmp_path):
    """AC-VET-009: negative control — `AC-X-001b` is not satisfied by a
    file that carries only `AC-X-001`, and passes when it carries both."""
    target = tmp_path / "tests" / "unit" / "test_fake.py"
    target.parent.mkdir(parents=True)
    target.write_text("AC-X-001\n", encoding="utf-8")
    text = "_Verify:_ `tests/unit/test_fake.py` (AC-X-001b)."
    bad = check_document("01-x.md", text, root=tmp_path)
    assert bad, "a dropped suffix let the base id satisfy the claim"
    assert "AC-X-001b" in bad[0], bad
    target.write_text("AC-X-001 AC-X-001b\n", encoding="utf-8")
    assert check_document("01-x.md", text, root=tmp_path) == []


def test_a_marker_quoted_in_backticks_is_prose(tmp_path):
    """AC-VET-009: negative control — a line that discusses `_Verify:` in a
    code span carries no payload, so its citation is not checked."""
    prose = "There is no `_Verify:` check for this rule yet.\n"
    assert payloads(prose) == [], payloads(prose)
    line = "no `_Verify:` test names `tests/unit/test_ghost.py` (AC-X-001)."
    assert check_document("01-x.md", line, root=tmp_path) == []
    live = "_Verify:_ `tests/unit/test_ghost.py` (AC-X-001).\n"
    assert len(payloads(live)) == 1, payloads(live)


def test_an_indented_boundary_ends_a_payload():
    """AC-VET-009: an indented bullet or table row ends a payload, so a
    neighbour's citation is not read into it."""
    text = ("- _Verify:_ job `unit`.\n"
            "  - `tests/unit/test_ghost.py` (AC-X-001).\n")
    assert payloads(text)[0]["text"] == "_ job `unit`."


def test_an_id_absent_from_the_cited_file_is_reported(tmp_path):
    """AC-VET-009: negative control — an id the cited file never names is
    reported by id; the id it does name passes."""
    target = tmp_path / "tests" / "unit" / "test_fake.py"
    target.parent.mkdir(parents=True)
    target.write_text("AC-X-001\n", encoding="utf-8")
    bad = check_document(
        "01-x.md", "_Verify:_ `tests/unit/test_fake.py` (AC-X-002).",
        root=tmp_path)
    assert bad, "an id absent from the cited file passed"
    assert "AC-X-002" in bad[0], bad
    good = check_document(
        "01-x.md", "_Verify:_ `tests/unit/test_fake.py` (AC-X-001).",
        root=tmp_path)
    assert good == [], good


def test_an_ac_range_is_expanded(tmp_path):
    """AC-VET-009: negative control — `AC-X-001..003` cites three ids, so
    the third, which the file omits, is reported."""
    target = tmp_path / "tests" / "unit" / "test_fake.py"
    target.parent.mkdir(parents=True)
    target.write_text("AC-X-001 AC-X-002\n", encoding="utf-8")
    assert expand_ids("AC-X-001..003") == {"AC-X-001", "AC-X-002",
                                           "AC-X-003"}
    findings = check_document(
        "01-x.md", "_Verify:_ `tests/unit/test_fake.py` (AC-X-001..003).",
        root=tmp_path)
    assert any("AC-X-003" in finding for finding in findings), findings
    assert not any("AC-X-002" in finding for finding in findings), findings


def test_a_struck_through_payload_is_ignored():
    """AC-VET-009: negative control — a retired passage between `~~`
    markers is no live payload, so its dead citation is not reported."""
    text = ("- ~~**SC1** — retired. _Verify:_ `tests/unit/test_ghost.py`\n"
            "(AC-X-001).~~ **Retired 2026-11-04.**\n")
    assert payloads(text) == [], payloads(text)
    assert check_document("01-x.md", text) == []


def test_a_payload_without_an_ac_id_is_ignored():
    """AC-VET-009: a payload naming only a CI job, or only a test path,
    makes no id claim and is out of scope."""
    assert check_document(
        "01-x.md", "_Verify:_ `ci.yml` job `doctrine`.") == []
    assert check_document(
        "01-x.md", "_Verify:_ `tests/unit/test_ghost.py` and the `unit` "
        "job.") == []
