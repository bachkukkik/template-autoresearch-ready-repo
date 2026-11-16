"""Run configuration — validation, creation and persistence of ``run.json``.

``init`` writes the file once; every later command reads it and nothing rewrites
it. That is deliberate: the config is the contract the ledger is validated
against, so a run that silently changed its own metric direction or noise floor
would make its history meaningless.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import posixpath
import shlex
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import gitops
from . import objective as objective_mod

try:  # POSIX-only; a Windows run simply has no lock rather than no engine.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

STATE_DIR = gitops.STATE_DIR
RUN_JSON = "run.json"
EVENTS_JSONL = "events.jsonl"
RESULTS_TSV = "results.tsv"
LAST_AGENT_LOG = "last_agent.log"
PROMPT_TXT = "prompt.txt"
REPORT_MD = "report.md"
LOCK_FILE = "lock"
GITIGNORE_BODY = "*\n"

DEFAULT_NOISE_FLOOR = 0.01
#: Three repeats by default (PRD 20 SC-evl-1): below two there is no sample, so
#: the dispersion gate is dormant while the docs claim it is live. ``--repeats 1``
#: stays honest (``honest: false``) and decides by the floor, as before.
DEFAULT_REPEATS = 3
DEFAULT_VERIFY_TIMEOUT = 600.0
DEFAULT_GUARD_TIMEOUT = 600.0
DIRECTIONS = ("lower", "higher")


class ConfigError(Exception):
    """A configuration or precondition problem. The CLI maps it to exit 2."""


# ─── path helpers ────────────────────────────────────────────────────────────


def state_dir(repo: os.PathLike | str, state: os.PathLike | str | None = None) -> Path:
    """The state directory: ``--state-dir`` when given, else ``<repo>/.autoresearch``."""
    if state:
        return Path(state).expanduser().resolve()
    return Path(repo) / STATE_DIR


def run_json_path(repo: os.PathLike | str, state: os.PathLike | str | None = None) -> Path:
    return state_dir(repo, state) / RUN_JSON


@contextlib.contextmanager
def state_lock(repo: os.PathLike | str, state: os.PathLike | str | None = None):
    """Hold the state directory's ``lock`` while a command mutates the run.

    Two runs on one repo would interleave commits and resets, so the second one
    is refused rather than queued: an operator who starts a run by mistake wants
    to be told, not to wait. The lock is advisory (``flock``) and released when
    the descriptor closes, including on an exception or a Ctrl-C.
    """
    if fcntl is None:  # pragma: no cover - POSIX-only engine
        yield
        return
    path = state_dir(repo, state) / LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ConfigError(
                f"another run holds the lock ({path}) — wait for it to finish"
            ) from exc
        yield


def under_scope(rel: str, scopes: Sequence[str]) -> bool:
    """True when repo-relative ``rel`` is ``scopes``-owned.

    A scope is a plain path prefix: ``src`` owns ``src`` and ``src/a/b.py`` but
    never ``srcfoo``. Exactly one leading ``./`` is stripped — ``lstrip('./')``
    would eat every leading dot and slash, so ``.github/...`` matched nothing.
    """
    rel = posixpath.normpath(rel.replace(os.sep, "/"))
    if rel == ".":
        rel = ""
    for scope in scopes:
        if rel == scope or rel.startswith(scope + "/"):
            return True
    return False


def hash_file(path: os.PathLike | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ─── the config object ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunConfig:
    """One run's immutable configuration."""

    repo: str
    verify: str
    metric_name: str
    direction: str
    scope: Tuple[str, ...]
    guard: Optional[str] = None
    target: Optional[float] = None
    noise_floor: float = DEFAULT_NOISE_FLOOR
    repeats: int = DEFAULT_REPEATS
    verify_timeout: float = DEFAULT_VERIFY_TIMEOUT
    guard_timeout: float = DEFAULT_GUARD_TIMEOUT
    protected: Mapping[str, str] = field(default_factory=dict)
    program: Optional[str] = None
    program_path: Optional[str] = None
    goal: Optional[str] = None
    created_at: str = ""
    #: An absolute state directory when ``--state-dir`` moved it out of the repo.
    state: Optional[str] = None
    #: The objective record this run was initialised from, and the leg it resolved.
    objective: Optional[str] = None
    objective_id: Optional[str] = None
    objective_leg: Optional[str] = None
    objective_unit: Optional[str] = None

    # -- views ---------------------------------------------------------------

    @property
    def state_dir(self) -> Path:
        return state_dir(self.repo, self.state)

    @property
    def events_path(self) -> Path:
        return self.state_dir / EVENTS_JSONL

    def protected_paths(self) -> List[str]:
        return sorted(self.protected)

    def as_dict(self) -> dict:
        return {
            "version": 1,
            "repo": self.repo,
            "verify": self.verify,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "scope": list(self.scope),
            "guard": self.guard,
            "target": self.target,
            "noise_floor": self.noise_floor,
            "repeats": self.repeats,
            "verify_timeout": self.verify_timeout,
            "guard_timeout": self.guard_timeout,
            "protected": dict(self.protected),
            "program": self.program,
            "program_path": self.program_path,
            "goal": self.goal,
            "created_at": self.created_at,
            "state_dir": self.state,
            "objective": self.objective,
            "objective_id": self.objective_id,
            "objective_leg": self.objective_leg,
            "objective_unit": self.objective_unit,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "RunConfig":
        try:
            direction = str(data["direction"])
            if direction not in DIRECTIONS:
                raise ConfigError(
                    f"direction must be one of {DIRECTIONS}, got {direction!r}"
                )
            return cls(
                repo=str(data["repo"]),
                verify=str(data["verify"]),
                metric_name=str(data["metric_name"]),
                direction=direction,
                scope=tuple(str(s) for s in data["scope"]),
                guard=data.get("guard"),
                target=None if data.get("target") is None else float(data["target"]),
                noise_floor=float(data.get("noise_floor", DEFAULT_NOISE_FLOOR)),
                repeats=int(data.get("repeats", DEFAULT_REPEATS)),
                verify_timeout=float(data.get("verify_timeout", DEFAULT_VERIFY_TIMEOUT)),
                guard_timeout=float(data.get("guard_timeout", DEFAULT_GUARD_TIMEOUT)),
                protected=dict(data.get("protected") or {}),
                program=data.get("program"),
                program_path=data.get("program_path"),
                goal=data.get("goal"),
                created_at=str(data.get("created_at", "")),
                state=data.get("state_dir"),
                objective=data.get("objective"),
                objective_id=data.get("objective_id"),
                objective_leg=data.get("objective_leg"),
                objective_unit=data.get("objective_unit"),
            )
        except KeyError as exc:
            raise ConfigError(f"run.json is missing the field {exc.args[0]!r}") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"run.json is malformed: {exc}") from exc


