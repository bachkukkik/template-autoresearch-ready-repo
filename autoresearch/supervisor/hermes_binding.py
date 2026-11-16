#!/usr/bin/env python3
"""The one scheduler binding this repo ships: Hermes cron, plus its WebUI session API.

Everything a scheduler dictates lives here — the ``cron list`` text parser, the
``cron create|edit|pause|resume`` argv, where a profile home sits, which file proves
a directory is a profile, and the loopback call that starts a session. The installer
and the controller read the interface below and know nothing about it; the launcher
knows the module's documented filename and the names it calls, and nothing else. So a
second scheduler is one module, not an edit to three.

The interface (``hermes_binding`` is the reference implementation of all of it). Fifteen
names; a second binding must implement every one:

``NAME``
    The binding's name, as ``--binding`` takes it.
``ROOT_ENV``
    Two env var names, most explicit first. The first is a root; the second is a
    scope home, whose root is derived by ``root_from_home``.
``BIN_ENV`` / ``PROFILE_ENV``
    Env names for the scheduler executable and the default profile.
``URL_ENV``
    The env name a launcher may read the session API's base URL from, when the
    config does not carry one. The launcher never spells it itself.
``root_from_home(value) -> Path``
    The root a scope-home env value implies: its parent's parent when that parent is
    the profiles directory, else the value itself.
``profile_home(root, profile) -> Path``
    Where one profile lives under a resolved root.
``is_profile(home) -> bool``
    The gate: does this directory carry the scheduler's own profile marker? A
    directory without it is refused before anything is written or called.
``cli_env(root) -> dict``
    The child environment, with the resolved root pinned so files and jobs cannot
    land in two different roots.
``list_jobs(binary, profile, root) -> (jobs, error)``
    The scheduler's own listing, parsed. ``error`` is set — never an empty match
    list — when the listing cannot be read, because create-versus-edit must not be
    guessed.
``job_argv(binary, profile, recipe, job_id) -> list[str]``
    The create (``job_id`` None) or edit command.
``state_argv(binary, profile, verb, job_id) -> list[str]``
    The pause or resume command.
``sessions(url, profile) -> list[dict]``
    The sessions the launcher's busy check reads.
``fire(url, profile, repo, prompt) -> str``
    Start one session with the rendered prompt; returns its id.
``read_hint(home, name) -> str|None``
    A read-only hint from the scheduler's state file, used as a cross-check only.

The sixteenth requirement is a filename, not a name: the launcher resolves the module
as ``autoresearch/supervisor/<NAME>_binding.py``, so a second scheduler ships
``<name>_binding.py`` beside ``guards.py`` and the launcher finds it with no edit —
``install.py``'s ``BINDINGS`` entry is what the installer and controller use.

A job is a dict with ``id``, ``state``, ``name``, ``schedule``, ``script``,
``next_run``. A second binding must implement those fifteen names and ship that
filename, and pass the installer, controller and launcher suites unchanged; no caller
imports this module for anything else.

Nothing here holds a credential. The WebUI URL is read from configuration and the
session calls are loopback with auth off; a deployment behind a gateway needs its
own binding, not a token smuggled into a recipe.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

NAME = "hermes"
ROOT_ENV = ("HERMES_ROOT", "HERMES_HOME")
BIN_ENV = "HERMES_BIN"
PROFILE_ENV = "HERMES_PROFILE"
#: The launcher's one session-API env name; it asks this module rather than spelling it.
URL_ENV = "HERMES_WEBUI_URL"
#: The directory name that marks a scope home as a *profile* home under a root.
PROFILES_DIR = "profiles"
#: How long the listing, a mutation and one HTTP call may take.
LIST_TIMEOUT = 60
ACTION_TIMEOUT = 60
HTTP_TIMEOUT = 30

_JOB_HEADER = re.compile(r"^\s+([0-9A-Za-z]+)\s+\[([a-z]+)\]\s*$")
_JOB_NAME = re.compile(r"^\s+Name:\s+(.+?)\s*$")
_JOB_FIELDS = {
    "schedule": re.compile(r"^\s+Schedule:\s+(.+?)\s*$"),
    "script": re.compile(r"^\s+Script:\s+(.+?)\s*$"),
    "next_run": re.compile(r"^\s+Next run:\s+(.+?)\s*$"),
}


def root_from_home(value):
    """The root a scope-home env value implies: its parent's parent when it is a profile."""
    home = Path(value).expanduser()
    return home.parent.parent if home.parent.name == PROFILES_DIR else home


