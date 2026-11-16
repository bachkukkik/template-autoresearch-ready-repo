#!/usr/bin/env python3
"""Import an external run ledger into a target profile's runs directory.

A season's record — ``state.json``, ``scoreboard.md``, the ``season-*`` archives
and the ``round-*`` directories — used to live inside the measured checkout. The
harness keeps its own state now (PRD 22), and this is the one command that moves
it: a copy, never a move, so the checkout it came from is left exactly as it was.
Runtime residue (a stale ``*.lock``, ``__pycache__``) is never carried.

Stdlib only, and no shell: every child is a copy call, not an exec.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

TARGET_DIR = Path(__file__).resolve().parent
REPO_ROOT = TARGET_DIR.parents[1]
sys.path.insert(0, str(TARGET_DIR))

import target as target_mod  # noqa: E402  — the one profile validator (PRD 22)

#: The state a round leaves; everything else in a runs dir is an archive of it.
STATE_FILES = ("state.json", "scoreboard.md")
ARCHIVE_GLOBS = ("season-*", "round-*")
SKIP = ("*.lock", "__pycache__")


def default_to(profile_name: str, targets: Path | str | None = None) -> Path:
    """The harness-owned runs directory, resolved by the one profile validator.

    The same ``load_profile``/``apply_profile`` pair the plan uses decides both
    the name and the relativity, so ``import-runs`` and ``profile`` cannot drift:
    ``runs_dir`` is harness-relative or an absolute path inside this repo. The
    checkout base is irrelevant here — only harness keys are read, and nothing
    is touched — so the harness repo itself stands in for it.
    """
    try:
        path = target_mod.profile_path(profile_name, targets)
        resolution = target_mod.apply_profile(
            target_mod.load_profile(profile_name, {}, targets), REPO_ROOT, path
        )
    except target_mod.TargetError as exc:
        raise ValueError(str(exc)) from exc
    if not resolution.ok:
        raise ValueError(f"profile {profile_name!r} refused — " + "; ".join(resolution.reasons()))
    return Path(resolution.harness["runs_dir"])


def carried(item: Path) -> Iterator[Path]:
    """Every file one item carries: runtime residue is never among them."""
    files = [item] if item.is_file() else sorted(p for p in item.rglob("*") if p.is_file())
    for path in files:
        parts = path.relative_to(item).parts if not item.is_file() else (item.name,)
        if "__pycache__" in parts or any(part.endswith(".lock") for part in parts):
            continue
        yield path


def plan(source: Path) -> list[Path]:
    """The top-level items a migration carries: the state files and the archives."""
    items = [source / name for name in STATE_FILES if (source / name).is_file()]
    for pattern in ARCHIVE_GLOBS:
        items += sorted(path for path in source.glob(pattern) if path.is_dir())
    return items


def copy_item(item: Path, dest: Path) -> int:
    """Copy one item under ``dest`` and return how many files it carried."""
    target = dest / item.name
    count = sum(1 for _ in carried(item))
    if item.is_dir():
        shutil.copytree(item, target, ignore=shutil.ignore_patterns(*SKIP), dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="import-runs", description=(__doc__ or "").splitlines()[0]
    )
    parser.add_argument("--from", dest="source", required=True, metavar="PATH",
                        help="an external runs directory (read only)")
    parser.add_argument("--profile", default="example", metavar="NAME",
                        help="declared profile whose runs_dir is the destination (default: example)")
    parser.add_argument("--to", dest="dest", default=None, metavar="PATH",
                        help="destination override (default: the profile's runs_dir)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be copied; write nothing")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing state.json in the destination")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    try:
        dest = Path(args.dest).expanduser().resolve() if args.dest else default_to(args.profile)
    except (OSError, ValueError) as exc:
        print(f"import-runs: {exc}", file=sys.stderr)
        return 2
    if not source.is_dir():
        print(f"import-runs: no runs directory at {source}", file=sys.stderr)
        return 2
    if source == dest:
        print(f"import-runs: {source} is already the destination", file=sys.stderr)
        return 2
    items = plan(source)
    if not items:
        print(f"import-runs: {source} holds no state.json, scoreboard.md or archive")
        return 2
    state = dest / "state.json"
    if state.exists() and not args.force:
        print(
            f"import-runs: {state} already exists — pass --force to overwrite it "
            "(nothing was copied)",
            file=sys.stderr,
        )
        return 1

    verb = "would copy" if args.dry_run else "copied"
    total = 0
    for item in items:
        files = sum(1 for _ in carried(item))
        total += files
        print(f"  {verb} {item.name}{'/' if item.is_dir() else ''} ({files} file(s))")
        if not args.dry_run:
            copy_item(item, dest)
    where = f"into {dest}" if args.dry_run else str(dest)
    print(f"import-runs: {total} file(s) from {source} {where}")
    if not args.dry_run and state.is_file():
        data = json.loads(state.read_text(encoding="utf-8"))
        print(
            f"import-runs: state reads season {data.get('season')} "
            f"round {data.get('round')}"
        )
    return 0

if __name__ == "__main__":
    sys.exit(main())
