"""Git plumbing for the loop.

Every call is argv-only (never a shell string) and bounded by ``timeout=``. The
loop commits and resets, so nothing here is allowed to block on a prompt or on a
credential: ``GIT_TERMINAL_PROMPT=0`` is forced on.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

STATE_DIR = ".autoresearch"

#: Path components the engine never treats as a change: byte-compiled output is
#: a side effect of *running* a script, not an edit an agent made.
NOISE_DIRS = ("__pycache__",)
NOISE_SUFFIXES = (".pyc",)

#: Identity used for every commit the loop makes, so a run is attributable in
#: ``git log`` and never depends on the operator's git config.
AUTHOR_ENV: Dict[str, str] = {
    "GIT_AUTHOR_NAME": "autoresearch",
    "GIT_AUTHOR_EMAIL": "autoresearch@localhost",
    "GIT_COMMITTER_NAME": "autoresearch",
    "GIT_COMMITTER_EMAIL": "autoresearch@localhost",
}

DEFAULT_TIMEOUT = 120.0


class GitError(RuntimeError):
    """A git command failed."""


def _env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra:
        env.update(extra)
    return env


def git(
    repo: os.PathLike | str,
    *args: str,
    timeout: float = DEFAULT_TIMEOUT,
    check: bool = True,
    env_extra: Optional[Dict[str, str]] = None,
    input_text: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run one git command in ``repo``; raise :class:`GitError` when ``check``."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_env(env_extra),
            input=input_text,
        )
    except subprocess.TimeoutExpired as exc:
        # A hung git is a precondition failure like any other: the CLI owes the
        # operator exit 2, not a traceback from the middle of the loop.
        raise GitError(f"git {' '.join(args)} timed out after {timeout:g}s") from exc
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode})"
            + (f": {detail[-1]}" if detail else "")
        )
    return proc


def repo_root(path: os.PathLike | str) -> Path:
    """Resolve the worktree root of ``path``, or raise :class:`GitError`."""
    p = Path(path)
    proc = git(p, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise GitError(f"{p} is not a git repository")
    return Path(proc.stdout.strip())


def is_state_path(rel: str) -> bool:
    """True for anything under the engine's own state directory."""
    return rel == STATE_DIR or rel.startswith(STATE_DIR + "/")


def is_noise_path(rel: str) -> bool:
    """True for interpreter by-products (``__pycache__/``, ``*.pyc``)."""
    parts = rel.replace(os.sep, "/").split("/")
    return any(part in NOISE_DIRS for part in parts) or rel.endswith(NOISE_SUFFIXES)


def status_paths(repo: os.PathLike | str, *, timeout: float = 60.0) -> List[str]:
    """Changed paths (tracked modifications, staged changes, untracked files).

    ``.autoresearch/`` is excluded: the state directory ignores itself, and the
    loop must never treat its own bookkeeping as a candidate change.
    ``__pycache__``/``*.pyc`` are excluded for the same reason — running a script
    writes them, so they are never evidence of an agent's edit.
    """
    proc = git(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        timeout=timeout,
    )
    fields = proc.stdout.split("\0")
    paths: List[str] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        xy = entry[:2]
        paths.append(entry[3:])
        if "R" in xy or "C" in xy:
            i += 1  # the record carries a second NUL-separated source path
        i += 1
    return [p for p in paths if p and not is_state_path(p) and not is_noise_path(p)]


IgnoredSnapshot = Mapping[str, Tuple[Optional[int], Optional[int]]]


def ignored_snapshot(
    repo: os.PathLike | str, scopes: Sequence[str], *, timeout: float = 60.0
) -> Dict[str, Tuple[Optional[int], Optional[int]]]:
    """Ignored files under ``scopes`` with a cheap ``(size, mtime_ns)`` fingerprint.

    Ignored paths are invisible to :func:`status_paths`, so a write to one inside
    the scope looked like ``no_change``. A before/after snapshot is the only way
    to see it without asking git to track what it was told to ignore.
    """
    args = [
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored=matching",
    ]
    if scopes:
        args += ["--", *scopes]
    proc = git(repo, *args, timeout=timeout)
    snapshot: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
    for entry in proc.stdout.split("\0"):
        if not entry.startswith("!! "):
            continue
        rel = entry[3:]
        if not rel or is_state_path(rel) or is_noise_path(rel):
            continue
        try:
            stat = (Path(repo) / rel).lstat()
        except OSError:
            snapshot[rel] = (None, None)
            continue
        snapshot[rel] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def ignored_delta(before: IgnoredSnapshot, after: IgnoredSnapshot) -> Tuple[List[str], List[str]]:
    """``(changed, added)`` ignored paths between two snapshots.

    ``changed`` also covers a path that disappeared: the ignored set is part of
    what the scope promises, so removing one is a change like any other.
    """
    added = sorted(set(after) - set(before))
    changed = sorted(
        path for path, fingerprint in before.items() if after.get(path) != fingerprint
    )
    return changed, added


def is_clean(repo: os.PathLike | str) -> bool:
    return not status_paths(repo)


def branch(repo: os.PathLike | str) -> str:
    """Current branch name, or ``""`` when HEAD is detached."""
    proc = git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    name = proc.stdout.strip()
    return "" if name == "HEAD" else name


def head(repo: os.PathLike | str) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def add(repo, paths: Sequence[str], *, timeout: float = 60.0) -> None:
    if paths:
        git(repo, "add", "--", *paths, timeout=timeout)


def staged_diff(repo, base: str, *, timeout: float = 120.0) -> str:
    """Diff of the index against ``base`` — the candidate, new files included."""
    return git(repo, "diff", "--cached", base, timeout=timeout).stdout


def commit_staged(repo, message: str, *, timeout: float = 120.0) -> str:
    """Commit the index with the loop's identity; return the new commit sha."""
    git(repo, "commit", "--no-verify", "-m", message, timeout=timeout, env_extra=AUTHOR_ENV)
    return head(repo)


def reset_hard(repo, commit: str, *, timeout: float = 120.0) -> None:
    git(repo, "reset", "--hard", commit, timeout=timeout)


def clean_scopes(repo, scopes: Iterable[str], *, timeout: float = 120.0) -> None:
    """Remove untracked files *inside* the declared scopes only.

    ``git clean`` outside the scope would delete work the operator owns, so the
    scope prefixes are the whole argument list.
    """
    scopes = [s for s in scopes if s]
    if not scopes:
        return
    git(repo, "clean", "-fd", "--", *scopes, timeout=timeout)


def apply_patch(repo, patch: str, *, timeout: float = 120.0) -> subprocess.CompletedProcess:
    """Apply a recorded patch to the worktree (replay adapter).

    Replay is idempotent: a patch whose result is already in the worktree
    reverses cleanly, so re-applying it is a no-op rather than a failure — a
    record replayed from the post-keep commit yields ``no_change``. A patch that
    neither applies nor reverses stays a failure, so a genuine divergence from
    the recorded baseline is still reported as an agent error.
    """
    proc = git(
        repo,
        "apply",
        "--whitespace=nowarn",
        timeout=timeout,
        check=False,
        input_text=patch,
    )
    if proc.returncode == 0:
        return proc
    already = git(
        repo,
        "apply",
        "--reverse",
        "--check",
        timeout=timeout,
        check=False,
        input_text=patch,
    )
    if already.returncode == 0:
        return subprocess.CompletedProcess(
            args=proc.args, returncode=0, stdout="already applied\n", stderr=""
        )
    return proc
