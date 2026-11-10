"""The workloads the service may execute, and where they live (PRD-20 SC2/SC4).

A workload is **bundled**: the caller names one and the service copies it into a
per-job repo. No request field is a directory, so a caller can never point the
service at host code — the registry is the whole allowlist, and an unknown name
is a ``ValueError`` (REST 400).

Each entry is the engine's run configuration for that source tree: the verify
and guard commands, the metric, the direction, the scope the agent may edit, and
the files that must not change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: File types copied from a workload source dir into a run repo. ``.md`` is
#: included because a workload may ship a ``program.md`` of standing
#: instructions; nothing else in a workload dir is executable code.
COPY_SUFFIXES = (".py", ".md")

#: Default bound on one verify/guard run, in seconds (the research runner's old
#: ``RESEARCH_RUN_TIMEOUT`` budget, now handed to the engine as a timeout).
DEFAULT_RUN_TIMEOUT = 30.0


def resolve_workload_dir() -> Path:
    """Locate the bundled contract source tree.

    Priority:
      1. ``$RESEARCH_WORKLOAD_DIR`` — explicit override (a custom workload).
      2. ``<autoresearch-root>/contract`` — source checkout: the engine, the
         contract and the service share one root (``autoresearch/``).
      3. ``/app/contract`` — the image's COPY of the contract, and the compose
         read-only mount, which is where it resolves when the package is
         installed instead of imported from the source tree.
    """
    env_dir = os.environ.get("RESEARCH_WORKLOAD_DIR")
    if env_dir:
        return Path(env_dir)
    here = Path(__file__).resolve()
    for candidate in (here.parents[2] / "contract", Path("/app/contract")):
        if candidate.is_dir() and (candidate / "prepare.py").is_file():
            return candidate
    return here.parents[1] / "workload"


def run_timeout() -> float:
    """Wall-clock bound for one verify/guard run (``RESEARCH_RUN_TIMEOUT``).

    Read per call, not at import, so a test — or an operator changing the
    budget — changes the next run rather than the next process.
    """
    return float(os.environ.get("RESEARCH_RUN_TIMEOUT", DEFAULT_RUN_TIMEOUT))


@dataclass(frozen=True)
class Workload:
    """One bundled research workload and the engine config it implies."""

    name: str
    source_dir: Path
    verify: str
    metric_name: str
    direction: str
    scope: tuple[str, ...]
    guard: str | None = None
    noise_floor: float = 0.01
    protect: tuple[str, ...] = ()
    program: str | None = None


_SPECS: dict[str, dict] = {
    "contract": {
        # `-m train` rather than `train.py`: the engine protects every file named
        # as a path token in verify/guard, and train.py is exactly the file the
        # agent edits here — naming it as a path would revert every candidate as
        # a protected violation. The module form runs the same file, prints the
        # same `val_bpb:` summary, and leaves prepare.py (the evaluator) as the
        # one protected file.
        "verify": "python3 -m train",
        "guard": "python3 prepare.py",
        "metric_name": "val_bpb",
        "direction": "lower",
        "scope": ("train.py",),
        "noise_floor": 0.001,
        "protect": ("prepare.py",),
        "program": "program.md",
    },
}


def known_workloads() -> tuple[str, ...]:
    """The names accepted by the API (``run_start``'s ``workload``)."""
    return tuple(sorted(_SPECS))


def get_workload(name: str) -> Workload:
    """The bundled workload called ``name``; ``ValueError`` when it is not one.

    A dict hit, not a path join: ``../../etc`` and ``/tmp`` miss like any other
    unknown name, so no request can name a directory.
    """
    spec = _SPECS.get(name) if isinstance(name, str) else None
    if spec is None:
        raise ValueError(
            f"unknown workload {name!r}; bundled workloads: {', '.join(known_workloads())}"
        )
    return Workload(name=name, source_dir=resolve_workload_dir(), **spec)
