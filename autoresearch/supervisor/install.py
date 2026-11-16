#!/usr/bin/env python3
"""Install one unattended-loop recipe into a scheduler profile (idempotent).

A recipe is a directory carrying ``recipe.json`` (name, schedule, installed script
name, delivery, timezone and the ``files`` map), an optional
``config.example.json``, and the files themselves. This script copies those files
into ``<profile>/scripts/``, writes the recipe's config beside them, and then
creates or edits the job of that name — a second run is an edit, never a second job.

Stdlib only. Every child process runs from a list argv under a timeout, never a
shell. ``--dry-run`` prints the whole plan and writes nothing: no copy, no config,
no job command. State and log files are never written by this script.

The root never comes from ``$HOME``: inside a scheduler-spawned process ``$HOME`` is
a per-profile home, so a plausible empty tree passes an existence check and reads as
"no jobs" — the measured cause of a duplicate job downstream. Resolution is
``--root`` -> the binding's explicit root env -> its scope-home env -> the current
directory, the source is printed, and a directory without the scheduler's profile
marker is refused before anything is written or called.

The installer itself names no scheduler: every scheduler-shaped decision — the listing,
the create/edit argv, the profile layout, the profile marker — is a call on the binding
module it is handed. ``hermes_binding`` is the shipped binding and carries the
interface (fifteen names, plus the ``<binding>_binding.py`` filename convention) in its
docstring; a second scheduler is a second module of that shape plus one ``BINDINGS``
entry. The launcher reads its session URL from the config, or from the env var the
binding names: the env spelling lives in the binding module, never in a caller.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 120
HERE = Path(__file__).resolve().parent


def _load(name, path):
    """Load a sibling module by absolute path, under a name of its own. No package needed."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = _load("supervisor_schema", HERE / "schema.py")
#: One entry per scheduler; the shipped one is Hermes cron.
BINDINGS = {"hermes": lambda: _load("supervisor_binding_hermes", HERE / "hermes_binding.py")}


def load_binding(name):
    """The binding module ``--binding`` names, or a clear error."""
    loader = BINDINGS.get(name)
    if loader is None:
        raise SystemExit(f"install: unknown binding {name!r} (have: {', '.join(sorted(BINDINGS))})")
    return loader()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Install one unattended-loop recipe into a scheduler profile (idempotent).")
    parser.add_argument("recipe_dir", help="the recipe directory (holds recipe.json)")
    parser.add_argument("--profile", default=None,
                        help="profile name (default: the binding's profile env, else 'default')")
    parser.add_argument("--root", "--scheduler-root", dest="root", default=None,
                        help="scheduler root (default: the binding's root env, else its "
                             "scope-home env, else the current directory — never $HOME)")
    parser.add_argument("--bin", dest="binary", default=None,
                        help="the scheduler executable (default: the binding's bin env, else its name)")
    parser.add_argument("--binding", default="hermes", help="which scheduler binding to use")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override one config value, repeatable; written to the installed config")
    parser.add_argument("--dry-run", action="store_true",
                        help="print every planned copy, write and command; perform none")
    return parser


def _account_home():
    """The account's real home from the password database — ``$HOME`` is unreliable here."""
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError):
        return Path("~").expanduser()


def _expand(value):
    """Expand a leading ``~`` against the account home, not ``$HOME``."""
    text = str(value)
    if text == "~":
        return _account_home()
    if text.startswith("~/"):
        return _account_home() / text[2:]
    return Path(text)


def resolve_root(binding, arg=None, env=None, cwd=None):
    """``(root, source)``: --root -> explicit env -> scope-home env -> the current directory.

    The scope-home env value is a *profile* home when its parent is the binding's
    profiles directory, so its root is the parent's parent. ``$HOME`` is never read:
    in a scheduler-spawned process it points at ``<root>/profiles/<p>/home``.
    """
    env = os.environ if env is None else env
    if arg:
        return _expand(arg), "--root"
    explicit, scope_home = binding.ROOT_ENV
    if env.get(explicit):
        return _expand(env[explicit]), explicit
    if env.get(scope_home):
        return binding.root_from_home(_expand(env[scope_home])), scope_home
    return Path(cwd or os.getcwd()), "cwd"


