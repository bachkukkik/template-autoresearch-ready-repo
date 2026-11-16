#!/usr/bin/env python3
"""Fire one unattended autoresearch session with a prompt rendered from repo state.

Installed by this directory's ``install.sh`` as ``autoresearch-overnight-launch.py``
in ``<profile>/scripts/`` and run by the ``autoresearch-overnight`` job. Each tick,
in this order — the order is the contract:

1. ``--dry-run`` renders the prompt and returns before every guard (it starts
   nothing, so it can duplicate nothing);
2. outside ``[start, end)`` in the configured zone the tick ends with no output and
   no log line — a daylight tick has nothing to supervise;
3. an unreadable session API logs ``api-error`` and fires nothing;
4. a session still working (streaming, or touched inside the idle floor) skips;
5. a live round marker skips — the run writes it, so a detached run that outlives
   its session is visible here; the process scan is the second, independent signal;
6. otherwise one session is started with the rendered prompt, and its id recorded.

The prompt is rendered from tracked repo state, never from constants: the active leg
of the objective record, the engine's own ``status`` and ``doctor`` output, the
command catalog it advertises, the last close record's verdict, and the
adopter-supplied charter. Every probe degrades to a labelled string and never
raises; a prompt that lies about the repo or names a command that does not exist
sends a session to the wrong place.

Machine values are configuration, not code: ``load_config`` reads
``<this file's stem>.config.json`` beside this file (the installed name), falling
back to ``config.json`` beside it (the repo layout), merged over ``DEFAULTS``.

The WebUI URL is configuration, or the environment variable the *binding* names
(``URL_ENV``) — this file spells no scheduler's env name, and the URL is never
written into code.

The guard helpers and the scheduler binding are read from the repo's
``autoresearch/supervisor/`` at fire time, so a guard fix reaches a profile without
a reinstall. A repo without them is a skip, not a fire: an unguarded launcher must
not start a session.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
STATE_NAME = "autoresearch-overnight-state.json"
LOG_NAME = "autoresearch-overnight.log"

#: Every machine value this launcher reads; a config file overrides them one by one.
#: ``webui_url`` is deliberately absent: it comes from the config, or from the env var
#: the binding names. ``max_wall_seconds`` is derived from ``max_wall_minutes`` at render
#: time, so the prompt and the config cannot drift by a factor of sixty.
DEFAULTS = {
    "profile": "default",
    "repo": ".",
    "engine": "autoresearch/engine/bin/autoresearch",
    "binding": "hermes",
    "target_profile": "example",
    "idle_minutes": 10,
    "overnight_start_hour": 0,
    "overnight_end_hour": 7,
    "timezone": "UTC",
    "state_dir": ".autoresearch",
    "max_iterations": 5,
    "max_wall_minutes": 45,
}

UNAVAILABLE = "(unavailable — read it yourself from the repo)"
NO_RUN = "(no initialised run — `init` creates one under the configured state directory)"
NO_RECORD = "(no close record yet — `report --record` writes one at the end of a run)"
PROBE_TIMEOUT = 60


class HelpersUnavailable(RuntimeError):
    """The repo does not carry the guard helpers this launcher needs."""


def _load(name, path):
    """Load a module by absolute path, under a name of its own. No package needed."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise HelpersUnavailable(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helpers(repo, binding="hermes"):
    """``(guards, binding)`` from the repo's ``autoresearch/supervisor/``."""
    base = Path(repo) / "autoresearch" / "supervisor"
    guards_path = base / "guards.py"
    binding_path = base / f"{binding}_binding.py"
    for path in (guards_path, binding_path):
        if not path.is_file():
            raise HelpersUnavailable(f"{path} is missing — no guard, no fire")
    return _load("overnight_guards", guards_path), _load(f"overnight_binding_{binding}", binding_path)


def merge_config(file_data=None, defaults=None):
    """DEFAULTS <- config file, as one dict. Pure.

    The environment is not merged here: the one env value this launcher reads is the
    WebUI URL, and its variable name belongs to the binding (``URL_ENV``), which is not
    loaded yet when a ``--dry-run`` reads its config.
    """
    cfg = dict(DEFAULTS if defaults is None else defaults)
    if file_data:
        cfg.update(file_data)
    return cfg


