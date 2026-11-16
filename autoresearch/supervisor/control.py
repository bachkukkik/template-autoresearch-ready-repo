#!/usr/bin/env python3
"""Inspect, pause and resume one recipe's job — the installer's other half.

``install.py`` puts a recipe into a profile; this module is the operator loop around
the job it created:

* ``status`` prints the job as the scheduler reports it (id, state, schedule,
  script, next run) — read-only, it only lists jobs;
* ``pause`` / ``resume`` issue the scheduler's pause or resume, then re-list, so a
  command that exits 0 without changing the state is a failure (1), not a success.

The job is found by the recipe's NAME through ``install.jobs_named`` — the same
lookup the installer uses, so install, status, pause and resume cannot disagree
about which job is the recipe's. No job, or two of that name, exits 2 with the ids
and a remedy; a listing that cannot be read is an error, never an empty result.

Install is not resume: installing a recipe whose job was paused leaves it paused,
and the runbook makes the operator say so explicitly. Stdlib only; every child is a
list argv under a timeout, never a shell, and the resolved root is pinned into it.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERBS = ("status", "pause", "resume")
#: The state a successful pause/resume must leave behind, in the scheduler's token.
WANTED_STATE = {"pause": "paused", "resume": "active"}
ACTION_TIMEOUT = 60
DEFAULT_RECIPE = HERE / "overnight"


def _load(name, path):
    """Load a sibling module by absolute path, under a name of its own. No package needed."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = _load("supervisor_install", HERE / "install.py")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="control.py",
        description="Print, pause or resume the job of one recipe (found by its name).")
    parser.add_argument("verb", choices=VERBS,
                        help="status prints the job; pause/resume change its state")
    parser.add_argument("recipe_dir", nargs="?", default=str(DEFAULT_RECIPE),
                        help="the recipe directory (holds recipe.json)")
    parser.add_argument("--profile", default=None, help="profile name")
    parser.add_argument("--root", "--scheduler-root", dest="root", default=None,
                        help="scheduler root (default: the binding's env, else the cwd)")
    parser.add_argument("--bin", dest="binary", default=None, help="the scheduler executable")
    parser.add_argument("--binding", default="hermes", help="which scheduler binding to use")
    return parser


def recipe_name(recipe_dir):
    """``(name, error)``: the job name a recipe declares, or why it cannot be read."""
    recipe_file = Path(recipe_dir) / "recipe.json"
    if not recipe_file.is_file():
        return None, f"no recipe.json in {recipe_dir}"
    try:
        recipe = json.loads(recipe_file.read_text())
    except (OSError, ValueError) as exc:
        return None, f"cannot read {recipe_file}: {exc}"
    name = recipe.get("name") if isinstance(recipe, dict) else None
    if not isinstance(name, str) or not name:
        return None, f"{recipe_file} names no job ('name')"
    return name, None


def render(job, profile):
    """The job as an operator reads it: one ``key: value`` line each."""
    rows = [("job", job.get("id")), ("name", job.get("name")), ("state", job.get("state")),
            ("schedule", job.get("schedule")), ("script", job.get("script")),
            ("next run", job.get("next_run")), ("profile", profile)]
    width = max(len(key) for key, _ in rows)
    return "\n".join(f"{(key + ':').ljust(width + 1)}  {value or '-'}" for key, value in rows)


def set_state(verb, job, binding, binary, profile, root):
    """Run the scheduler's ``pause``/``resume``, then re-list: 0 only if the state moved."""
    command = binding.state_argv(binary, profile, verb, job["id"])
    try:
        subprocess.run(command, timeout=ACTION_TIMEOUT, check=True, capture_output=True,
                       text=True, env=binding.cli_env(root))
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or "").strip().splitlines()
        print(f"control: {' '.join(command)} failed (exit {exc.returncode}): "
              f"{tail[-1] if tail else 'no stderr'}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"control: {' '.join(command)} failed: {exc}", file=sys.stderr)
        return 1

    after, error = install.jobs_named(binding, binary, profile, root, job["name"])
    if error:
        print(f"control: {verb} ran but the job list cannot be read: {error}", file=sys.stderr)
        return 1
    if len(after) != 1:
        print(f"control: {verb} ran but {job['name']!r} now matches {len(after)} jobs — "
              f"check the status verb", file=sys.stderr)
        return 1
    wanted = WANTED_STATE[verb]
    print(f"control: {verb} {after[0]['id']} -> {after[0]['state']}")
    if after[0]["state"] != wanted:
        print(f"control: {verb} exited 0 but the job reads {after[0]['state']!r}, "
              f"not {wanted!r}", file=sys.stderr)
        return 1
    return 0


def main(argv=None, binding=None):
    args = build_parser().parse_args(argv)
    binding = install.load_binding(args.binding) if binding is None else binding
    recipe_dir = Path(args.recipe_dir).resolve()
    name, error = recipe_name(recipe_dir)
    if error:
        print(f"control: {error}", file=sys.stderr)
        return 2

    profile = args.profile or os.environ.get(binding.PROFILE_ENV) or "default"
    binary = args.binary or os.environ.get(binding.BIN_ENV) or binding.NAME
    root, root_source = install.resolve_root(binding, args.root, os.environ, os.getcwd())
    home = binding.profile_home(root, profile)
    print(f"control: root {root} (from {root_source})")
    print(f"control: recipe {name} (from {recipe_dir})")
    if not binding.is_profile(home):
        print(f"control: {home} is not a profile of the {binding.NAME} scheduler "
              f"(no profile marker) — root {root} (from {root_source}); "
              f"check --profile / --root", file=sys.stderr)
        return 2

    matches, list_error = install.jobs_named(binding, binary, profile, root, name)
    if list_error:
        print(f"control: {list_error} — cannot read the job list", file=sys.stderr)
        return 2
    if not matches:
        print(f"control: no job named {name!r} in profile {profile!r} — "
              f"install it first", file=sys.stderr)
        return 2
    if len(matches) > 1:
        ids = [job["id"] for job in matches]
        print(f"control: {install.duplicate_message(len(ids), name, ids)}", file=sys.stderr)
        return 2

    job = matches[0]
    if args.verb == "status":
        print(render(job, profile))
        return 0
    return set_state(args.verb, job, binding, binary, profile, root)


if __name__ == "__main__":
    sys.exit(main())
