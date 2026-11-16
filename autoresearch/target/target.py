"""The target-profile contract: the measured checkout is a parameter.

A harness that scores another repository keeps two halves apart. The files it
needs **in order to score** — the engine, the evaluator, the guard command and
the state a round leaves — belong to the harness and resolve here whatever
checkout is named. Everything a round **measures** — the program, the scopes,
the protected list, the target's own scripts — resolves inside that checkout.

A profile declares both halves, and its ``$comment`` states which key is on which
side so a reader cannot mis-guess. A target is a **declared name**
(``autoresearch/targets/<name>.json``), never a filesystem path: a traversal-shaped
or undeclared name is refused with the reason before any state is read.
"""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

TARGET_DIR = Path(__file__).resolve().parent
#: The repository this module ships in — what a harness-relative key resolves against.
HARNESS_REPO = TARGET_DIR.parents[1]
#: Every declared profile, one file per name, beside this module — not inside it.
TARGETS_DIR = TARGET_DIR.parent / "targets"
TARGET_ENV = "AUTORESEARCH_TARGET_REPO"
PROFILE_ENV = "AUTORESEARCH_TARGET_PROFILE"
#: The evaluator invocation: the referee prints one ``METRIC <name>=<value>`` line
#: for the checkout, so a reading never depends on the process's working directory.
VERIFY_TEMPLATE = "python3 {referee} --target-repo {target}"
COMMENT_KEY = "$comment"
HARNESS_KEYS = ("engine", "referee", "guard_command", "runs_dir")
TARGET_KEYS = (
    "program",
    "scopes",
    "protected",
    "docker_free_tier",
    "e2e_dir",
    "context_dir",
    "dockerfile",
    "fresh_script",
    "guard_steps",
    "fresh_instruction",
    "arena_test_files",
)
#: Declarative, neither harness nor target: they describe the measurement, not a path.
SCALAR_KEYS = ("name", "metric_name", "direction")
PROFILE_KEYS = (COMMENT_KEY, *SCALAR_KEYS, *HARNESS_KEYS, *TARGET_KEYS)
DIRECTIONS = ("higher", "lower")
#: Optional target keys may ship as ``""`` (present but not configured).
OPTIONAL_TARGET_KEYS = (
    "program",
    "docker_free_tier",
    "e2e_dir",
    "context_dir",
    "dockerfile",
    "fresh_script",
    "fresh_instruction",
)


class TargetError(RuntimeError):
    """A target or profile that cannot be used; the message carries the reason."""


def resolve_target(
    flag: str | None = None,
    environ: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
) -> Path:
    """The checkout a round measures: the flag, else the env, else ``cwd``.

    Pure and resolved before any state is read, so the order is testable with no
    git repo and no process environment.
    """
    env = os.environ if environ is None else environ
    raw = (flag or "").strip() or (env.get(TARGET_ENV) or "").strip()
    return Path(raw).expanduser().resolve() if raw else Path(cwd or Path.cwd()).resolve()


def _refuse_name(text: str) -> str | None:
    """The reason a profile name cannot be a name, or ``None`` when it can."""
    if not text:
        return "no target profile named — pass a declared name, not a path"
    if text in (".", "..") or text.startswith("~"):
        return f"target profile {text!r} is traversal-shaped"
    if "/" in text or "\\" in text or "\x00" in text:
        return f"target profile {text!r} is a path, not a declared name"
    if text.endswith(".json"):
        return f"target profile {text!r} names a file — pass {text[:-5]!r}, the declared name"
    return None


def profile_path(name: str | None = None, targets: Path | str | None = None) -> Path:
    """The file a declared profile name names, or a refusal carrying the reason."""
    text = (name or "").strip()
    reason = _refuse_name(text)
    if reason:
        raise TargetError(reason + "; a target is declared under autoresearch/targets/<name>.json")
    root = Path(targets or TARGETS_DIR)
    path = root / f"{text}.json"
    if not path.is_file():
        declared = ", ".join(sorted(p.stem for p in root.glob("*.json"))) or "none"
        raise TargetError(f"target profile {text!r} is not declared under {root} (declared: {declared})")
    return path


