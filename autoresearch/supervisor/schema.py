#!/usr/bin/env python3
"""The ``recipe.json`` schema — one field list, one validator, no per-recipe parser.

A recipe is a directory that carries everything a scheduler needs: the job
definition (``recipe.json``), the operator knobs (``config.example.json``) and the
files the job runs. The schema is deliberately small — a scheduler job needs a name,
a schedule, a script and the files to install — and every optional key has a default
the installer applies, so an adopter writing a second recipe copies one file.

Validation returns every problem at once, never the first: a hand-edited recipe is
then fixed in one pass instead of one error per install attempt.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Keys a recipe must declare, with the shape each one takes.
REQUIRED = {
    "name": "the job name the scheduler is asked for, and the name status/pause/resume look up",
    "schedule": "the scheduler's own schedule token; an interval ('every 60m') travels better than a cron expression",
    "script": "the installed filename of the entry script, inside the profile's scripts directory",
    "files": "source filename -> installed filename, every path relative to the recipe directory",
}
#: Keys a recipe may declare; the installer's default is written beside each.
OPTIONAL = {
    "no_agent": "false — true asks the scheduler to run the script without an agent turn",
    "deliver": "local — where the scheduler sends the script's output",
    "timezone": "UTC — the zone the schedule is read in",
    "config_renames": "{} — retired config key -> its replacement, folded before the merge",
    "note": "empty — one line for the operator, printed by --dry-run",
}
#: The schema itself, for the README and the test that keeps the two in step.
SCHEMA = {**REQUIRED, **OPTIONAL}


def _problems_of_string(recipe, key, problems):
    value = recipe.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{key!r} must be a non-empty string, got {value!r}")
        return False
    return True


def validate(recipe, recipe_dir=None):
    """Every problem with one recipe, in one list. Pure when ``recipe_dir`` is None."""
    problems = []
    if not isinstance(recipe, dict):
        return [f"recipe.json must be an object, got {type(recipe).__name__}"]
    for key in ("name", "schedule", "script"):
        _problems_of_string(recipe, key, problems)

    files = recipe.get("files")
    if files is not None and not isinstance(files, dict):
        problems.append(f"'files' must map source names to installed names, got {files!r}")
    elif isinstance(files, dict):
        if not files:
            problems.append("'files' is empty — a recipe installs at least its script")
        for source, installed in files.items():
            if not isinstance(source, str) or not isinstance(installed, str):
                problems.append(f"'files' entry {source!r}: {installed!r} is not a name pair")
            elif not installed.strip() or Path(installed).name != installed:
                problems.append(f"'files' entry {source!r} -> {installed!r} is not a bare filename")
        script = recipe.get("script")
        if isinstance(script, str) and script and script not in set(files.values()):
            problems.append(f"'script' {script!r} is not one of the installed 'files'")

    renames = recipe.get("config_renames")
    if renames is not None and not isinstance(renames, dict):
        problems.append(f"'config_renames' must be an object, got {renames!r}")
    elif isinstance(renames, dict):
        for old, new in renames.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                problems.append(f"'config_renames' entry {old!r} -> {new!r} is not a name pair")

    for key in ("no_agent",):
        if key in recipe and not isinstance(recipe[key], bool):
            problems.append(f"{key!r} must be true or false, got {recipe[key]!r}")

    if recipe_dir is not None and isinstance(files, dict):
        base = Path(recipe_dir)
        for source in files:
            if isinstance(source, str) and not (base / source).is_file():
                problems.append(f"'files' names {source!r} but {base / source} does not exist")
    return problems


def load(path):
    """``(recipe, problems)`` from a ``recipe.json`` path; a parse error is one problem."""
    try:
        return json.loads(Path(path).read_text()), []
    except OSError as exc:
        return None, [f"cannot read {path}: {exc}"]
    except ValueError as exc:
        return None, [f"{path} is not JSON: {exc}"]
