"""The live-round marker: the loop writes it, the unattended guard reads it.

An unattended fire needs a signal that a run is already in play. A session API cannot
see one — the run is a detached process tree that outlives the session that started
it — and a process scan is brittle by nature: the argv shape varies with the flags an
operator passes, and ``pgrep`` is absent on some hosts. Both failures are silent, and
a guard that fails silently is a second writer on one ledger.

So the run announces itself in a file. :func:`round_marker` writes
``<state_dir>/round.marker`` (or ``$AUTORESEARCH_ROUND_MARKER``) at start and removes
it at exit, carrying the pid, the start time and the repo. The guard reads the file
first and treats a pid that is gone as a finished run; the process scan stays as a
second, independent signal.

Writing is best-effort: a marker that cannot be written must not stop a run the
operator started by hand, and it says so on stderr. The guard then falls back to the
scan, which is what it would have had without this file.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

#: The env var that moves the marker; the default lives inside the run's state dir.
ENV = "AUTORESEARCH_ROUND_MARKER"
FILENAME = "round.marker"


def path_for(cfg):
    """Where this run's marker goes: the env override, else ``<state_dir>/round.marker``."""
    override = os.environ.get(ENV)
    if override:
        return Path(override).expanduser()
    return Path(cfg.state_dir) / FILENAME


def payload(cfg, argv=None, now=None):
    """The marker body, as the guard expects to read it. Pure."""
    moment = time.time() if now is None else now
    started = datetime.fromtimestamp(moment, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "pid": os.getpid(),
        "started": started,
        "epoch": moment,
        "repo": str(cfg.repo),
        "state_dir": str(cfg.state_dir),
        "argv": list(sys.argv if argv is None else argv)[:8],
    }


def write(path, cfg):
    """Write the marker, or warn and return None — never raise into the run."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload(cfg), indent=1) + "\n")
    except OSError as exc:
        print(f"marker: cannot write {target} ({exc}) — the unattended guard falls back "
              f"to its process scan", file=sys.stderr)
        return None
    return target


def clear(path):
    """Remove the marker; a missing one is already clear."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        return False
    return True


def read(path):
    """``(marker, problem)``: the parsed marker, or why it cannot be read."""
    file = Path(path)
    if not file.is_file():
        return None, None
    try:
        data = json.loads(file.read_text())
    except (OSError, ValueError) as exc:
        return None, f"{file} is unreadable ({type(exc).__name__})"
    return (data, None) if isinstance(data, dict) else (None, f"{file} is not an object")


@contextlib.contextmanager
def round_marker(cfg):
    """Hold the marker for the duration of one run, and remove it however the run ends."""
    path = path_for(cfg)
    written = write(path, cfg)
    try:
        yield written
    finally:
        if written is not None:
            clear(written)