def load(repo: os.PathLike | str, state: os.PathLike | str | None = None) -> RunConfig:
    """Read the run's ``run.json`` from ``--state-dir``, else ``<repo>/.autoresearch``."""
    path = run_json_path(repo, state)
    if not path.is_file():
        raise ConfigError(
            f"no run configured under {path} — run `autoresearch init` first"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    return RunConfig.from_dict(data)


# ─── validation ──────────────────────────────────────────────────────────────


def require_git_repo(repo: os.PathLike | str) -> Path:
    try:
        return gitops.repo_root(repo)
    except (gitops.GitError, OSError) as exc:
        raise ConfigError(str(exc)) from exc


def require_clean(repo: os.PathLike | str, *, what: str = "working tree") -> None:
    dirty = gitops.status_paths(repo)
    if dirty:
        shown = ", ".join(dirty[:5]) + (" ..." if len(dirty) > 5 else "")
        raise ConfigError(
            f"{what} is not clean ({len(dirty)} changed path(s): {shown}) — "
            "commit or stash before continuing"
        )


def require_branch(repo: os.PathLike | str) -> str:
    name = gitops.branch(repo)
    if not name:
        raise ConfigError("HEAD is detached — check out a named branch first")
    return name


def normalize_scope(root: Path, scopes: Iterable[str]) -> Tuple[str, ...]:
    """Validate scope prefixes and return them in a canonical form."""
    out: List[str] = []
    for raw in scopes:
        text = str(raw).strip().rstrip("/")
        if not text:
            raise ConfigError("--scope must not be empty")
        if any(ch in text for ch in "*?["):
            raise ConfigError(
                f"scope {raw!r} contains a glob — scopes are plain path prefixes"
            )
        candidate = Path(text)
        if candidate.is_absolute():
            raise ConfigError(f"scope {raw!r} must be repo-relative")
        if ".." in candidate.parts:
            raise ConfigError(f"scope {raw!r} must not contain '..'")
        posix = candidate.as_posix()
        if posix in ("", "."):
            # A root scope makes `git clean -fd` repo-wide, so a revert would
            # delete every untracked file the operator owns.
            raise ConfigError(
                f"--scope {raw!r} is the repo root — a revert would clean every "
                "untracked file in the repository; name a subdirectory instead"
            )
        if not (root / candidate).exists():
            raise ConfigError(f"scope {raw!r} does not exist in {root}")
        out.append(posix)
    return tuple(dict.fromkeys(out))


_SHELL_META = set("$`|&;<>()*?[]{}!\n")


def path_tokens(command: str) -> List[str]:
    """Tokens of a command line that could name a repo file.

    Flags, absolute paths, URLs and anything carrying shell metacharacters are
    skipped — the point is to find ``score.py`` in ``python3 score.py``, not to
    parse shell.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    found: List[str] = []
    for token in tokens:
        if not token or token.startswith("-"):
            continue
        if "://" in token or any(ch in _SHELL_META for ch in token):
            continue
        found.append(token)
    return found


def default_protected(root: Path, commands: Iterable[Optional[str]]) -> Dict[str, str]:
    """Files named as path tokens in the verify/guard commands, hashed.

    Those are the files that define the measurement. An agent that edits them can
    make any candidate look good, so they are protected by default and the loop
    refuses a candidate that changes them.
    """
    protected: Dict[str, str] = {}
    for command in commands:
        if not command:
            continue
        for token in path_tokens(command):
            candidate = (root / token)
            try:
                if not candidate.is_file():
                    continue
                rel = candidate.resolve().relative_to(root.resolve()).as_posix()
            except (OSError, ValueError):
                continue
            protected[rel] = hash_file(candidate)
    return protected


def protected_mismatches(cfg: RunConfig) -> List[str]:
    """Protected files whose current content differs from the recorded hash."""
    root = Path(cfg.repo)
    bad: List[str] = []
    for rel in sorted(cfg.protected):
        path = root / rel
        try:
            if not path.is_file() or hash_file(path) != cfg.protected[rel]:
                bad.append(rel)
        except OSError:
            bad.append(rel)
    return bad


# ─── creation ────────────────────────────────────────────────────────────────


def _write_json(path: Path, data: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _unique_dir(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    candidate = parent / stamp
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = parent / f"{stamp}-{suffix}"
    candidate.mkdir()
    return candidate


def archive_state(root: Path, state: os.PathLike | str | None = None) -> Path:
    """Move the existing state aside into ``<state dir>/archive/<ts>/``."""
    here = state_dir(root, state)
    dest = _unique_dir(here / "archive")
    for entry in sorted(here.iterdir()):
        # The archive skips itself, and the lock: it is held by the very
        # `init --force` that is archiving, and moving it would release it.
        if entry.name in ("archive", LOCK_FILE):
            continue
        shutil.move(str(entry), str(dest / entry.name))
    return dest


def _read_program(root: Path, program: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not program:
        return None, None
    for candidate in (Path(program), root / program):
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8"), candidate.as_posix()
        except OSError as exc:
            raise ConfigError(f"cannot read program file {program!r}: {exc}") from exc
    raise ConfigError(f"program file {program!r} does not exist")


def _leg_contradictions(
    leg: Mapping[str, Any],
    *,
    verify: Optional[str],
    metric_name: Optional[str],
    direction: Optional[str],
    repeats: Optional[int],
    noise_floor: Optional[float],
    guard: Optional[str],
) -> list[str]:
    """Explicit flags that would make the run measure something other than its leg.

    Deriving is a default, but a *contradiction* is not: a run initialised on a leg
    while measuring another command, direction or floor produces a record that
    disagrees with its own objective. Equal values are fine — the flag is a restatement.
    """
    where = f"leg {leg.get('name')!r} of objective {leg.get('objective_id')!r}"
    problems: list[str] = []
    if verify and verify.strip() != str(leg.get("command") or "").strip():
        problems.append(f"--verify {verify!r} is not the leg's command {leg.get('command')!r}")
    if metric_name and metric_name.strip() != str(leg.get("name") or ""):
        problems.append(f"--metric-name {metric_name!r} is not the leg's name {leg.get('name')!r}")
    if direction is not None and direction != leg.get("direction"):
        problems.append(f"--direction {direction!r} is not the leg's {leg.get('direction')!r}")
    if repeats is not None and int(repeats) != int(leg.get("repeats") or 0):
        problems.append(f"--repeats {repeats!r} is not the leg's {leg.get('repeats')!r}")
    if noise_floor is not None and float(noise_floor) != float(leg.get("noise_floor") or 0.0):
        problems.append(
            f"--noise-floor {noise_floor:g} is not the leg's {float(leg.get('noise_floor') or 0.0):g}"
        )
    if guard is not None and guard.strip() != str(leg.get("guard") or "").strip():
        problems.append(f"--guard {guard!r} is not the leg's {leg.get('guard')!r}")
    if problems:
        return [f"{item} ({where})" for item in problems]
    return problems


def init_run(
    *,
    repo: os.PathLike | str,
    verify: Optional[str] = None,
    metric_name: Optional[str] = None,
    direction: Optional[str] = None,
    scope: Sequence[str],
    guard: Optional[str] = None,
    target: Optional[float] = None,
    noise_floor: Optional[float] = None,
    repeats: Optional[int] = None,
    verify_timeout: float = DEFAULT_VERIFY_TIMEOUT,
    guard_timeout: float = DEFAULT_GUARD_TIMEOUT,
    protect: Sequence[str] = (),
    program: Optional[str] = None,
    goal: Optional[str] = None,
    force: bool = False,
    state: Optional[os.PathLike | str] = None,
    objective: Optional[str] = None,
    objective_leg: Optional[str] = None,
) -> RunConfig:
    """Validate the target repo and write its ``run.json`` (in ``--state-dir``)."""
    root = require_git_repo(repo)
    require_branch(root)
    require_clean(root)

    leg, objective_path = None, None
    if objective:
        try:
            loaded = objective_mod.load(objective)
            leg = objective_mod.resolve_leg(loaded, leg=objective_leg)
        except objective_mod.ObjectiveError as exc:
            raise ConfigError(f"--objective: {exc}") from exc
        objective_path = objective_mod.record_path(objective).resolve()
        contradictions = _leg_contradictions(
            leg,
            verify=verify,
            metric_name=metric_name,
            direction=direction,
            repeats=repeats,
            noise_floor=noise_floor,
            guard=guard,
        )
        if contradictions:
            raise ConfigError(
                "--objective: an explicit flag cannot contradict the leg it names: "
                + "; ".join(contradictions)
            )

    verify = (verify or (leg or {}).get("command") or "").strip()
    if not verify:
        raise ConfigError("--verify must be a command (or --objective names a leg with one)")
    metric_name = (metric_name or (leg or {}).get("name") or "").strip()
    if not metric_name or " " in metric_name:
        raise ConfigError("--metric-name must be a single token")
    direction = direction or (leg or {}).get("direction")
    if direction not in DIRECTIONS:
        raise ConfigError(f"--direction must be one of {DIRECTIONS}")
    if noise_floor is None:
        noise_floor = float((leg or {}).get("noise_floor", DEFAULT_NOISE_FLOOR))
    if repeats is None:
        repeats = int((leg or {}).get("repeats", DEFAULT_REPEATS))
    guard = guard or (leg or {}).get("guard")
    if not math.isfinite(noise_floor) or noise_floor < 0:
        raise ConfigError("--noise-floor must be a finite number >= 0")
    if target is not None and not math.isfinite(target):
        raise ConfigError("--target must be a finite number")
    if repeats < 1:
        raise ConfigError("--repeats must be >= 1")
    if not math.isfinite(verify_timeout) or not math.isfinite(guard_timeout):
        # nan/inf make a bound meaningless: `nan <= 0` is False, so the check
        # below would have waved them through.
        raise ConfigError("timeouts must be finite numbers > 0")
    if verify_timeout <= 0 or guard_timeout <= 0:
        raise ConfigError("timeouts must be > 0")
    if not scope:
        raise ConfigError("at least one --scope is required")

    scopes = normalize_scope(root, scope)

    protected = default_protected(root, (verify, guard))
    for raw in protect:
        rel = normalize_scope(root, [raw])[0]
        path = root / rel
        if not path.is_file():
            raise ConfigError(f"--protect {raw!r} is not a file")
        protected[rel] = hash_file(path)

    program_text, program_path = _read_program(root, program)

    # Archiving is destructive (it moves the previous run aside), so it happens
    # only once every argument above has validated: a typo in --protect must not
    # cost the operator the run it was meant to replace.
    where = state_dir(root, state)
    if run_json_path(root, state).exists() and not force:
        raise ConfigError(
            f"{run_json_path(root, state)} already exists — pass --force to archive it "
            "and start a new run"
        )
    if run_json_path(root, state).exists():
        archive_state(root, state)

    cfg = RunConfig(
        repo=str(root),
        verify=verify,
        metric_name=metric_name,
        direction=direction,
        scope=scopes,
        guard=(guard or "").strip() or None,
        target=target,
        noise_floor=float(noise_floor),
        repeats=int(repeats),
        verify_timeout=float(verify_timeout),
        guard_timeout=float(guard_timeout),
        protected=dict(sorted(protected.items())),
        program=program_text,
        program_path=program_path,
        goal=goal,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        state=str(where) if state else None,
        objective=str(objective_path) if objective_path else None,
        objective_id=(leg or {}).get("objective_id"),
        objective_leg=(leg or {}).get("name"),
        objective_unit=(leg or {}).get("unit"),
    )

    where.mkdir(parents=True, exist_ok=True)
    # The state directory ignores itself, so a run never pollutes `git status`
    # and the loop never mistakes its own bookkeeping for a candidate change.
    (where / ".gitignore").write_text(GITIGNORE_BODY, encoding="utf-8")
    _write_json(where / RUN_JSON, cfg.as_dict())
    return cfg
