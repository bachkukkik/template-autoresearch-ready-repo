"""Running the verify/guard commands and reading the metric out of them.

A measurement command is untrusted input that the operator wrote, so it is never
handed to a shell: ``shlex.split`` produces argv and the child is exec'd
directly. The child environment is scrubbed of anything whose *name* looks like a
credential — a verify script has no business seeing an API key — and no value is
ever logged, only names.
"""

from __future__ import annotations

import math
import os
import re
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

#: Variable *names* matching this are removed from a measurement child's env.
#: Only the name is inspected; values are never read, compared or logged.
SCRUB_PATTERN = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)

FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

TAIL_LINES = 40

#: ``measure()`` reduces repeats to a **median**, whose SE is ``1.2533 * s /
#: sqrt(n)`` (the factor is ``sqrt(pi/2)``). A margin built on the mean's
#: ``s / sqrt(n)`` would be ~20% too narrow to be honest.
MEDIAN_CONSISTENCY = 1.2533


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
    """One verify run (or a repeat series reduced by median).

    ``repeats`` and ``spread`` are facts about ``values``, filled in here rather
    than trusted from the caller: the spread is the sample standard deviation,
    and below two repeats there is no sample, so it is ``None`` and the
    measurement is not ``honest`` evidence of anything.

    ``honest`` has exactly one definition, derived here and never assigned by a
    caller: at least two repeats *and* a point estimate to talk about. A repeat
    series that failed on its second run has several values but no result, and
    claiming it as evidence would be a lie.
    """

    value: Optional[float]
    values: List[float] = field(default_factory=list)
    seconds: float = 0.0
    ok: bool = False
    log_tail: str = ""
    repeats: int = 0
    spread: Optional[float] = None
    honest: bool = False
    #: The evaluator's own output line the metric was read from — the record keeps
    #: evidence, not a paraphrase, so a later reader can re-derive the number. With
    #: repeats it is the line of the *median repeat*, never a later one.
    raw: str = ""

    def __post_init__(self) -> None:
        if not self.repeats:
            self.repeats = len(self.values)
        if self.spread is None and len(self.values) >= 2:
            self.spread = statistics.stdev(self.values)
        self.honest = self.repeats >= 2 and self.value is not None


def standard_error_of_difference(
    candidate: Measurement, incumbent: Measurement
) -> Optional[float]:
    """SE of the difference of two **medians**: ``sqrt(k^2 s1^2/n1 + k^2 s2^2/n2)``.

    This is an **independent two-sample** standard error — nothing here is
    paired: the two runs share no seed, no ordering and no data, so no
    covariance term is available to subtract. ``k`` is
    :data:`MEDIAN_CONSISTENCY`, because the point estimates the margin compares
    are medians, not means.

    ``None`` when either side is not honest (fewer than two repeats, i.e. no
    sample to measure dispersion from, or no point estimate at all): the caller
    must fall back to a fixed floor instead of inventing a zero. The gate is the
    repeat count — the single source of truth for whether something was
    measured — not ``spread``, so a hand-built measurement that reports repeats
    but no recorded dispersion is treated as *no observed dispersion* (variance
    0), exactly like a series of identical repeats.
    """
    if not candidate.honest or not incumbent.honest:
        return None
    first_spread = 0.0 if candidate.spread is None else candidate.spread
    second_spread = 0.0 if incumbent.spread is None else incumbent.spread
    return MEDIAN_CONSISTENCY * math.sqrt(
        first_spread**2 / candidate.repeats + second_spread**2 / incumbent.repeats
    )


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


def _find(stdout: str, name: str) -> "tuple[Optional[float], Optional[str]]":
    """The metric and the exact line it came from; ``(None, None)`` when absent."""
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None, None
    escaped = re.escape(name)

    tagged = re.compile(rf"^METRIC\s+{escaped}\s*=\s*({FLOAT_RE})$")
    for line in reversed(lines):
        match = tagged.match(line)
        if match:
            return float(match.group(1)), line

    labelled = re.compile(rf"^{escaped}\s*:\s*({FLOAT_RE})$")
    for line in reversed(lines):
        match = labelled.match(line)
        if match:
            return float(match.group(1)), line

    bare = re.compile(rf"^({FLOAT_RE})$")
    match = bare.match(lines[-1])
    if match:
        return float(match.group(1)), lines[-1]
    return None, None


def parse_metric(stdout: str, name: str) -> Optional[float]:
    """Extract ``name`` from a verify command's stdout.

    Three accepted shapes, in priority order:

    (a) ``METRIC name=1.5``      — preferred, unambiguous;
    (b) ``name: 1.5``            — a plain labelled line;
    (c) a final bare ``1.5``     — last resort for one-number scripts.

    The *last* matching line wins in every case, so a script may log a header
    value and then the final one.
    """
    return _find(stdout, name)[0]


def metric_line(stdout: str, name: str) -> Optional[str]:
    """The evaluator's own line for ``name`` — what a run record keeps as ``raw``."""
    return _find(stdout, name)[1]


def median_index(values: Sequence[float]) -> int:
    """The repeat the median belongs to; the lower middle one for an even count.

    A record keeps the evaluator's own line beside the number, and the median of an
    even series is an average that no run printed. The point estimate stays
    :func:`statistics.median`; this index only says which line is the median
    *repeat*, so the pairing is stated rather than claimed.
    """
    order = sorted(range(len(values)), key=lambda index: values[index])
    return order[(len(values) - 1) // 2]


def measure(cfg, *, log=None) -> Measurement:
    """Run verify ``cfg.repeats`` times; the metric is the median of the runs."""
    values: List[float] = []
    seconds = 0.0
    tail = ""
    lines: List[str] = []
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
        line = metric_line(result.stdout, cfg.metric_name) or ""
        values.append(value)
        lines.append(line)
    chosen = median_index(values)
    return Measurement(
        statistics.median(values), values, seconds, True, tail, raw=lines[chosen]
    )


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
