"""The veteran register as a machine-checkable table (unit tier).

`docs/prd/28-veteran-layer.md` § *The register* lists twenty portable
decisions, each with the failure that earned it, an enforcement cell and a
source. This module holds that table to its own claims: AC-VET-001..006 here
and AC-VET-008 for the layer model in `ADOPTING.md`; AC-VET-007 is the
behavioural local-CI guard in `tests/unit/test_local_ci_guard.py`. Hermetic:
three tracked file reads and stdlib parsing only.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRD = REPO_ROOT / "docs" / "prd" / "28-veteran-layer.md"
GAP = REPO_ROOT / "docs" / "gaps" / "28-veteran-rules-unenforced.md"
ADOPTING = REPO_ROOT / "ADOPTING.md"

# The five cells of a register row, in table order.
FIELDS = ("id", "rule", "earned-by", "enforcement", "source")
ID_RE = re.compile(r"^VD-\d{2}$")
# An absolute path: a slash opening a token, not a path separator mid-token.
ABS_PATH_RE = re.compile(r"(?:^|[\s(])/\S")
# A sibling checkout's name must never reach the register.
SIBLINGS = ("vanilla-open-design", "media-gen-ops")
DECLARED = "declared: none"
ENFORCED_KINDS = ("test", "test-partial")
EXPECTED_IDS = [f"VD-{n:02d}" for n in range(1, 21)]
LAYER_ALIASES = {
    0: ("Layer 0", "0 — core"),
    1: ("Layer 1", "1 — instruments"),
    2: ("Layer 2", "2 — game"),
}
LAYER_RULE = "configured downstream, never forked"


# --- table parsing ---------------------------------------------------------


def parse_table_rows(text):
    """Every markdown row whose first cell is a `VD-NN` id.

    Returns dicts of `id` plus `cells`, the stripped cells of the row. The
    cell list is kept whole so a short row can be reported instead of
    silently dropped.
    """
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if cells and ID_RE.match(cells[0]):
            rows.append({"id": cells[0], "cells": cells})
    return rows


def parse_register(text):
    """The register rows of the PRD (§ *The register*)."""
    return parse_table_rows(text)


def parse_gap_listing(text):
    """`id` -> the gap-table row that lists it, in the gap file."""
    return {
        row["id"]: " | ".join(row["cells"])
        for row in parse_table_rows(text)
    }


def cell(row, name):
    """One named cell of a row, or '' when the row is short."""
    index = FIELDS.index(name)
    cells = row["cells"]
    return cells[index] if index < len(cells) else ""


def unwrap(value):
    """A cell with its markdown backticks removed."""
    return value.replace("`", "").strip()


def enforcement_kind(row):
    """(kind, target) of an enforcement cell: `test`, `test-partial`,
    `declared`, or ('', text) when the cell carries no colon."""
    text = unwrap(cell(row, "enforcement"))
    kind, sep, target = text.partition(":")
    if not sep:
        return "", text
    return kind.strip(), target.strip()


def layer_section(text):
    """Body of the section whose heading starts `## Layer model`, or None."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## Layer model"):
            start = index
            break
    if start is None:
        return None
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


# --- findings helpers (empty list == conformant) ---------------------------


def check_shape(rows):
    """Findings for the row count and the id set (AC-VET-001)."""
    findings = []
    if len(rows) != len(EXPECTED_IDS):
        findings.append(
            f"parsed {len(rows)} register row(s), expected {len(EXPECTED_IDS)}"
        )
    ids = [row["id"] for row in rows]
    missing = [name for name in EXPECTED_IDS if name not in ids]
    extra = [name for name in ids if name not in EXPECTED_IDS]
    if missing:
        findings.append(f"missing id(s): {missing}")
    if extra:
        findings.append(f"unexpected id(s): {extra}")
    return findings


def check_cells(rows):
    """Findings naming the id and the column of every blank cell
    (AC-VET-002)."""
    findings = []
    for row in rows:
        if len(row["cells"]) != len(FIELDS):
            findings.append(
                f"{row['id']}: {len(row['cells'])} cell(s), expected "
                f"{len(FIELDS)} — id | rule | earned-by | enforcement | source"
            )
            continue
        for name in FIELDS:
            if not cell(row, name):
                findings.append(f"{row['id']}: empty cell in column '{name}'")
    return findings


def check_enforced_paths(rows, root=REPO_ROOT):
    """Findings for a `test:` / `test-partial:` cell naming no file
    (AC-VET-003)."""
    findings = []
    for row in rows:
        kind, target = enforcement_kind(row)
        if kind not in ENFORCED_KINDS:
            continue
        if not target:
            findings.append(f"{row['id']}: '{kind}:' names no path")
        elif not (root / target).is_file():
            findings.append(
                f"{row['id']}: enforcement path does not exist: {target}"
            )
    return findings