def load_profile(
    name: str | None = None,
    environ: Mapping[str, str] | None = None,
    targets: Path | str | None = None,
) -> dict[str, Any]:
    """One declared profile as a dict; a half-described target never reaches a round.

    A profile that cannot be read, is not an object, is missing a key this schema
    requires, or calls itself something other than the name it is declared under
    is refused **by name** before any state is read.
    """
    env = os.environ if environ is None else environ
    chosen = (name or "").strip() or (env.get(PROFILE_ENV) or "").strip()
    path = profile_path(chosen, targets)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TargetError(f"cannot read target profile {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TargetError(f"target profile {path} is not a JSON object")
    missing = [key for key in PROFILE_KEYS if key not in data]
    if missing:
        raise TargetError(f"target profile {path} is missing {', '.join(missing)}")
    if str(data["name"]).strip() != path.stem:
        raise TargetError(
            f"target profile {path} calls itself {data['name']!r}; the name must be "
            f"{path.stem!r} — the name it is declared under"
        )
    return data


@dataclass(frozen=True)
class Resolution:
    """One profile bound to one checkout: both halves, and every refusal."""

    name: str
    profile_path: Path
    target: Path
    harness: Mapping[str, Any] = field(default_factory=dict)
    target_paths: Mapping[str, Any] = field(default_factory=dict)
    refused: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.refused

    def reasons(self) -> list[str]:
        return [f"{key}: {why}" for key, why in sorted(self.refused.items())]

    def relative(self, path: Path) -> str:
        return Path(path).relative_to(self.target).as_posix()

    def engine_argv(self) -> list[str]:
        """The engine invocation this profile resolves to — a plan, never a run."""
        if self.refused:
            raise TargetError("target profile refused — " + "; ".join(self.reasons()))
        argv = [
            str(self.harness["engine"]),
            "init",
            "--repo",
            str(self.target),
            # The round's state stays the harness's: the engine is told where,
            # so the measured checkout receives no `.autoresearch` at all.
            "--state-dir",
            str(Path(self.harness["runs_dir"]) / "state"),
            "--verify",
            self.harness["verify"],
            "--guard",
            self.harness["guard_command"],
            "--metric-name",
            self.harness["metric_name"],
            "--direction",
            self.harness["direction"],
        ]
        for rel in self._scopes():
            argv += ["--scope", rel]
        for path in self.target_paths["protected"]:
            argv += ["--protect", self.relative(path)]
        if self.target_paths["program"]:
            argv += ["--program", self.relative(self.target_paths["program"])]
        return argv

    def _scopes(self) -> list[str]:
        seen: list[str] = []
        for paths in self.target_paths["scopes"].values():
            for path in paths:
                rel = self.relative(path)
                if rel not in seen:
                    seen.append(rel)
        return seen


def _quote(path: Path) -> str:
    return shlex.quote(str(path))


def _fill(template: str, referee: Path, target: Path) -> str:
    return template.replace("{referee}", _quote(referee)).replace("{target}", _quote(target))


def _harness_path(key, raw, refused, root: Path, *, inside: bool = False) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        refused[key] = "must be a non-empty path string"
        return None
    path = Path(raw.strip())
    if path.is_absolute():
        resolved = path.resolve()
        # A tool may live anywhere (an adopter's evaluator outside this tree); the
        # state a round leaves may not, or the harness owns nothing.
        if inside and root not in resolved.parents:
            refused[key] = (
                f"{raw!r} is not a directory under the harness repo — state is harness-owned"
            )
            return None
        return resolved
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        refused[key] = f"{raw!r} escapes the harness repo — name it here, not by traversal"
        return None
    return resolved


def _target_path(key, raw, target: Path, refused, *, optional: bool = False) -> Path | None:
    if not isinstance(raw, str):
        refused[key] = "must be a path string relative to the target"
        return None
    text = raw.strip()
    if not text:
        if optional:
            return None
        refused[key] = "must not be empty"
        return None
    path = Path(text)
    if path.is_absolute():
        refused[key] = f"{text!r} is absolute — a target key resolves inside the checkout"
        return None
    if ".." in path.parts:
        refused[key] = f"{text!r} contains '..' — a target key stays inside the checkout"
        return None
    resolved = (target / path).resolve()
    try:
        resolved.relative_to(target)
    except ValueError:
        refused[key] = f"{text!r} escapes the target checkout"
        return None
    return resolved


def _target_list(key, raw, target: Path, refused) -> tuple[Path, ...]:
    if not isinstance(raw, list):
        refused[key] = "must be a list of target-relative paths (empty is honest)"
        return ()
    out: list[Path] = []
    for index, item in enumerate(raw):
        path = _target_path(f"{key}[{index}]", item, target, refused)
        if path is not None:
            out.append(path)
    return tuple(out)


def _scopes(raw, target: Path, refused) -> dict[str, tuple[Path, ...]]:
    if not isinstance(raw, dict) or not raw:
        refused["scopes"] = "must be a non-empty object of leg → [target-relative paths]"
        return {}
    legs: dict[str, tuple[Path, ...]] = {}
    for leg, paths in raw.items():
        if not isinstance(paths, list) or not paths:
            refused[f"scopes.{leg}"] = "must be a non-empty list of target-relative paths"
            continue
        legs[str(leg)] = _target_list(f"scopes.{leg}", paths, target, refused)
    return legs


def _guard_steps(raw, refused) -> tuple[tuple[str, tuple[str, ...], float], ...]:
    if not isinstance(raw, list):
        refused["guard_steps"] = "must be a list of [name, argv, timeout] (empty is honest)"
        return ()
    steps = []
    for index, step in enumerate(raw):
        key = f"guard_steps[{index}]"
        if (
            not isinstance(step, list)
            or len(step) != 3
            or not isinstance(step[0], str)
            or not isinstance(step[1], list)
            or not all(isinstance(arg, str) for arg in step[1])
            or not isinstance(step[2], (int, float))
        ):
            refused[key] = "must be [name, [argv...], timeout_seconds]"
            continue
        steps.append((step[0], tuple(step[1]), float(step[2])))
    return tuple(steps)


def apply_profile(
    profile: Mapping[str, Any],
    target: Path | str,
    path: Path | str | None = None,
) -> Resolution:
    """Bind one profile to one checkout, by relativity, refusing each bad key.

    Per-key problems are returned in ``refused`` with the reason rather than
    raised one at a time: a caller can report every misdescribed key in a single
    pass, and a profile is never half-applied.
    """
    root = HARNESS_REPO.resolve()
    checkout = Path(target).expanduser().resolve()
    name = str(profile.get("name", "")).strip()
    profile_file = Path(path).resolve() if path else (TARGETS_DIR / f"{name}.json")
    refused: dict[str, str] = {}
    if name and name != profile_file.stem:
        refused["name"] = f"{name!r} is not the name it is declared under ({profile_file.stem!r})"
    for key in profile:
        if key not in PROFILE_KEYS:
            refused[str(key)] = "not a declared profile key"

    harness: dict[str, Any] = {
        "engine": _harness_path("engine", profile.get("engine"), refused, root),
        "referee": _harness_path("referee", profile.get("referee"), refused, root),
        "runs_dir": _harness_path(
            "runs_dir", profile.get("runs_dir"), refused, root, inside=True
        ),
    }
    guard = profile.get("guard_command")
    if not isinstance(guard, str) or "{referee}" not in guard or "{target}" not in guard:
        refused["guard_command"] = "must be a template naming {referee} and {target}"
        harness["guard_command"] = ""
    else:
        harness["guard_command"] = guard

    metric = profile.get("metric_name")
    if not isinstance(metric, str) or not metric.strip() or " " in metric.strip():
        refused["metric_name"] = "must be a single token"
        harness["metric_name"] = ""
    else:
        harness["metric_name"] = metric.strip()
    direction = profile.get("direction")
    if direction not in DIRECTIONS:
        refused["direction"] = f"must be one of {', '.join(DIRECTIONS)}"
        harness["direction"] = ""
    else:
        harness["direction"] = direction

    if harness.get("referee"):
        harness["verify"] = _fill(VERIFY_TEMPLATE, harness["referee"], checkout)
    else:
        harness["verify"] = ""
    if isinstance(guard, str) and harness.get("referee"):
        harness["guard_command"] = _fill(guard, harness["referee"], checkout)

    target_paths: dict[str, Any] = {}
    for key in OPTIONAL_TARGET_KEYS:
        if key == "fresh_instruction":
            value = profile.get(key)
            if not isinstance(value, str):
                refused[key] = "must be a string (empty is honest)"
                target_paths[key] = ""
            else:
                target_paths[key] = value.strip()
            continue
        target_paths[key] = _target_path(
            key, profile.get(key), checkout, refused, optional=True
        )
    target_paths["scopes"] = _scopes(profile.get("scopes"), checkout, refused)
    target_paths["protected"] = _target_list("protected", profile.get("protected"), checkout, refused)
    target_paths["arena_test_files"] = _target_list(
        "arena_test_files", profile.get("arena_test_files"), checkout, refused
    )
    target_paths["guard_steps"] = _guard_steps(profile.get("guard_steps"), refused)

    if not isinstance(profile.get(COMMENT_KEY), list) or not all(
        isinstance(line, str) for line in profile.get(COMMENT_KEY, [])
    ):
        refused[COMMENT_KEY] = "must state the relativity split as a list of lines"

    return Resolution(
        name=name,
        profile_path=profile_file,
        target=checkout,
        harness=harness,
        target_paths=target_paths,
        refused=refused,
    )
