"""Unit tier — the tracked-file-size gate. IDs: AC-SIZE-0NN.

Hermetic: the auditor is loaded by path and driven in-process with main(argv)
against tmp_path — no subprocess, no service import, no transport, and nothing
written inside the repo. AC-SIZE-001 asserts the shipped tree passes at its
ADOPTED cap of 60 KB (the script default stays 20 KB and stays hard — see
docs/prd/27-file-size-audit.md); AC-SIZE-002 proves the cap is inclusive and
the flag moves it; AC-SIZE-003 pins the CLI contract and the cap arithmetic;
AC-SIZE-004 proves explicit paths override the tracked scope; AC-SIZE-005
holds the 80-column style rule; AC-SIZE-006 proves the policy exemptions
(kb/raw/, kb/log.md, autoresearch/uv.lock) are skipped and counted, never
reported as offenders.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit-size.py"
TEST = REPO_ROOT / "tests" / "unit" / "test_audit_size.py"
# The adopted cap: CI and this gate run --max-kb 60 because 30 tracked files
# are legitimately larger than 20 KB. 20 KB remains the script default and is
# still a hard failure; docs/prd/27-file-size-audit.md records the deviation.
ADOPTED_KB = "60"


def _load_audit_size():
    """Load scripts/audit-size.py by path (it is a CLI, not a package)."""
    spec = importlib.util.spec_from_file_location("audit_size", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


size = _load_audit_size()


def test_size_real_repo_is_within_adopted_cap(capsys):
    """AC-SIZE-001: the shipped tree passes at 60 KB; totals agree.

    The deviation is deliberate and recorded in
    docs/prd/27-file-size-audit.md: 20 KB is still the script default and
    still fails a file, but this repo cannot hold 20 KB (kb/raw/ is
    append-or-archive, kb/log.md is append-only, uv.lock is generated), so
    the gate runs at the adopted 60 KB instead.
    """
    assert size.main(["--max-kb", ADOPTED_KB]) == 0, (
        "a tracked file is over the adopted 61440-byte cap "
        "(`python3 scripts/audit-size.py --max-kb 60`). Shrink it, or split "
        "it, before merge — see docs/prd/27-file-size-audit.md."
    )

    capsys.readouterr()
    assert size.main(["--max-kb", ADOPTED_KB, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    totals = payload["totals"]
    assert payload["max_bytes"] == 61440
    assert totals["over"] == 0, "no tracked file may exceed the adopted cap"
    assert totals["files"] >= 50, "the tracked scope must be measured in full"
    assert totals["exempt"] > 0, "the policy exemptions must be live"
    assert 0 < totals["largest"] <= 61440
    widest = max(entry["bytes"] for entry in payload["files"])
    assert totals["largest"] == widest
    assert totals["largest"] == payload["files"][0]["bytes"], "largest first"


def test_size_cap_boundary_and_flag(tmp_path, capsys):
    """AC-SIZE-002: cap+1 fails, exactly cap passes, --max-kb lifts the cap."""
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * 20481)
    edge = tmp_path / "edge.txt"
    edge.write_bytes(b"x" * 20480)

    assert size.main([str(big)]) == 1
    out = capsys.readouterr().out
    assert str(big) in out, "the finding must name the offending file"
    assert "20481" in out, "the finding must carry the measured byte count"

    # The cap is inclusive: 20480 bytes is within a 20480-byte budget.
    assert size.main([str(edge)]) == 0
    out = capsys.readouterr().out
    assert "Over cap" not in out

    assert size.main([str(big), "--max-kb", "30"]) == 0
    capsys.readouterr()

    assert size.main([str(big), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["max_bytes"] == 20480
    assert payload["totals"]["over"] == 1
    assert payload["files"][0]["bytes"] == 20481
    assert payload["files"][0]["over"] is True


def test_size_cli_contract(tmp_path, capsys):
    """AC-SIZE-003: pin the default, the arithmetic, --help and a bad path."""
    assert size.build_parser().parse_args([]).max_kb == 20.0
    assert size.limit_bytes(20.0) == 20480
    assert size.limit_bytes(0.5) == 512

    with pytest.raises(SystemExit) as excinfo:
        size.main(["--help"])
    assert excinfo.value.code == 0

    missing = tmp_path / "does-not-exist.txt"
    assert size.main([str(missing)]) == 1
    err = capsys.readouterr().err
    assert str(missing) in err, "the error message must name the missing path"


def test_size_explicit_paths_override_tracked_scope(tmp_path, capsys):
    """AC-SIZE-004: measure only the named files, never the git scope."""
    a = tmp_path / "a.txt"
    a.write_bytes(b"a" * 20481)
    b = tmp_path / "b.txt"
    b.write_bytes(b"b" * 10)

    assert size.main([str(a), str(b), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    names = [Path(entry["file"]).name for entry in payload["files"]]
    assert payload["totals"]["files"] == 2, "explicit paths replace the scope"
    assert names == ["a.txt", "b.txt"], "largest first, and nothing else"
    flagged = [n for n, e in zip(names, payload["files"]) if e["over"]]
    assert flagged == ["a.txt"]
    assert payload["totals"]["over"] == 1
    assert payload["files"][1]["bytes"] == 10


def test_size_source_lines_fit_eighty_columns():
    """AC-SIZE-005: both new files stay within the 80-column style rule."""
    for path in (SCRIPT, TEST):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            assert len(line) <= 80, (
                f"{path.relative_to(REPO_ROOT)}:{number} is {len(line)} chars, "
                "over the 80-column limit"
            )


def _seed_exempt_tree(root):
    """Seed an over-cap tree: three policy-exempt paths and an ordinary twin.

    The tree is not a git repository, so the auditor takes its documented
    plain-walk fallback — the same scope, without touching the real repo.
    """
    for name in ("kb/raw/x.md", "kb/log.md", "autoresearch/uv.lock",
                 "ordinary.txt"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 20481)


def test_size_exempt_paths_are_skipped_and_counted(tmp_path, capsys):
    """AC-SIZE-006: exempt paths are counted, never reported as offenders.

    kb/raw/ is append-or-archive (funnel rule 3), kb/log.md is append-only
    and autoresearch/uv.lock is generated, so all three are exempt whatever
    their size — while a same-sized file with an ordinary name is still an
    offender at the unchanged 20 KB default. See
    docs/prd/27-file-size-audit.md.
    """
    _seed_exempt_tree(tmp_path)

    assert size.main(["--json"], root=tmp_path) == 1
    payload = json.loads(capsys.readouterr().out)
    totals = payload["totals"]
    assert payload["max_bytes"] == 20480, "the default cap is still hard"
    assert totals["exempt"] == 3, "all three policy classes must be exempt"
    assert [row["file"] for row in payload["files"]] == ["ordinary.txt"], (
        "an exempt path is never measured; the ordinary twin still is"
    )
    assert totals["files"] == 1, "exempt files never enter the measurement"
    assert totals["over"] == 1, "the same-sized ordinary file is an offender"
    assert payload["files"][0]["over"] is True

    # The human summary names the exemption count, so it is not silent.
    assert size.main([], root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "exempt: 3 (may not shrink by policy)" in out
    assert "ordinary.txt" in out, "the real offender is still reported"
    for name in ("kb/raw/x.md", "kb/log.md", "autoresearch/uv.lock"):
        assert name not in out, f"{name} is exempt and must not be reported"

    # Structural, not a size accident: a cap that clears every file still
    # skips the three, and the tree then passes.
    assert size.main(["--max-kb", ADOPTED_KB, "--json"], root=tmp_path) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["exempt"] == 3, "exemption does not depend on cap"
    assert payload["totals"]["files"] == 1
    assert payload["totals"]["over"] == 0

    # The matcher: a trailing '/' is a directory prefix, anything else must
    # match the whole path — no glob, no substring match.
    assert size.is_exempt("kb/raw/x.md") is True
    assert size.is_exempt("kb/raw") is False
    assert size.is_exempt("kb/log.md") is True
    assert size.is_exempt("kb/log.md.bak") is False
    assert size.is_exempt("nested/kb/log.md") is False
    assert size.is_exempt("autoresearch/uv.lock") is True
    assert size.is_exempt("ordinary.txt") is False