def workdir(script=None):
    """The directory this launcher lives in: beside the installed copy, or its recipe dir."""
    return Path(__file__).resolve().parent if script is None else Path(script).resolve().parent


def prefix(script=None):
    """The recipe prefix of this file: its stem minus a trailing ``-launch``. Pure."""
    stem = Path(__file__).resolve().stem if script is None else Path(script).stem
    return stem[:-7] if stem.endswith("-launch") else stem


def beside(name, script=None, prefix_name=None):
    """``<dir>/<name>`` or ``<dir>/<prefix>-<prefix_name>`` beside the script, else None."""
    script = Path(__file__).resolve() if script is None else Path(script)
    names = [name]
    if prefix_name:
        names.insert(0, f"{prefix(script)}-{prefix_name}")
    for candidate in (script.parent / n for n in names):
        if candidate.is_file():
            return candidate
    return None


def template_path(script=None):
    """The prompt template beside this file: repo layout first, installed name second."""
    return beside("prompt.tmpl.txt", script, "prompt.tmpl.txt")


def config_path(script=None):
    """``<stem>.config.json`` beside ``script``, else ``config.json``, else None. Pure."""
    script = Path(__file__).resolve() if script is None else Path(script)
    for name in (f"{script.stem}.config.json", "config.json"):
        candidate = script.parent / name
        if candidate.is_file():
            return candidate
    return None


def load_config(script=None):
    """``merge_config`` over the config file beside ``script`` (defaults when there is none)."""
    path = config_path(script)
    data = json.loads(path.read_text()) if path else None
    return merge_config(data)


def engine_path(cfg, repo):
    """The engine wrapper as an absolute path: a relative ``engine`` resolves against the repo."""
    engine = Path(cfg["engine"]).expanduser()
    return str(engine if engine.is_absolute() else Path(repo) / engine)


def state_path(cfg, repo):
    """The run's state directory: a relative ``state_dir`` resolves against the repo."""
    state = Path(cfg["state_dir"]).expanduser()
    return state if state.is_absolute() else Path(repo) / state


def _run(argv, repo=None, timeout=PROBE_TIMEOUT):
    """``(code, stdout, stderr)`` from one bounded child, or ``(None, '', reason)``."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              cwd=None if repo is None else str(repo))
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "", f"{type(exc).__name__}: {' '.join(str(a) for a in argv[1:])}"
    return done.returncode, done.stdout or "", done.stderr or ""


def _tail(text, lines=1):
    found = [line for line in (text or "").strip().splitlines() if line.strip()]
    return found[-1] if found else ""


def objective_line(text):
    """The active objective's first priced leg, as one line. Pure; never raises."""
    try:
        data = json.loads(text or "")
    except (TypeError, ValueError) as exc:
        return f"(unavailable — objective record did not parse: {type(exc).__name__})"
    objectives = data.get("objectives", []) if isinstance(data, dict) else []
    active = [o for o in objectives if isinstance(o, dict) and o.get("status") == "active"]
    if not active:
        return "(unavailable — the objective record declares no active objective)"
    chosen = active[0]
    rotation = chosen.get("rotation") if isinstance(chosen.get("rotation"), list) else []
    legs = [leg for leg in chosen.get("legs", []) if isinstance(leg, dict)]
    leg = next((l for l in legs if rotation and l.get("name") == rotation[0]), None)
    if leg is None:
        leg = next((l for l in legs if (chosen.get("weights") or {}).get(l.get("name"))), None)
    if leg is None:
        leg = legs[0] if legs else None
    if leg is None:
        return f"{chosen.get('id', '?')} (active): no leg priced"
    direction = "lower" if leg.get("direction") == "lower" else "higher"
    return (f"{chosen.get('id', '?')} (active): leg {leg.get('name', '?')} — {direction} is "
            f"better, unit {leg.get('unit', '?')}, command '{leg.get('command', '?')}', "
            f"repeats {leg.get('repeats', '?')}, noise floor {leg.get('noise_floor', '?')}, "
            f"guard '{leg.get('guard') or '(none)'}'")