def check_declared_listed(rows, gap_text):
    """Both directions of the declared <-> gap-listing link (AC-VET-004).

    Forward: every `declared: none` row is named in the gap file by id.
    Reverse: every id the gap file lists belongs to a row this repo does not
    fully enforce — `declared`, or a `test-partial` row whose gap line says
    which half is partial. VD-18 is the one partial row the gap lists.
    """
    declared = {
        row["id"] for row in rows
        if unwrap(cell(row, "enforcement")) == DECLARED
    }
    listing = parse_gap_listing(gap_text)
    findings = [
        f"{name}: declared but not listed in {GAP.name}"
        for name in sorted(declared - set(listing))
    ]
    by_id = {row["id"]: row for row in rows}
    for name in sorted(set(listing) - declared):
        row = by_id.get(name)
        if row is None:
            findings.append(
                f"{name}: listed in {GAP.name} but it is not a register row"
            )
        elif not _partial_listed(row, listing[name]):
            findings.append(
                f"{name}: listed in {GAP.name} but its enforcement is "
                f"'{unwrap(cell(row, 'enforcement'))}'"
            )
    return findings


def _partial_listed(row, gap_row):
    """True when a `test-partial` row's gap row admits the missing half."""
    kind = enforcement_kind(row)[0]
    return kind == "test-partial" and "test-partial" in gap_row


def check_portability(rows):
    """Findings for any cell that is machine-bound (AC-VET-005)."""
    findings = []
    for row in rows:
        for name in FIELDS:
            for hit in _machine_bound(cell(row, name)):
                findings.append(f"{row['id']}: {name} cell carries {hit}")
        source = unwrap(cell(row, "source"))
        if source and not source.startswith(("docs/", "https://")):
            findings.append(
                f"{row['id']}: source {source!r} is neither docs/ nor "
                "https://"
            )
    return findings


def _machine_bound(value):
    """The machine-bound fragments one cell carries, named for the report."""
    hits = []
    if ABS_PATH_RE.search(value):
        hits.append("an absolute path")
    if "scratchpads/" in value:
        hits.append("'scratchpads/'")
    if ".." in value:
        hits.append("a '..' traversal")
    for name in SIBLINGS:
        if name in value:
            hits.append(f"the sibling checkout name {name!r}")
    return hits


def check_id_uniqueness(rows):
    """Findings for duplicate or non-contiguous ids (AC-VET-006)."""
    ids = [row["id"] for row in rows]
    findings = []
    duplicate = sorted({name for name in ids if ids.count(name) > 1})
    if duplicate:
        findings.append(f"duplicate id(s): {duplicate}")
    numbers = {int(name[3:]) for name in ids}
    absent = [n for n in range(1, len(EXPECTED_IDS) + 1) if n not in numbers]
    if absent:
        findings.append(f"id gap(s): {[f'VD-{n:02d}' for n in absent]}")
    return findings


def check_layer_model(text):
    """Findings for the layer-model section of ADOPTING.md (AC-VET-008)."""
    body = layer_section(text)
    if body is None:
        return ["no heading starting '## Layer model'"]
    # A sentence may be wrapped mid-phrase, so match against flat prose.
    flat = " ".join(body.split()).lower()
    findings = []
    for number, names in LAYER_ALIASES.items():
        if not any(name in flat for name in names):
            aliases = " or ".join(names)
            findings.append(f"does not name layer {number} ({aliases})")
    if LAYER_RULE not in flat:
        findings.append(f"does not say a game layer is {LAYER_RULE}")
    return findings


# --- tests -----------------------------------------------------------------


def _register():
    """The parsed register; a parse of zero rows is itself the failure."""
    rows = parse_register(PRD.read_text(encoding="utf-8"))
    assert rows, (
        f"parsed no register rows out of {PRD.relative_to(REPO_ROOT)} — the "
        "table parser or the path is wrong"
    )
    return rows


def test_register_parses_twenty_rows():
    """AC-VET-001: the PRD carries a table of exactly twenty rows, and the
    ids are `VD-01`..`VD-20`."""
    rows = _register()
    findings = check_shape(rows)
    assert findings == [], "; ".join(findings)
    assert {row["id"] for row in rows} == set(EXPECTED_IDS)


def test_every_register_cell_is_filled():
    """AC-VET-002: each row carries five non-empty cells; a blank cell is
    reported by id and column name."""
    rows = _register()
    findings = check_cells(rows)
    assert findings == [], "; ".join(findings)


def test_enforced_rows_name_an_existing_test():
    """AC-VET-003: a `test:` / `test-partial:` cell names a repo-relative
    path that exists, so a claimed enforcement cannot rot."""
    rows = _register()
    kinds = {enforcement_kind(row)[0] for row in rows}
    assert set(ENFORCED_KINDS) | {"declared"} <= kinds, (
        f"the register uses only {sorted(kinds)} — one kind vanished, so one "
        "of the checks below cannot run in earnest"
    )
    findings = check_enforced_paths(rows)
    assert findings == [], "; ".join(findings)