def profile_home(root, profile):
    """``<root>/profiles/<profile>``, or ``<root>`` for the default profile."""
    base = Path(root)
    return base if profile == "default" else base / PROFILES_DIR / profile


def is_profile(home):
    """A profile home exists only when it carries ``config.yaml``; never mkdir one."""
    return (Path(home) / "config.yaml").is_file()


def cli_env(root):
    """The child environment with the resolved root pinned into the scheduler's own name."""
    return {**os.environ, ROOT_ENV[1]: str(root)}


def parse_jobs(text):
    """``cron list --all`` -> one dict per job, in listing order. Pure.

    A job header is ``  <id> [state]``; the fields below it are indented ``Key:``
    lines. A job with no ``Name:`` cannot be found by name, so it is skipped.
    """
    jobs, current = [], None
    for line in (text or "").splitlines():
        header = _JOB_HEADER.match(line)
        if header:
            if current and current["name"]:
                jobs.append(current)
            current = {"id": header.group(1), "state": header.group(2), "name": None,
                       "schedule": None, "script": None, "next_run": None}
            continue
        if current is None:
            continue
        name = _JOB_NAME.match(line)
        if name:
            if current["name"] is None:
                current["name"] = name.group(1)
            continue
        for key, pattern in _JOB_FIELDS.items():
            found = pattern.match(line)
            if found and current[key] is None:
                current[key] = found.group(1)
                break
    if current and current["name"]:
        jobs.append(current)
    return jobs


def parse_list(text):
    """``cron list --all`` -> ``[(id, name), ...]``. Pure."""
    return [(job["id"], job["name"]) for job in parse_jobs(text)]


def list_text(binary, profile, root):
    """``(stdout, None)`` from the scheduler's listing, or ``(None, error)``."""
    argv = [binary, "-p", profile, "cron", "list", "--all"]
    try:
        done = subprocess.run(argv, timeout=LIST_TIMEOUT, check=True, capture_output=True,
                              text=True, env=cli_env(root))
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or "").strip().splitlines()
        return None, (f"{' '.join(argv)} failed (exit {exc.returncode}): "
                      f"{tail[-1] if tail else 'no stderr'}")
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{' '.join(argv)} failed: {exc}"
    return done.stdout, None


def list_jobs(binary, profile, root):
    """``(jobs, None)`` from the listing, or ``([], error)`` — never an empty match list."""
    text, error = list_text(binary, profile, root)
    if error:
        return [], error
    return parse_jobs(text), None


def job_argv(binary, profile, recipe, job_id=None):
    """The create (``job_id`` None) or edit command for this recipe. Pure."""
    argv = [binary, "-p", profile, "cron", "create" if job_id is None else "edit"]
    if job_id is not None:
        argv.append(job_id)
    else:
        argv += ["--name", recipe["name"]]
    argv += ["--schedule", recipe["schedule"], "--script", recipe["script"],
             "--deliver", recipe.get("deliver", "local"),
             "--timezone", recipe.get("timezone", "UTC")]
    if recipe.get("no_agent"):
        argv.append("--no-agent")
    return argv


def state_argv(binary, profile, verb, job_id):
    """The pause or resume command. Pure."""
    return [binary, "-p", profile, "cron", verb, job_id]


def read_hint(home, name):
    """The job id the profile's ``cron/jobs.json`` names, or None. Read-only, never decides."""
    path = Path(home) / "cron" / "jobs.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    for job in jobs if isinstance(jobs, list) else []:
        if isinstance(job, dict) and job.get("name") == name:
            return job.get("id")
    return None


def _call(path, body=None, base=None, profile=None):
    """One loopback WebUI call with the profile cookie; returns the parsed body."""
    headers = {"Content-Type": "application/json", "Cookie": f"hermes_profile={profile}"}
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers,
                                     method="GET" if body is None else "POST")
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read() or b"{}")


def sessions(url, profile):
    """The scheduler's session list. Raises; the launcher turns a raise into a skip."""
    return _call("/api/sessions", base=url, profile=profile).get("sessions", [])


def fire(url, profile, repo, prompt):
    """Start one session in ``repo`` with the prompt; returns its session id."""
    session = _call("/api/session/new", {"profile": profile, "workspace": str(repo),
                                         "worktree": False}, base=url, profile=profile)["session"]
    sid = session["session_id"]
    _call("/api/chat/start", {"session_id": sid, "message": prompt}, base=url, profile=profile)
    return sid
