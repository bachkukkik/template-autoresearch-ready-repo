#!/usr/bin/env python3
"""The guard ladder for one unattended fire — pure where it can be, fail-closed everywhere.

Every guard answers one question: may this tick start a session? When a guard cannot
answer, the tick is skipped — a missed run costs one interval, a duplicate run writes
twice into one ledger. The ladder's order is part of the contract:

1. ``--dry-run`` returns before the first guard (it starts nothing, it can duplicate nothing);
2. outside ``[start, end)`` in the configured zone -> exit 0, no log line;
3. an unreadable session API -> log ``api-error`` and do not fire blind;
4. a session still working -> skip (streaming, or touched inside the idle floor);
5. a detached run -> skip, proved by the marker file the run itself writes.

This module carries no scheduler and no HTTP: the caller supplies the session list,
the clock and the process list, so every rule is a pure, testable function. The
scheduler binding lives in ``hermes_binding.py``; the launcher that orders the ladder
lives in the recipe directory.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

#: The env var a run may use to move its marker; the engine writes `<state_dir>/round.marker`.
MARKER_ENV = "AUTORESEARCH_ROUND_MARKER"
MARKER_NAME = "round.marker"
#: A marker older than this with a live pid is still blocking; the age is only reported.
MARKER_MAX_AGE_HOURS = 24.0
#: Seconds one `pgrep` scan may take before the scan counts as unreadable — an unreadable
#: scan is not a run, and the marker has already decided.
SCAN_TIMEOUT = 10


def in_window(now=None, start=0, end=7, tz_name="UTC"):
    """True inside ``[start, end)`` local hours in ``tz_name``. Pure.

    ``start == end`` is a full day; ``start > end`` wraps midnight, so ``22 -> 6`` is
    the six hours after ten at night. An unknown zone raises, because a window that
    silently falls back to UTC fires at the wrong hour rather than not at all.
    """
    moment = datetime.now(timezone.utc) if now is None else now
    local = moment.astimezone(ZoneInfo(tz_name))
    start, end = int(start), int(end)
    if start == end:
        return True
    if start < end:
        return start <= local.hour < end
    return local.hour >= start or local.hour < end


def busy_session(sessions, now=None, idle_minutes=10, profile=""):
    """The id of a session still working, or None. Pure: the caller supplies the clock.

    Every session is read, not only the last one this launcher fired: a worker
    between LLM turns (a long tool call, a delegated subagent) reports
    ``agent_running=false``, so the idle floor is what covers that race. A session
    belonging to another profile is ignored — it does not share the workspace.
    """
    moment = time.time() if now is None else now
    for session in sessions or []:
        if not isinstance(session, dict):
            continue
        owner = session.get("profile")
        if owner and profile and owner != profile:
            continue
        if session.get("is_streaming"):
            return session.get("session_id")
        last = session.get("updated_at") or session.get("last_message_at") or 0
        try:
            quiet = not last or (moment - float(last)) >= float(idle_minutes) * 60
        except (TypeError, ValueError):
            quiet = False
        if not quiet:
            return session.get("session_id")
    return None


#: A run as the engine's wrapper leaves it in the process table: the flags may sit
#: between the program and the subcommand, so the pattern allows tokens in between.
ROUND_PATTERN = re.compile(r"(?:^|[\s/])autoresearch(?:\.py)?\b(?:\s+[^\s]+)*\s+run(?:\s|$)")
#: pgrep's deliberately broad prefilter: it decides nothing, it only shrinks the list.
ROUND_PREFILTER = r"autoresearch"


def process_in_flight(lines, pattern=ROUND_PATTERN):
    """The command line of a run still in play, or None. Pure: the caller supplies lines.

    A run is a detached process tree that outlives the session that started it, so
    it is invisible to the session API — firing into it is how two writers come to
    share one ledger. The pattern is matched against real argv, where global flags
    sit between the program and ``run``; a literal ``"autoresearch run"`` misses
    exactly those and fails open.
    """
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    for line in lines or []:
        if compiled.search(line or ""):
            return (line or "").strip()
    return None


def live_process(prefilter=ROUND_PREFILTER, pattern=ROUND_PATTERN):
    """``process_in_flight`` over what pgrep sees; an unreadable pgrep is not a run.

    pgrep is a prefilter, never the decision: it cannot see a run whose argv differs,
    and it is absent on some hosts. Callers keep the marker file as the first signal.
    """
    try:
        done = subprocess.run(
            ["pgrep", "-af", prefilter], capture_output=True, text=True, timeout=SCAN_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return process_in_flight((done.stdout or "").splitlines(), pattern)


def pid_alive(pid):
    """True when ``pid`` names a live process. ``EPERM`` means alive but not ours."""
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError, OverflowError):
        return False
    return True


def marker_path(state_dir, repo=None, env=None):
    """The marker file a run writes: ``$MARKER_ENV`` when set, else ``<state_dir>/<MARKER_NAME>``.

    The one home for both names: the engine's writer and this guard read the same file
    because the *guard* computes its path here, and the launcher reads no marker name of
    its own. A relative ``state_dir`` resolves against ``repo`` exactly as ``launch.py``
    resolves it, so a profile whose config uses the default cannot point the guard at a
    second directory.
    """
    env = os.environ if env is None else env
    override = env.get(MARKER_ENV)
    if override:
        return Path(override).expanduser()
    state = Path(state_dir).expanduser()
    if repo is not None and not state.is_absolute():
        state = Path(repo) / state
    return state / MARKER_NAME


def read_marker(path):
    """``(marker, problem)``: the parsed marker file, or why it cannot be read."""
    file = Path(path)
    if not file.is_file():
        return None, None
    try:
        data = json.loads(file.read_text())
    except (OSError, ValueError) as exc:
        return None, f"marker {file} is unreadable ({type(exc).__name__})"
    if not isinstance(data, dict):
        return None, f"marker {file} is not an object"
    return data, None


def marker_state(path, now=None, alive=pid_alive):
    """``(blocking, reason)`` from the run's marker file — broad check first.

    Broad: does a marker exist at all? Specific: does its pid still run? A marker
    whose pid is gone is a crashed or finished run and does not block; a marker that
    exists but cannot be parsed blocks, because a guard that cannot read the signal
    must not read it as "clear". The file is never deleted here — the run owns it.
    """
    marker, problem = read_marker(path)
    if problem:
        return True, f"{problem} — refusing to fire blind"
    if marker is None:
        return False, "no marker"
    pid = marker.get("pid")
    if pid is None:
        return True, f"marker {path} carries no pid — refusing to fire blind"
    if not alive(pid):
        return False, f"stale marker (pid {pid} is gone)"
    started = marker.get("started") or "unknown"
    detail = f"run pid {pid} started {started}"
    moment = time.time() if now is None else now
    epoch = marker.get("epoch")
    if not isinstance(epoch, (int, float)):
        return True, detail
    age_hours = (moment - float(epoch)) / 3600.0
    if age_hours > MARKER_MAX_AGE_HOURS:
        return True, f"{detail} — running for {age_hours:.1f} h (pid reuse? check by hand)"
    return True, detail


def log_skip(log_path, reason, scanned=0, now=None):
    """Append one skip line; an unwritable log never turns a skip into a fire."""
    stamp = datetime.now(timezone.utc) if now is None else now
    line = f"{stamp.strftime('%Y-%m-%d %H:%M UTC')}: skip, {reason} ({scanned} sessions scanned)\n"
    try:
        with Path(log_path).open("a") as handle:
            handle.write(line)
    except OSError:
        return None
    return line
