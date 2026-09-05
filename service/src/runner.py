"""Bounded subprocess runner for the autoresearch loop (PRD-05, SC5; PRD-06, SC1/SC2).

Executes THE canonical autoresearch contract at `contract/` — `prepare.py`
(immutable data prep) followed by `train.py` (the agent-edited artifact) — as
two sequential `python3` subprocesses under a single time budget. No vendored
copy: the runner consumes `contract/` directly (host dev: `repo/contract`;
container: `/app/contract` via the compose read-only bind mount), or a custom
workload dir via `RESEARCH_WORKLOAD_DIR`. The metric is parsed from the LAST
matching stdout line of train.py — either `RESULT val_bpb=...` (legacy vendor
format) or `val_bpb: ...` (the canonical contract summary block).

Sandbox posture: explicit args list (no shell), always a timeout, output
captured, and the child env carries the budget (`RUN_TIMEOUT`), overridable at
the runner level via the `RESEARCH_RUN_TIMEOUT` env var.

Isolated-workdir mode (PRD-06 SC1/SC2): pass `work_dir` to `run_loop` to execute
inside a pre-provisioned per-job workspace (see `src.workspace.provision_workspace`)
instead of the shared reference workload dir, so concurrent jobs never share a
working directory. In that mode the report additionally carries the workspace
`topic` (from topic.txt) and corpus stats (file count + total chars) in every
branch; with no `work_dir` the report is unchanged (no topic/corpus keys).
"""

import os
import re
import subprocess
import time
from pathlib import Path

RESULT_RE = re.compile(r"RESULT\s+val_bpb=([-+0-9.eE]+)")
# Canonical contract summary block (contract/train.py): `val_bpb: 3.795531`.
SUMMARY_RE = re.compile(r"val_bpb:\s*([-+0-9.eE]+)")


def resolve_workload_dir() -> Path:
    """Locate the canonical autoresearch contract (or a custom workload).

    Priority:
      1. $RESEARCH_WORKLOAD_DIR — explicit env override (custom workload).
      2. <repo-root>/contract    — host dev layout (repo/contract).
      3. <service-root>/contract — container layout (/app/contract via the
         compose read-only bind mount).
    The first candidate that is a directory containing `prepare.py` wins; if
    none exists, fall back to <service-root>/workload so a user can still drop
    a custom workload directory there.
    """
    env_dir = os.environ.get("RESEARCH_WORKLOAD_DIR")
    if env_dir:
        return Path(env_dir)
    here = Path(__file__).resolve()
    for candidate in (here.parents[2] / "contract", here.parents[1] / "contract"):
        if candidate.is_dir() and (candidate / "prepare.py").is_file():
            return candidate
    return here.parents[1] / "workload"


DEFAULT_WORKLOAD_DIR = resolve_workload_dir()
# Budget override env (mirrors the RUN_TIMEOUT handed to the workload scripts).
DEFAULT_RUN_TIMEOUT = float(os.environ.get("RESEARCH_RUN_TIMEOUT", "30"))


def parse_val_bpb(stdout: str) -> float | None:
    """Return the float from the LAST matching metric line in stdout.

    Two output formats are supported and scanned together, lines in reverse
    (last occurrence wins):
      - `RESULT val_bpb=<float>`       — legacy vendor-stub format (RESULT_RE)
      - `val_bpb: <float>`             — canonical contract summary block
                                         (SUMMARY_RE; contract/train.py prints
                                         ``val_bpb:          3.795531``)
    If both patterns match the same line, the RESULT line is preferred.
    """
    for line in reversed(stdout.splitlines()):
        m = RESULT_RE.search(line)
        if m:
            return float(m.group(1))
        m = SUMMARY_RE.search(line)
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

    def _run_script(self, script: str, env: dict, cwd: Path | None = None) -> tuple:
        """Run one script in the workload (or per-job workspace) dir.

        Returns (returncode | None, stdout, stderr); returncode None means the
        budget expired — subprocess.run() kills the child before re-raising
        TimeoutExpired, so the process never survives the budget.
        """
        try:
            proc = subprocess.run(  # explicit args list, no shell, always timeout
                ["python3", script],
                cwd=str(cwd if cwd is not None else self.workload_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            return None, exc.stdout or "", exc.stderr or ""

    @staticmethod
    def _read_topic(run_dir: Path) -> str:
        """Topic string from topic.txt (missing/unreadable -> empty string)."""
        try:
            return (run_dir / "topic.txt").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return ""

    @staticmethod
    def _corpus_stats(run_dir: Path) -> dict:
        """Corpus stats: file count + total chars under run_dir/corpus (0/0 absent)."""
        files, chars = 0, 0
        corpus_dir = run_dir / "corpus"
        if corpus_dir.is_dir():
            for p in corpus_dir.rglob("*"):
                if p.is_file():
                    files += 1
                    try:
                        chars += len(p.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        pass
        return {"files": files, "chars": chars}

    def _workspace_report(self, run_dir: Path) -> dict:
        """topic + corpus stats for the isolated-workdir report (PRD-06 SC2)."""
        return {
            "topic": self._read_topic(run_dir),
            "corpus": self._corpus_stats(run_dir),
        }

    def run_loop(self, work_dir: str | None = None) -> dict:
        """Execute prepare.py then train.py; return the run report.

        `work_dir`: optional pre-provisioned per-job workspace (PRD-06 SC1). When
        given, the scripts run with cwd=work_dir and the report additionally
        carries `topic` (from topic.txt) and `corpus` stats (files/chars) in
        every branch. When None, the shared reference workload dir is used and
        the report has no topic/corpus keys (legacy behaviour, unchanged).

        status: 'completed' | 'failed' | 'timeout'
          - completed: both scripts exited 0 (val_bpb may still be None if
            train.py printed no RESULT line).
          - failed: missing scripts, or a non-zero exit (prepare failure short-
            circuits before train).
          - timeout: the budget expired mid-run; the child was killed.
        """
        t0 = time.monotonic()
        command = "python3 prepare.py && python3 train.py"
        run_dir = Path(work_dir) if work_dir else self.workload_dir
        extra = self._workspace_report(run_dir) if work_dir else {}

        missing = [name for name in ("prepare.py", "train.py")
                   if not (run_dir / name).is_file()]
        if missing:
            return {
                "status": "failed",
                "val_bpb": None,
                "output": "missing workload scripts: " + ", ".join(missing),
                "duration_s": time.monotonic() - t0,
                "command": command,
                **extra,
            }

        env = self._env()
        chunks = []
        val_bpb = None
        for script in ("prepare.py", "train.py"):
            rc, stdout, stderr = self._run_script(script, env, cwd=run_dir)
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
                    **extra,
                }
            if rc != 0:  # prepare failure short-circuits; train crash fails too
                return {
                    "status": "failed",
                    "val_bpb": None,
                    "output": "".join(chunks),
                    "duration_s": time.monotonic() - t0,
                    "command": command,
                    **extra,
                }
            if script == "train.py" and stdout:
                val_bpb = parse_val_bpb(stdout)

        return {
            "status": "completed",
            "val_bpb": val_bpb,
            "output": "".join(chunks),
            "duration_s": time.monotonic() - t0,
            "command": command,
            **extra,
        }