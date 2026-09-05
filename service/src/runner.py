"""Bounded subprocess runner for the autoresearch loop (PRD-05, SC5).

Executes a workload directory — `prepare.py` (immutable data prep) followed by
`train.py` (the agent-edited artifact) — as two sequential `python3` subprocesses
under a single time budget. The metric is parsed from the LAST stdout line of
train.py matching `RESULT val_bpb=...`.

Sandbox posture: explicit args list (no shell), always a timeout, output
captured, and the child env carries the budget (`RUN_TIMEOUT`), overridable at
the runner level via the `RESEARCH_RUN_TIMEOUT` env var.
"""

import os
import re
import subprocess
import time
from pathlib import Path

RESULT_RE = re.compile(r"RESULT\s+val_bpb=([-+0-9.eE]+)")

# service/src/runner.py -> service/workload/
DEFAULT_WORKLOAD_DIR = Path(__file__).resolve().parents[1] / "workload"
# Budget override env (mirrors the RUN_TIMEOUT handed to the workload scripts).
DEFAULT_RUN_TIMEOUT = float(os.environ.get("RESEARCH_RUN_TIMEOUT", "30"))


def parse_val_bpb(stdout: str) -> float | None:
    """Return the float from the LAST 'RESULT val_bpb=...' line in stdout."""
    for line in reversed(stdout.splitlines()):
        m = RESULT_RE.search(line)
        if m:
            return float(m.group(1))
    return None


class ResearchRunner:
    """Run the workload's prepare.py then train.py under a time budget."""

    def __init__(self, workload_dir: str | None = None,
                 timeout_s: float | None = None):
        self.workload_dir = Path(workload_dir) if workload_dir else DEFAULT_WORKLOAD_DIR
        self.timeout_s = float(timeout_s) if timeout_s is not None else DEFAULT_RUN_TIMEOUT

    def _env(self) -> dict:
        """Parent env plus the budget vars the workload scripts may read."""
        env = dict(os.environ)
        env["RUN_TIMEOUT"] = str(self.timeout_s)
        return env

    def _run_script(self, script: str, env: dict) -> tuple:
        """Run one script in the workload dir.

        Returns (returncode | None, stdout, stderr); returncode None means the
        budget expired — subprocess.run() kills the child before re-raising
        TimeoutExpired, so the process never survives the budget.
        """
        try:
            proc = subprocess.run(  # explicit args list, no shell, always timeout
                ["python3", script],
                cwd=str(self.workload_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            return None, exc.stdout or "", exc.stderr or ""

    def run_loop(self) -> dict:
        """Execute prepare.py then train.py; return the run report.

        status: 'completed' | 'failed' | 'timeout'
          - completed: both scripts exited 0 (val_bpb may still be None if
            train.py printed no RESULT line).
          - failed: missing scripts, or a non-zero exit (prepare failure short-
            circuits before train).
          - timeout: the budget expired mid-run; the child was killed.
        """
        t0 = time.monotonic()
        command = "python3 prepare.py && python3 train.py"

        missing = [name for name in ("prepare.py", "train.py")
                   if not (self.workload_dir / name).is_file()]
        if missing:
            return {
                "status": "failed",
                "val_bpb": None,
                "output": "missing workload scripts: " + ", ".join(missing),
                "duration_s": time.monotonic() - t0,
                "command": command,
            }

        env = self._env()
        chunks = []
        val_bpb = None
        for script in ("prepare.py", "train.py"):
            rc, stdout, stderr = self._run_script(script, env)
            chunk = "$ python3 {}\n{}".format(script, stdout)
            if stderr and stderr not in stdout:
                chunk += stderr
            chunks.append(chunk)
            if rc is None:  # budget expired — subprocess.run killed the child
                return {
                    "status": "timeout",
                    "val_bpb": None,
                    "output": "".join(chunks),
                    "duration_s": time.monotonic() - t0,
                    "command": command,
                }
            if rc != 0:  # prepare failure short-circuits; train crash fails too
                return {
                    "status": "failed",
                    "val_bpb": None,
                    "output": "".join(chunks),
                    "duration_s": time.monotonic() - t0,
                    "command": command,
                }
            if script == "train.py" and stdout:
                val_bpb = parse_val_bpb(stdout)

        return {
            "status": "completed",
            "val_bpb": val_bpb,
            "output": "".join(chunks),
            "duration_s": time.monotonic() - t0,
            "command": command,
        }