def engine_status(repo, engine, state):
    """The engine's own ``status`` answer, first lines only; degrade to one labelled string."""
    code, out, err = _run([engine, "status", "--repo", str(repo), "--state-dir", str(state)])
    if code is None:
        return f"(unavailable — {err})"
    lines = [line for line in out.strip().splitlines() if line.strip()]
    if code != 0 or not lines:
        tail = _tail(err) or f"exit {code}"
        if code == 2:
            return f"{NO_RUN} (status said: {tail})"
        return f"(unavailable — `status` exited {code}: {tail})"
    return "\n".join(lines[:8])


def engine_doctor(repo, engine):
    """The engine's ``doctor`` output, first lines only; degrade to one labelled string."""
    code, out, err = _run([engine, "doctor"], repo=repo)
    if code is None:
        return f"(unavailable — {err})"
    lines = [line for line in out.strip().splitlines() if line.strip()]
    if code != 0 or not lines:
        return f"(unavailable — `doctor` exited {code}: {_tail(err)})"
    return "\n".join(lines[:8])


def catalog(repo, engine):
    """The subcommands the engine advertises in its own help, or a labelled reason."""
    code, out, err = _run([engine, "--help"], repo=repo)
    if code is None or code != 0:
        return f"(unavailable — `--help` failed: {_tail(err) or code})"
    for token in out.split():
        if token.startswith("{") and token.endswith("}") and "," in token:
            return ", ".join(part for part in token.strip("{}").split(",") if part)
    return UNAVAILABLE


def last_record(repo, state):
    """The last close record's verdict, as one line. Pure read; never raises."""
    path = Path(state) / "record.json"
    if not path.is_file():
        return NO_RECORD
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return f"(unavailable — {path.name} is unreadable: {type(exc).__name__})"
    if not isinstance(data, dict):
        return f"(unavailable — {path.name} is not an object)"
    verdict = data.get("verdict", "?")
    readings = [r for r in data.get("readings", []) if isinstance(r, dict)]
    if not readings:
        return f"verdict {verdict} (no reading recorded)"
    first = readings[0]
    return (f"verdict {verdict} — leg {first.get('name', '?')} "
            f"{first.get('before')} -> {first.get('after')} {first.get('unit', '')}".rstrip())


def charter_text(script=None):
    """The adopter-supplied charter, or a clearly marked placeholder naming the file."""
    script = Path(__file__).resolve() if script is None else Path(script)
    found = beside("charter.md", script, "charter.md")
    if found is not None:
        try:
            return found.read_text().strip()
        except OSError:
            pass
    wanted = script.parent / f"{prefix(script)}-charter.md"
    return (f"[ADOPTER-SUPPLIED — no charter at {wanted}. Write one paragraph: what this "
            f"repo should become, what 'better' means here, and what must not change.]")


def wall_seconds(cfg):
    """``max_wall_minutes`` as the seconds the engine's ``--max-wall`` takes. Pure, never raises."""
    try:
        return int(float(cfg["max_wall_minutes"]) * 60)
    except (KeyError, TypeError, ValueError):
        return "unavailable — max_wall_minutes is not a number"


def gather_context(cfg, repo, engine, script=None):
    """Every prompt value, from tracked repo state. Never raises: a dead probe is a string."""
    repo = Path(repo)
    state = state_path(cfg, repo)
    ctx = {
        "repo": str(repo),
        "engine": engine,
        "target_profile": cfg["target_profile"],
        "state_dir": str(state),
        "max_iterations": cfg["max_iterations"],
        "max_wall_minutes": cfg["max_wall_minutes"],
        "max_wall_seconds": wall_seconds(cfg),
        "fired_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "objective_line": UNAVAILABLE,
        "engine_status": NO_RUN,
        "engine_doctor": UNAVAILABLE,
        "last_record": NO_RECORD,
        "catalog": UNAVAILABLE,
        "charter": charter_text(script),
    }
    try:
        registry = (repo / "autoresearch" / "objective" / "registry.json").read_text()
        ctx["objective_line"] = objective_line(registry)
    except OSError as exc:
        ctx["objective_line"] = f"(unavailable — objective record: {type(exc).__name__})"
    ctx["engine_status"] = engine_status(repo, engine, state)
    ctx["engine_doctor"] = engine_doctor(repo, engine)
    ctx["last_record"] = last_record(repo, state)
    ctx["catalog"] = catalog(repo, engine)
    return ctx


