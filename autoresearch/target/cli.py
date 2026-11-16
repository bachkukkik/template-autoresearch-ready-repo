"""``autoresearch profile <name> [--repo PATH]`` — print the resolved engine plan.

Validation only: the command resolves a declared profile and the target checkout,
then prints the engine invocation those two imply. It never initialises a run and
never writes to the target, so it is safe to run before a round is funded.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import target as target_mod  # noqa: E402

EXIT_OK = 0
EXIT_CONFIG = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoresearch profile",
        description="Validate a declared target profile and print the engine plan (dry).",
    )
    parser.add_argument("name", help="a declared profile name under autoresearch/targets/")
    parser.add_argument("--repo", default=None,
                        help="the checkout measured (default: $AUTORESEARCH_TARGET_REPO or cwd)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="emit {name, profile, target, argv} instead of one command line")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        checkout = target_mod.resolve_target(args.repo)
        path = target_mod.profile_path(args.name)
        resolution = target_mod.apply_profile(
            target_mod.load_profile(args.name), checkout, path
        )
    except target_mod.TargetError as exc:
        print(f"autoresearch profile: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    if not resolution.ok:
        print(f"autoresearch profile: {path} refused", file=sys.stderr)
        for reason in resolution.reasons():
            print(f"  - {reason}", file=sys.stderr)
        return EXIT_CONFIG
    if args.json_output:
        print(json.dumps({
            "name": resolution.name,
            "profile": str(resolution.profile_path),
            "target": str(resolution.target),
            "argv": resolution.engine_argv(),
        }, sort_keys=True))
    else:
        print(shlex.join(resolution.engine_argv()))
    return EXIT_OK

if __name__ == "__main__":
    sys.exit(main())