def test_declared_rows_are_listed_in_the_gap():
    """AC-VET-004: every `declared: none` row is named in the gap file by
    id, and every id the gap file lists is a row this repo does not fully
    enforce."""
    rows = _register()
    gap_text = GAP.read_text(encoding="utf-8")
    findings = check_declared_listed(rows, gap_text)
    assert findings == [], "; ".join(findings)


def test_no_cell_is_machine_bound():
    """AC-VET-005: no absolute path, `scratchpads/`, `..` or sibling
    checkout name in any cell; every source is repo-relative or `https://`."""
    rows = _register()
    findings = check_portability(rows)
    assert findings == [], "; ".join(findings)


def test_ids_are_unique_and_contiguous():
    """AC-VET-006: no duplicate id and no gap in `VD-01`..`VD-20`."""
    rows = _register()
    findings = check_id_uniqueness(rows)
    assert findings == [], "; ".join(findings)


def test_layer_model_is_stated_in_adopting():
    """AC-VET-008: `ADOPTING.md` carries a *Layer model* heading naming all
    three layers and the rule that a game is configured downstream."""
    findings = check_layer_model(ADOPTING.read_text(encoding="utf-8"))
    assert findings == [], "; ".join(findings)


def test_shape_check_reports_a_short_register():
    """AC-VET-001: negative control — nineteen rows fail, and the missing id
    is named."""
    findings = check_shape(_register()[:-1])
    assert findings, "the shape check passed a nineteen-row register"
    assert any("19" in finding for finding in findings), findings


def test_cell_check_names_the_empty_column():
    """AC-VET-002: negative control — a blank `earned-by` cell is reported
    against the id and the column."""
    row = {"id": "VD-99", "cells": ["VD-99", "a rule", "", "declared: none",
                                    "docs/x.md"]}
    findings = check_cells([row])
    assert findings, "the cell check passed a blank earned-by cell"
    assert "VD-99" in findings[0] and "earned-by" in findings[0], findings


def test_path_check_reports_a_missing_test_file():
    """AC-VET-003: negative control — a `test:` cell pointing at a non-file
    is reported by id and path."""
    row = {"id": "VD-99", "cells": ["VD-99", "a rule", "a failure",
                                    "`test: tests/unit/test_ghost.py`",
                                    "`docs/x.md`"]}
    findings = check_enforced_paths([row], root=REPO_ROOT)
    assert findings, "the path check passed a test path that does not exist"
    assert "VD-99" in findings[0] and "test_ghost.py" in findings[0], findings


def test_declared_check_reports_both_directions():
    """AC-VET-004: negative control — a declared row missing from the gap
    file and a gap listing for a fully enforced row both fail."""
    declared = {"id": "VD-01", "cells": ["VD-01", "r", "e", "declared: none",
                                         "`docs/x.md`"]}
    enforced = {"id": "VD-02", "cells": ["VD-02", "r", "e",
                                         "`test: tests/unit/x.py`",
                                         "`docs/x.md`"]}
    missing = check_declared_listed([declared, enforced], "| Rule |\n|---|\n")
    assert any("VD-01" in finding for finding in missing), missing
    stray = check_declared_listed([declared, enforced],
                                  "| VD-02 | not enforced | closed by |\n")
    assert any("VD-02" in finding for finding in stray), stray
    both = ("| VD-01 | gap | closed by |\n"
            "| VD-02 | gap, `test-partial` half | closed by |\n")
    assert check_declared_listed(
        [declared, {"id": "VD-02", "cells": ["VD-02", "r", "e",
                                             "`test-partial: tests/unit/x.py`",
                                             "`docs/x.md`"]}], both) == []


def test_portability_check_rejects_machine_paths():
    """AC-VET-005: negative control — an absolute path, `scratchpads/`, a
    `..` traversal and a sibling name are each reported."""
    for bad in ("/Users/me/repo/x.md", "`scratchpads/probe.md`",
                "../sibling/x.md", "vanilla-open-design/x.md"):
        row = {"id": "VD-99", "cells": ["VD-99", "r", "e", "`test: x`",
                                        bad]}
        findings = check_portability([row])
        assert findings, f"the portability check passed {bad!r}"
        assert any("VD-99" in finding for finding in findings), findings
    offsite = {"id": "VD-99", "cells": ["VD-99", "r", "e", "`test: x`",
                                        "kb/concepts/x.md"]}
    assert check_portability([offsite]), "a non-docs source must be reported"


def test_layer_model_check_requires_three_layers():
    """AC-VET-008: negative control — a section missing layer 2, or missing
    the never-forked rule, is reported."""
    body = "## Layer model\n\n| 0 — core | a |\n| 1 — instruments | b |\n"
    findings = check_layer_model(body)
    assert any("layer 2" in finding for finding in findings), findings
    assert any(LAYER_RULE in finding for finding in findings), findings
    assert check_layer_model("## Nothing\n"), "a missing section must fail"