def render(ctx, template_text=None, template_file=None):
    """Fill the template from ``ctx``. Pure when ``template_text`` is supplied."""
    if template_text is None:
        path = template_path() if template_file is None else Path(template_file)
        if path is None:
            return "overnight prompt: no prompt.tmpl.txt beside " + str(HERE)
        template_text = path.read_text()
    return Template(template_text).safe_substitute(ctx)


def build_parser():
    parser = argparse.ArgumentParser(description="One unattended autoresearch tick.")
    parser.add_argument("--dry-run", action="store_true",
                        help="render the prompt and print it; touch no API, no state, no guard")
    parser.add_argument("--force", action="store_true",
                        help="skip only the window guard, for a manual out-of-hours fire")
    return parser


def main(argv=None, script=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(script)
    base = workdir(script)
    state_file = base / STATE_NAME
    log_file = base / LOG_NAME
    repo = Path(cfg["repo"]).expanduser().resolve()
    engine = engine_path(cfg, repo)

    if args.dry_run:
        print(render(gather_context(cfg, repo, engine, script)))
        return 0

    try:
        guard_mod, binding = helpers(repo, cfg["binding"])
    except HelpersUnavailable as exc:
        # No guard helpers means no ladder: skip, and leave the reason where a scheduler
        # that drops stderr will still show it.
        print(f"overnight: {exc}", file=sys.stderr)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        try:
            with log_file.open("a") as handle:
                handle.write(f"{stamp}: skip, helpers unavailable — {exc}\n")
        except OSError:
            pass
        return 0

    if not args.force and not guard_mod.in_window(
            start=cfg["overnight_start_hour"], end=cfg["overnight_end_hour"],
            tz_name=cfg["timezone"]):
        return 0

    url = cfg.get("webui_url") or os.environ.get(binding.URL_ENV, "")
    if not url:
        guard_mod.log_skip(log_file, f"webui_url unset — set it in the config or {binding.URL_ENV}")
        return 0

    try:
        sessions = binding.sessions(url, cfg["profile"])
    except Exception as exc:  # noqa: BLE001 — an unreadable API must never become a duplicate
        guard_mod.log_skip(log_file, f"api-error {type(exc).__name__} — not firing blind", 0)
        return 0

    working = guard_mod.busy_session(sessions, idle_minutes=cfg["idle_minutes"],
                                     profile=cfg["profile"])
    if working:
        guard_mod.log_skip(log_file, f"{working} is live — no fire", len(sessions))
        return 0

    blocking, reason = guard_mod.marker_state(
        guard_mod.marker_path(cfg["state_dir"], repo))
    if blocking:
        guard_mod.log_skip(log_file, f"a run is in play — no fire: {reason}", len(sessions))
        return 0

    playing = guard_mod.live_process()
    if playing:
        guard_mod.log_skip(log_file, f"a run is in play — no fire: {playing[:70]}", len(sessions))
        return 0

    prompt = render(gather_context(cfg, repo, engine, script))
    previous = None
    if state_file.is_file():
        try:
            previous = json.loads(state_file.read_text()).get("session_id")
        except (OSError, ValueError):
            previous = None
    sid = binding.fire(url, cfg["profile"], repo, prompt)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        state_file.write_text(json.dumps({"session_id": sid, "fired_at": now,
                                          "previous": previous}, indent=1) + "\n")
    except OSError as exc:
        # The session has already started; a read-only scripts dir must not turn that
        # into a non-zero tick. The next tick simply has no "previous" to report, so the
        # miss is logged best-effort — the same rule log_skip follows for its own write.
        try:
            with log_file.open("a") as handle:
                handle.write(f"{now}: fired {sid} but the state file is unwritable "
                             f"({type(exc).__name__}) — previous session unknown\n")
        except OSError:
            pass
    print(f"{now}: fired autoresearch session {sid} (profile {cfg['profile']}, "
          f"previous {previous or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
