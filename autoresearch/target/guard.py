"""The evaluator guard: hash what scores, at both ends of a round.

Keeping the evaluator outside the measured worktree bounds what a seat's *diff*
can reach; it does not detect a *write*. A seat runs as the same OS user and can
open an absolute path the worktree diff never sees, so the round hashes its
evaluator surface at the start, hashes it again before anything is settled, and
on any difference **voids the round** with the reason. Tampered files are left in
place as evidence — the guard never restores them and never writes.

Two reads bound what two reads can see: a write followed by a restore between
them is invisible, so the round claims change-detection, not a write bound.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

#: The target-profile modules are part of the surface: they resolve and guard a round.
EVALUATOR_SOURCE = ("target.py", "guard.py", "cli.py")
#: The event that already means "a protected file moved"; a round is charged it, not scored.
TAMPER_EVENT = "protected_violation"


class GuardError(RuntimeError):
    """A round that must not start, or whose settlement is void."""


def engine_files(engine: Path | str) -> tuple[Path, ...]:
    """The engine a round runs, file by file: its wrapper and every package module."""
    root = Path(engine).resolve().parent.parent
    return (root / "bin" / "autoresearch", *sorted((root / "autoresearch").glob("*.py")))


def evaluator_files(resolution: Any) -> tuple[Path, ...]:
    """Every file a round is scored by, all of them outside the measured checkout."""
    referee = resolution.harness.get("referee")
    engine = resolution.harness.get("engine")
    if not referee or not engine:
        raise GuardError("the resolution names no referee or no engine — nothing to guard")
    here = Path(__file__).resolve().parent
    files = [Path(referee), Path(resolution.profile_path)]
    files += [here / name for name in EVALUATOR_SOURCE]
    files += list(engine_files(engine))
    return tuple(dict.fromkeys(files))


def digest(paths: Iterable[Path | str]) -> dict[Path, str | None]:
    """A sha256 per file — ``None`` for one that is gone, never an omission.

    A missing file therefore compares as a change like any other, so deleting the
    evaluator cannot read as "no difference".
    """
    out: dict[Path, str | None] = {}
    for raw in paths:
        path = Path(raw)
        try:
            out[path] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        except OSError:
            out[path] = None
    return out


def tamper(
    before: Mapping[Path, str | None], after: Mapping[Path, str | None]
) -> dict[str, Any] | None:
    """The void record a round leaves when the evaluator moved, else ``None``."""
    changed = sorted(str(path) for path in {*before, *after} if before.get(path) != after.get(path))
    if not changed:
        return None
    return {
        "round": "void",
        "void": True,
        "event": TAMPER_EVENT,
        "reason": "the evaluator moved during the round: " + ", ".join(changed),
        "evaluator_tampered": changed,
    }


def _inside(path: Path | str, root: Path | str) -> bool:
    """True when ``path`` resolves to ``root`` or somewhere beneath it."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


@dataclass
class RoundGuard:
    """One round's evaluator hash, taken before the seats run and re-read at settle."""

    resolution: Any
    before: Mapping[Path, str | None] = field(default_factory=dict)

    @classmethod
    def start(cls, resolution: Any) -> "RoundGuard":
        """Open a round only when its evaluator is outside the checkout and present."""
        if not getattr(resolution, "ok", False):
            raise GuardError("target profile refused — " + "; ".join(resolution.reasons()))
        paths = evaluator_files(resolution)
        inside = [str(path) for path in paths if _inside(path, resolution.target)]
        if inside:
            raise GuardError(
                "refusing the round: evaluator file(s) inside the measured checkout — "
                + ", ".join(inside)
            )
        missing = [str(path) for path in paths if not Path(path).is_file()]
        if missing:
            raise GuardError("refusing the round: evaluator file(s) missing — " + ", ".join(missing))
        return cls(resolution=resolution, before=digest(paths))

    @property
    def paths(self) -> tuple[Path, ...]:
        return tuple(self.before)

    def settle(self) -> dict[str, Any] | None:
        """``None`` when the evaluator held; the void record when it did not."""
        return tamper(self.before, digest(self.paths))
