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
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import gitops

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
DEFAULT_REPEATS = 1
DEFAULT_VERIFY_TIMEOUT = 600.0
DEFAULT_GUARD_TIMEOUT = 600.0
DIRECTIONS = ("lower", "higher")


class ConfigError(Exception):
    """A configuration or precondition problem. The CLI maps it to exit 2."""


# ─── path helpers ────────────────────────────────────────────────────────────


def state_dir(repo: os.PathLike | str) -> Path:
    return Path(repo) / STATE_DIR


def run_json_path(repo: os.PathLike | str) -> Path:
    return state_dir(repo) / RUN_JSON


@contextlib.contextmanager
def state_lock(repo: os.PathLike | str):
    """Hold ``.autoresearch/lock`` while a command mutates the run.

    Two runs on one repo would interleave commits and resets, so the second one
    is refused rather than queued: an operator who starts a run by mistake wants
    to be told, not to wait. The lock is advisory (``flock``) and released when
    the descriptor closes, including on an exception or a Ctrl-C.
    """
    if fcntl is None:  # pragma: no cover - POSIX-only engine
        yield
        return
    path = state_dir(repo) / LOCK_FILE
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

    # -- views ---------------------------------------------------------------

    @property
    def state_dir(self) -> Path:
        return state_dir(self.repo)

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
            )
        except KeyError as exc:
            raise ConfigError(f"run.json is missing the field {exc.args[0]!r}") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"run.json is malformed: {exc}") from exc


def load(repo: os.PathLike | str) -> RunConfig:
    """Read ``.autoresearch/run.json``; a missing file is a config error."""
    path = run_json_path(repo)
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


def archive_state(root: Path) -> Path:
    """Move the existing state aside into ``.autoresearch/archive/<ts>/``."""
    state = state_dir(root)
    dest = _unique_dir(state / "archive")
    for entry in sorted(state.iterdir()):
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


def init_run(
    *,
    repo: os.PathLike | str,
    verify: str,
    metric_name: str,
    direction: str,
    scope: Sequence[str],
    guard: Optional[str] = None,
    target: Optional[float] = None,
    noise_floor: float = DEFAULT_NOISE_FLOOR,
    repeats: int = DEFAULT_REPEATS,
    verify_timeout: float = DEFAULT_VERIFY_TIMEOUT,
    guard_timeout: float = DEFAULT_GUARD_TIMEOUT,
    protect: Sequence[str] = (),
    program: Optional[str] = None,
    goal: Optional[str] = None,
    force: bool = False,
) -> RunConfig:
    """Validate the target repo and write ``.autoresearch/run.json``."""
    root = require_git_repo(repo)
    require_branch(root)
    require_clean(root)

    verify = (verify or "").strip()
    if not verify:
        raise ConfigError("--verify must be a command")
    metric_name = (metric_name or "").strip()
    if not metric_name or " " in metric_name:
        raise ConfigError("--metric-name must be a single token")
    if direction not in DIRECTIONS:
        raise ConfigError(f"--direction must be one of {DIRECTIONS}")
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
    if run_json_path(root).exists() and not force:
        raise ConfigError(
            f"{run_json_path(root)} already exists — pass --force to archive it "
            "and start a new run"
        )
    if run_json_path(root).exists():
        archive_state(root)

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
    )

    state = state_dir(root)
    state.mkdir(parents=True, exist_ok=True)
    # The state directory ignores itself, so a run never pollutes `git status`
    # and the loop never mistakes its own bookkeeping for a candidate change.
    (state / ".gitignore").write_text(GITIGNORE_BODY, encoding="utf-8")
    _write_json(run_json_path(root), cfg.as_dict())
    return cfg
