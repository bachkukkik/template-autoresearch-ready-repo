"""Harness adapters — one argv shape per agent CLI, plus ``command`` and ``replay``.

The argv is fixed and exact because the loop's behaviour has to be reproducible:
a run recorded with one harness must be replayable without that harness present.
``replay`` is therefore not a process at all — it re-applies the recorded patch.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import gitops
from . import measure as measure_mod

#: Default binary per harness name.
DEFAULT_BINARIES: Dict[str, str] = {
    "claude": "claude",
    "opencode": "opencode",
    "hermes": "hermes",
    "dsh": "dsh",
}

HARNESSES = ("claude", "opencode", "hermes", "dsh")
AGENTS = HARNESSES + ("command", "replay")

TAIL_LINES = 40


@dataclass
class AgentResult:
    exit_code: int
    seconds: float
    output_tail: str
    description: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join((text or "").rstrip().splitlines()[-lines:])


def _description(output: str, iteration: int) -> str:
    """Last ``CHANGE: <summary>`` line, else ``iteration <i>``.

    The summary is agent-controlled text that becomes a commit subject and a
    report cell, so it is reduced to one printable, whitespace-collapsed,
    length-capped line.
    """
    for line in reversed((output or "").splitlines()):
        stripped = line.strip()
        if stripped.upper().startswith("CHANGE:"):
            summary = sanitize(stripped[len("CHANGE:") :])
            if summary:
                return summary
    return f"iteration {iteration}"


#: Longest description kept. A commit subject is one line; a report cell is one
#: cell, and neither should be at the mercy of what the agent printed.
DESCRIPTION_LIMIT = 120


def sanitize(text: str, limit: int = DESCRIPTION_LIMIT) -> str:
    """One printable line: no control characters, no runs of whitespace."""
    printable = "".join(ch if ch.isprintable() else " " for ch in (text or ""))
    return " ".join(printable.split())[:limit].rstrip()


def _kill_group(proc: subprocess.Popen) -> None:
    measure_mod.kill_group(proc)


class Adapter:
    """One agent harness, addressed by name.

    ``binary`` is the executable the loop expects on ``PATH`` (``None`` for
    ``command`` and ``replay``, which need no discovery of their own).
    """

    def __init__(
        self,
        name: str,
        binary: Optional[str] = None,
        *,
        model: Optional[str] = None,
        extra: Sequence[str] = (),
        agent_cmd: Optional[str] = None,
        records: Optional[Sequence[Dict]] = None,
    ):
        if name not in AGENTS:
            raise ValueError(f"unknown agent {name!r}; choose from {AGENTS}")
        self.name = name
        self.binary = DEFAULT_BINARIES.get(name) if binary is None else binary
        self.model = model
        self.extra = list(extra)
        self.agent_cmd = agent_cmd
        self.records = list(records or [])
        if name == "command" and not agent_cmd:
            raise ValueError("the command adapter needs --agent-cmd")

    # -- argv ----------------------------------------------------------------

    def prompt_path(self, repo: os.PathLike | str) -> Path:
        return Path(repo) / gitops.STATE_DIR / "prompt.txt"

    def argv(
        self,
        prompt: str,
        repo: os.PathLike | str,
        model: Optional[str] = None,
        extra: Optional[Sequence[str]] = None,
    ) -> List[str]:
        """The exact argv this harness is invoked with."""
        model = self.model if model is None else model
        extra = list(self.extra if extra is None else extra)
        repo = str(repo)

        if self.name == "claude":
            argv = [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "text",
                "--permission-mode",
                "acceptEdits",
                "--allowedTools",
                "Read,Edit,Write,Glob,Grep,Bash",
            ]
            if model:
                argv += ["--model", model]
            return argv + extra

        if self.name == "opencode":
            argv = ["opencode", "run", "--dir", repo]
            if model:
                argv += ["--model", model]
            return argv + extra + [prompt]

        if self.name == "hermes":
            argv = ["hermes", "chat", "-q", prompt, "-Q", "--yolo", "--in", repo]
            if model:
                argv += ["-m", model]
            return argv + extra

        if self.name == "dsh":
            return ["dsh", "--profile", "headless"] + extra + [prompt]

        if self.name == "command":
            prompt_file = str(self.prompt_path(repo))
            tokens = shlex.split(self.agent_cmd or "")
            return [
                token.replace("{prompt_file}", prompt_file).replace("{repo}", repo)
                for token in tokens
            ] + extra

        # replay: no process
        return []

    def resolve_binary(self) -> Optional[str]:
        """The binary the dry-run preflight should look for on ``PATH``."""
        if self.name in HARNESSES:
            return self.binary
        if self.name == "command":
            tokens = shlex.split(self.agent_cmd or "")
            return tokens[0] if tokens else None
        return None

    def env(self, repo: os.PathLike | str) -> Dict[str, str]:
        """Child environment.

        Agents need the operator's credentials, so this is *not* the scrubbed
        measurement environment. ``dsh`` additionally needs to be told which
        worktree it is working in.
        """
        env = dict(os.environ)
        if self.name == "dsh":
            env["DEEPSEEK_HARNESS_WORKSPACE"] = str(repo)
        return env

    # -- execution -----------------------------------------------------------

    def run(
        self,
        prompt: str,
        repo: os.PathLike | str,
        timeout: float,
        iteration: int = 1,
    ) -> AgentResult:
        if self.name == "replay":
            return self._run_replay(repo, timeout, iteration)

        if self.name == "command":
            path = self.prompt_path(repo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prompt, encoding="utf-8")

        argv = self.argv(prompt, repo)
        started = time.monotonic()
        proc = subprocess.Popen(
            argv,
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env(repo),
            start_new_session=True,
        )
        timed_out = False
        try:
            try:
                output, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
                output, _ = measure_mod.collect_after_kill(proc)
        except BaseException:
            # Ctrl-C: the loop reverts the worktree, so a harness still writing
            # to it must be killed before the interrupt travels upwards.
            _kill_group(proc)
            raise
        seconds = time.monotonic() - started
        output = output or ""
        if timed_out:
            return AgentResult(
                exit_code=124,
                seconds=seconds,
                output_tail=_tail(f"agent timeout after {timeout:g}s\n{output}"),
                description=f"iteration {iteration} (timeout)",
            )
        return AgentResult(
            exit_code=proc.returncode if proc.returncode is not None else -1,
            seconds=seconds,
            output_tail=_tail(output),
            description=_description(output, iteration),
        )

    def _run_replay(self, repo, timeout: float, iteration: int) -> AgentResult:
        started = time.monotonic()
        record = self.record_for(iteration)
        if record is None:
            return AgentResult(
                exit_code=1,
                seconds=time.monotonic() - started,
                output_tail=f"no replay record for iteration {iteration}",
                description=f"iteration {iteration} (no record)",
            )
        patch = record.get("patch") or ""
        description = sanitize(str(record.get("description") or f"iteration {iteration}"))
        if not patch.strip():
            return AgentResult(
                exit_code=0,
                seconds=time.monotonic() - started,
                output_tail="empty patch",
                description=description,
            )
        proc = gitops.apply_patch(repo, patch, timeout=timeout)
        output = (proc.stderr or proc.stdout or "").strip()
        return AgentResult(
            exit_code=proc.returncode,
            seconds=time.monotonic() - started,
            output_tail=_tail(f"git apply: {output}" if output else "git apply: ok"),
            description=description,
        )

    def record_for(self, iteration: int) -> Optional[Dict]:
        for record in self.records:
            if record.get("iteration") == iteration:
                return record
        return None


def make_adapter(
    agent: str,
    *,
    model: Optional[str] = None,
    extra: Sequence[str] = (),
    agent_cmd: Optional[str] = None,
    records: Optional[Sequence[Dict]] = None,
) -> Adapter:
    return Adapter(
        agent,
        model=model,
        extra=extra,
        agent_cmd=agent_cmd,
        records=records,
    )


def load_records(path: os.PathLike | str) -> List[Dict]:
    """Read a ``--record`` JSONL file written by a previous run."""
    records: List[Dict] = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{number} is not valid JSON: {exc}") from exc
            if not isinstance(record, dict) or "iteration" not in record:
                raise ValueError(f"{path}:{number} is not a record object")
            records.append(record)
    return records
