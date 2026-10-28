"""Running the verify/guard commands and reading the metric out of them.

A measurement command is untrusted input that the operator wrote, so it is never
handed to a shell: ``shlex.split`` produces argv and the child is exec'd
directly. The child environment is scrubbed of anything whose *name* looks like a
credential — a verify script has no business seeing an API key — and no value is
ever logged, only names.
"""

from __future__ import annotations

import os
import re
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

#: Variable *names* matching this are removed from a measurement child's env.
#: Only the name is inspected; values are never read, compared or logged.
SCRUB_PATTERN = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)

FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

TAIL_LINES = 40


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False

    def tail(self, lines: int = TAIL_LINES) -> str:
        text = "\n".join(part for part in (self.stdout, self.stderr) if part)
        return "\n".join(text.rstrip().splitlines()[-lines:])


@dataclass
class Measurement:
    """One verify run (or a repeat series reduced by median)."""

    value: Optional[float]
    values: List[float] = field(default_factory=list)
    seconds: float = 0.0
    ok: bool = False
    log_tail: str = ""


def scrub_env(env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Drop every variable whose name matches :data:`SCRUB_PATTERN`."""
    source = dict(os.environ if env is None else env)
    return {k: v for k, v in source.items() if not SCRUB_PATTERN.search(k)}


def kill_group(proc: subprocess.Popen) -> None:
    """Kill the child *and its children* — a verify script may fork helpers."""
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except OSError:
            pass


#: Bound on the drain after a kill. A ``setsid`` grandchild inherits stdout and
#: can hold the pipe open long after the child is dead, so ``communicate()`` with
#: no timeout after a kill is not a bound at all.
KILL_GRACE = 5.0


def collect_after_kill(proc: subprocess.Popen) -> "tuple[str, str]":
    """Read what a killed child wrote, without waiting on a leaked pipe.

    The drain is bounded; when even that fails the pipes are closed and the
    caller moves on. A lost tail is a missing clue, a hung run is a bug.
    """
    try:
        stdout, stderr = proc.communicate(timeout=KILL_GRACE)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=KILL_GRACE)
        except (subprocess.TimeoutExpired, OSError):
            pass
        return "", ""
    return stdout or "", stderr or ""


def run_command(
    command: str,
    repo: os.PathLike | str,
    timeout: float,
    *,
    env: Optional[Dict[str, str]] = None,
) -> CommandResult:
    """Run one operator command, bounded by ``timeout``, with a scrubbed env."""
    import shlex

    argv = shlex.split(command)
    if not argv:
        raise ValueError("empty command")
    child_env = scrub_env(os.environ if env is None else env)
    started = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=child_env,
        start_new_session=True,
    )
    timed_out = False
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_group(proc)
            stdout, stderr = collect_after_kill(proc)
    except BaseException:
        # Ctrl-C must not orphan the child: the loop reverts the worktree from
        # under it, so it is killed before the interrupt travels upwards.
        kill_group(proc)
        raise
    return CommandResult(
        exit_code=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout or "",
        stderr=stderr or "",
        seconds=time.monotonic() - started,
        timed_out=timed_out,
    )


def parse_metric(stdout: str, name: str) -> Optional[float]:
    """Extract ``name`` from a verify command's stdout.

    Three accepted shapes, in priority order:

    (a) ``METRIC name=1.5``      — preferred, unambiguous;
    (b) ``name: 1.5``            — a plain labelled line;
    (c) a final bare ``1.5``     — last resort for one-number scripts.

    The *last* matching line wins in every case, so a script may log a header
    value and then the final one.
    """
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    escaped = re.escape(name)

    tagged = re.compile(rf"^METRIC\s+{escaped}\s*=\s*({FLOAT_RE})$")
    for line in reversed(lines):
        match = tagged.match(line)
        if match:
            return float(match.group(1))

    labelled = re.compile(rf"^{escaped}\s*:\s*({FLOAT_RE})$")
    for line in reversed(lines):
        match = labelled.match(line)
        if match:
            return float(match.group(1))

    bare = re.compile(rf"^({FLOAT_RE})$")
    match = bare.match(lines[-1])
    if match:
        return float(match.group(1))
    return None


def measure(cfg, *, log=None) -> Measurement:
    """Run verify ``cfg.repeats`` times; the metric is the median of the runs."""
    values: List[float] = []
    seconds = 0.0
    tail = ""
    for _ in range(max(1, int(cfg.repeats))):
        try:
            result = run_command(cfg.verify, cfg.repo, cfg.verify_timeout)
        except (OSError, ValueError) as exc:
            return Measurement(None, values, seconds, False, str(exc))
        seconds += result.seconds
        tail = result.tail()
        if result.timed_out:
            return Measurement(None, values, seconds, False, f"timeout\n{tail}".strip())
        if result.exit_code != 0:
            return Measurement(
                None, values, seconds, False, f"exit {result.exit_code}\n{tail}".strip()
            )
        value = parse_metric(result.stdout, cfg.metric_name)
        if value is None:
            return Measurement(
                None,
                values,
                seconds,
                False,
                f"no {cfg.metric_name!r} metric in stdout\n{tail}".strip(),
            )
        values.append(value)
    return Measurement(statistics.median(values), values, seconds, True, tail)


def run_guard(cfg) -> "tuple[bool, str]":
    """Run the guard command; ``(True, "")`` when no guard is configured."""
    if not cfg.guard:
        return True, ""
    try:
        result = run_command(cfg.guard, cfg.repo, cfg.guard_timeout)
    except (OSError, ValueError) as exc:
        return False, str(exc)
    if result.timed_out:
        return False, f"guard timeout\n{result.tail()}".strip()
    if result.exit_code != 0:
        return False, f"guard exit {result.exit_code}\n{result.tail()}".strip()
    return True, ""