def parse_sets(pairs):
    """``['k=v', ...]`` -> ``{'k': v}``. A pair without '=' is a usage error."""
    overrides = {}
    for pair in pairs or []:
        key, sep, value = str(pair).partition("=")
        if not sep or not key:
            raise ValueError(f"--set needs KEY=VALUE, got {pair!r}")
        overrides[key] = _coerce(value)
    return overrides


def _coerce(value):
    """A --set value as JSON when it parses (ints, floats, booleans), else the raw string."""
    try:
        return json.loads(value)
    except ValueError:
        return value


def merge_config(example, installed, overrides):
    """``config.example.json`` <- the installed config (operator edits kept) <- ``--set``."""
    merged = dict(example or {})
    merged.update(installed or {})
    merged.update(overrides or {})
    return merged


def apply_renames(config, renames):
    """Fold a retired key into its replacement; the old name never lingers. Pure.

    An installed value under the old key moves only when the new key is absent — the
    new key always wins — and the old key is dropped either way: a stale name would
    otherwise look configured while the launcher reads only the new one.
    """
    moved = []
    for old, new in (renames or {}).items():
        if old not in config:
            continue
        value = config.pop(old)
        if new not in config:
            config[new] = value
        moved.append(f"{old} -> {new}")
    return moved


def jobs_named(binding, binary, profile, root, name):
    """``(matches, error)``: every listed job called ``name``, and why the list failed.

    The one lookup the installer and ``control.py`` share. A failed listing sets
    ``error`` — never an empty match list — so create, pause and resume cannot act
    blind, and a duplicate name is returned as the list it is so the caller refuses
    with both ids.
    """
    jobs, error = binding.list_jobs(binary, profile, root)
    if error:
        return [], error
    return [job for job in jobs if job.get("name") == name], None


def duplicate_message(count, name, ids):
    """The refusal both callers print when a recipe name is not unique."""
    return (f"{count} jobs are named {name!r} ({', '.join(ids)}) — "
            f"remove the duplicates first")


def run(recipe_dir, profile, root, binary, overrides, dry_run, binding, root_source="-"):
    """The install itself; returns the process exit code. Prints every step it takes."""
    recipe_dir = Path(recipe_dir).resolve()
    recipe, problems = schema.load(recipe_dir / "recipe.json")
    problems += schema.validate(recipe, recipe_dir) if recipe is not None else []
    if problems:
        for problem in problems:
            print(f"install: {problem}", file=sys.stderr)
        return 2
    if recipe is None:
        return 2
    files = recipe["files"]

    home = binding.profile_home(root, profile)
    print(f"install: root {root} (from {root_source})")
    if not binding.is_profile(home):
        print(f"install: {home} is not a profile of the {binding.NAME} scheduler "
              f"(no profile marker) — root {root} (from {root_source}); "
              f"check --profile / --root", file=sys.stderr)
        return 2

    scripts_dir = home / "scripts"
    config_path = scripts_dir / (Path(recipe["script"]).stem + ".config.json")
    example_path = recipe_dir / "config.example.json"
    installed = None
    if config_path.is_file():
        try:
            installed = json.loads(config_path.read_text())
        except (OSError, ValueError) as exc:
            print(f"install: cannot read the installed config {config_path}: {exc}",
                  file=sys.stderr)
            return 2
        if not isinstance(installed, dict):
            print(f"install: the installed config {config_path} is not a JSON object "
                  f"({type(installed).__name__}) — refusing to merge over it", file=sys.stderr)
            return 2
    example = None
    if example_path.is_file():
        try:
            example = json.loads(example_path.read_text())
        except (OSError, ValueError) as exc:
            print(f"install: cannot read the recipe's config example {example_path}: {exc}",
                  file=sys.stderr)
            return 2
        if not isinstance(example, dict):
            print(f"install: the recipe's config example {example_path} is not a JSON "
                  f"object ({type(example).__name__})", file=sys.stderr)
            return 2
    # The on-disk config is the comparison base: renames mutate `installed`, so comparing
    # against it would report "keep" and leave the retired key in the file.
    original = dict(installed) if installed is not None else None
    moved = apply_renames(installed, recipe.get("config_renames")) if installed else []
    config = merge_config(example, installed, overrides)

    matches, list_error = jobs_named(binding, binary, profile, root, recipe["name"])
    if list_error:
        print(f"install: {list_error} — refusing to guess create vs edit", file=sys.stderr)
        return 2
    if len(matches) > 1:
        ids = [job["id"] for job in matches]
        print(f"install: {duplicate_message(len(ids), recipe['name'], ids)}, "
              f"nothing was written", file=sys.stderr)
        return 2
    job_id = matches[0]["id"] if matches else None

    hinted = binding.read_hint(home, recipe["name"])
    if hinted and job_id is None:
        # Downstream's duplicate job, refused at the same seam: the state file says a job
        # of this name exists and the listing (which decides) cannot see it. Creating now
        # is exactly how a second job is minted beside a live one.
        print(f"install: the scheduler's state file under {home} names job {hinted} for "
              f"{recipe['name']!r}, but its listing shows no such job — refusing to create "
              f"a second one; compare the two with `control.py status`, reconcile the state "
              f"entry, and re-run", file=sys.stderr)
        return 2
    if hinted and job_id and hinted != job_id:
        print(f"install: the state file names job {hinted} but the listing shows {job_id}; "
              f"the listing decides")
    elif job_id and not hinted:
        print(f"install: warning: no state-file entry under {home} names {recipe['name']!r}; "
              f"using the listing's id {job_id}")

    verb = "create" if job_id is None else f"edit {job_id}"
    for move in moved:
        print(f"{'would rename' if dry_run else 'rename'}: {move} in {config_path}")
    for source, installed_name in files.items():
        print(f"{'would copy' if dry_run else 'copy'}: {source} -> {scripts_dir / installed_name}")
        if not dry_run:
            scripts_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipe_dir / source, scripts_dir / installed_name)

    if config:
        payload = json.dumps(config, indent=2, sort_keys=True) + "\n"
        if original is not None and config == original:
            print(f"keep: {config_path} (already current)")
        else:
            print(f"{'would write' if dry_run else 'write'}: {config_path}")
            if not dry_run:
                scripts_dir.mkdir(parents=True, exist_ok=True)
                config_path.write_text(payload)

    command = binding.job_argv(binary, profile, recipe, job_id)
    print(f"{'would run' if dry_run else 'run'}: {' '.join(command)}")
    if dry_run:
        print(f"summary: recipe {recipe['name']} ({verb}) -> {scripts_dir} "
              f"[dry-run, nothing written]")
        if recipe.get("note"):
            print(f"note: {recipe['note']}")
        return 0

    try:
        subprocess.run(command, timeout=TIMEOUT, check=True, env=binding.cli_env(root))
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or "").strip().splitlines()
        print(f"install: {' '.join(command)} failed (exit {exc.returncode}): "
              f"{tail[-1] if tail else 'no stderr'}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"install: {' '.join(command)} failed: {exc}", file=sys.stderr)
        return 1

    installed_script = scripts_dir / recipe["script"]
    if not installed_script.is_file():
        print(f"install: {installed_script} is missing after the install", file=sys.stderr)
        return 1
    verified, verify_error = jobs_named(binding, binary, profile, root, recipe["name"])
    if verify_error:
        print(f"install: {verify_error} — cannot verify the job", file=sys.stderr)
        return 1
    if len(verified) != 1:
        print(f"install: expected exactly one job named {recipe['name']!r} after the install, "
              f"the listing shows {len(verified)}", file=sys.stderr)
        return 1
    print(f"summary: recipe {recipe['name']} ({verb} -> job {verified[0]['id']}) "
          f"-> {scripts_dir} [installed, verified]")
    return 0


def main(argv=None, binding=None):
    args = build_parser().parse_args(argv)
    binding = load_binding(args.binding) if binding is None else binding
    profile = args.profile or os.environ.get(binding.PROFILE_ENV) or "default"
    binary = args.binary or os.environ.get(binding.BIN_ENV) or binding.NAME
    root, root_source = resolve_root(binding, args.root, os.environ, os.getcwd())
    try:
        overrides = parse_sets(args.set)
    except ValueError as exc:
        print(f"install: {exc}", file=sys.stderr)
        return 2
    return run(args.recipe_dir, profile, root, binary, overrides, args.dry_run, binding,
               root_source)


if __name__ == "__main__":
    sys.exit(main())
