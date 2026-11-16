"""The objective record: what a run optimises, as tracked data rather than a constant.

Downstream learned this at season 17: the game was a constant in code, so it could
be narrowed but never continued, and every earlier season stayed recorded against
an objective that no longer existed anywhere to be read. A *record* can be forked,
retired and archived while the results it produced stay comparable.

One record declares every objective, each with its priced legs and weights, the
periods (seasons, rounds) it owns, and the reason it was forked or retired. The
validation rules are not hygiene: each refuses a record that would load and still
play while paying for something nobody can measure. Every problem is returned at
once so a hand-edited record is fixed in one pass.

The template engine still measures one metric per ``init``. A leg here *feeds*
that driver: :func:`resolve_leg` returns the ``--verify``/``--metric-name``/
``--direction``/``--repeats``/``--noise-floor`` arguments ``init`` takes, and a
single leg at weight 1.0 is the degenerate case, not a special one.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional

HERE = Path(__file__).resolve().parent
#: The harness this module ships in — an objective is the harness's record, never
#: the measured checkout's, so the default resolves here whatever repo is scored.
HARNESS_REPO = HERE.parents[2]
DEFAULT_RECORD = HARNESS_REPO / "autoresearch" / "objective" / "registry.json"

DIRECTIONS = ("lower", "higher")
STATUSES = ("active", "retired", "archived")
WEIGHT_FLOOR = 0.5
WEIGHT_CEILING = 3.0

#: A leg is a contract: with no command it cannot be re-measured, with no floor
#: every move would count as a win. ``guard`` may be empty, but must be present.
REQUIRED_LEG_FIELDS = (
    "name",
    "direction",
    "unit",
    "command",
    "repeats",
    "noise_floor",
    "guard",
)
REQUIRED_OBJECTIVE_FIELDS = ("id", "parent", "status", "legs", "weights")

#: The pinned denominator: the commit a leg's baseline is read at, and the trio that
#: splits it. Validated here so a run's record cannot inherit a trio nobody checked.
BASELINE_KEYS = ("commit", "declared", "credited", "uncovered")
TRIO_KEYS = ("declared", "credited", "uncovered")


class ObjectiveError(RuntimeError):
    """A record that cannot be read or used; the message carries every reason."""


class ObjectiveReadError(ObjectiveError):
    """The file could not be opened at all — an operator error, not a bad record."""


def record_path(path: Optional[Path | str] = None) -> Path:
    """The file to read: the argument, else the tracked default beside the harness."""
    return DEFAULT_RECORD if path is None else Path(path).expanduser()


def read(path: Optional[Path | str] = None) -> dict[str, Any]:
    """Read the file without judging it: an operator error stops here, naming the path."""
    file = record_path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        # Missing or unreadable is the operator's path, not the record's content:
        # the CLI answers it with the config exit code, never "invalid record".
        raise ObjectiveReadError(f"cannot read {file}: {exc}") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ObjectiveError(f"{file} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ObjectiveError(f"{file} is not a JSON object")
    return data


def load(path: Optional[Path | str] = None) -> dict[str, Any]:
    """Read and validate; refuse with **every** contradiction, never the first."""
    data = read(path)
    problems = validate(data)
    if problems:
        raise ObjectiveError(f"{record_path(path)}: " + "; ".join(problems))
    return data


def _label(objective: Mapping[str, Any], index: int) -> str:
    oid = objective.get("id")
    return oid if isinstance(oid, str) and oid.strip() else f"#{index}"


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(float(value)) else None


def at_floor(leg: Mapping[str, Any]) -> Optional[bool]:
    """Whether a leg reads at its structural floor, or ``None`` when unmeasured.

    ``best`` is the last measured value and ``floor`` the value beyond which the
    leg cannot improve. Both are optional because a record can be written before
    the first measurement; once both are present the question has one answer.
    """
    best, floor = _number(leg.get("best")), _number(leg.get("floor"))
    if best is None or floor is None:
        return None
    return best <= floor if leg.get("direction") != "higher" else best >= floor


def _baseline_problems(label: str, baseline: Any, objective_label: str) -> list[str]:
    """A leg's pinned baseline: known keys, a commit name, a trio that adds up."""
    where = f"leg {label!r} of objective {objective_label!r}"
    if not isinstance(baseline, Mapping):
        return [f"{where} has a 'baseline' value that is not an object"]
    problems = [
        f"{where} declares baseline key {key!r}, which is not one of "
        f"{'/'.join(BASELINE_KEYS)}"
        for key in baseline
        if key not in BASELINE_KEYS
    ]
    if "commit" in baseline:
        commit = baseline.get("commit")
        if not isinstance(commit, str) or not commit.strip():
            problems.append(f"{where} pins its baseline at {commit!r}, not a commit name")
    given = [key for key in TRIO_KEYS if key in baseline]
    if given and len(given) != len(TRIO_KEYS):
        problems.append(
            f"{where} records {len(given)} of declared/credited/uncovered — one "
            "number hides which half moved"
        )
    numbers = {key: _number(baseline.get(key)) for key in given}
    for key, number in numbers.items():
        if number is None:
            problems.append(f"{where} records baseline {key} {baseline.get(key)!r}, not a number")
    if len(given) == len(TRIO_KEYS):
        declared, credited, uncovered = (numbers[key] for key in TRIO_KEYS)
        if declared is not None and credited is not None and uncovered is not None:
            if declared != credited + uncovered:
                problems.append(
                    f"{where} declares {declared:g} but credits {credited:g} and leaves "
                    f"{uncovered:g} — the denominator does not add up"
                )
    return problems


def _leg_problems(objective_label: str, legs: Any, weights: Any) -> list[str]:
    """Rules for one objective's legs, their weights, and the rotation over them."""
    problems: list[str] = []
    if not isinstance(legs, list):
        return [f"objective {objective_label!r} has a 'legs' value that is not a list"]
    names: dict[str, int] = {}
    for index, leg in enumerate(legs, start=1):
        if not isinstance(leg, Mapping):
            problems.append(f"objective {objective_label!r} leg #{index} is not an object")
            continue
        name = leg.get("name")
        label = name if isinstance(name, str) and name.strip() else f"#{index}"
        if not isinstance(name, str) or not name.strip():
            problems.append(f"objective {objective_label!r} leg #{index} has no name")
        else:
            if name in names:
                problems.append(
                    f"leg {name!r} of objective {objective_label!r} is declared "
                    f"{names[name] + 1} times"
                )
            names[name] = names.get(name, 0) + 1
        missing = [field for field in REQUIRED_LEG_FIELDS if field not in leg]
        if missing:
            problems.append(
                f"leg {label!r} of objective {objective_label!r} has no "
                f"{'/'.join(missing)}"
            )
        if "direction" in leg and leg["direction"] not in DIRECTIONS:
            problems.append(
                f"leg {label!r} of objective {objective_label!r} declares direction "
                f"{leg['direction']!r}, not one of {'/'.join(DIRECTIONS)}"
            )
        repeats = _number(leg.get("repeats"))
        if "repeats" in leg and (repeats is None or repeats < 1 or repeats != int(repeats)):
            problems.append(
                f"leg {label!r} of objective {objective_label!r} has repeats "
                f"{leg.get('repeats')!r} (must be an integer >= 1)"
            )
        floor = leg.get("noise_floor")
        measured_floor = _number(floor)
        if "noise_floor" in leg and (measured_floor is None or measured_floor < 0):
            problems.append(
                f"leg {label!r} of objective {objective_label!r} has noise_floor "
                f"{floor!r} (must be finite and >= 0)"
            )
        command = leg.get("command")
        if "command" in leg and (not isinstance(command, str) or not command.strip()):
            problems.append(
                f"leg {label!r} of objective {objective_label!r} has no command — "
                "it cannot be re-measured"
            )
        if ("best" in leg) != ("floor" in leg):
            problems.append(
                f"leg {label!r} of objective {objective_label!r} records best without "
                "floor (or the reverse) — an at-floor check needs both"
            )
        if "baseline" in leg:
            problems.extend(
                _baseline_problems(str(label), leg.get("baseline"), objective_label)
            )

    if not isinstance(weights, Mapping):
        problems.append(f"objective {objective_label!r} has a 'weights' value that is not an object")
        weights = {}
    for key, weight in weights.items():
        if key not in names:
            problems.append(
                f"weight {key!r} of objective {objective_label!r} names no declared leg"
            )
        value = _number(weight)
        if value is None:
            problems.append(
                f"weight {key!r} of objective {objective_label!r} is {weight!r}, not a number"
            )
        elif not WEIGHT_FLOOR <= value <= WEIGHT_CEILING:
            problems.append(
                f"weight {key!r} of objective {objective_label!r} is {value:g}, outside "
                f"[{WEIGHT_FLOOR:g}, {WEIGHT_CEILING:g}]"
            )
    for name in names:
        if name not in weights:
            problems.append(
                f"leg {name!r} of objective {objective_label!r} has no weight — an "
                "unweighted leg is not priced"
            )
    return problems


def _rotation_problems(
    objective_label: str, legs: Any, rotation: Any
) -> list[str]:
    """A rotation must name exactly the playable legs, once each, and nothing at floor."""
    if not isinstance(legs, list):
        return []
    declared = {
        leg.get("name"): leg
        for leg in legs
        if isinstance(leg, Mapping) and isinstance(leg.get("name"), str)
    }
    playable = [name for name, leg in declared.items() if at_floor(leg) is not True]
    if rotation is None:
        return []
    if not isinstance(rotation, list) or not all(isinstance(name, str) for name in rotation):
        return [
            f"rotation of objective {objective_label!r} is not a list of leg names"
        ]
    problems: list[str] = []
    for name in rotation:
        if name not in declared:
            problems.append(
                f"rotation of objective {objective_label!r} names {name!r}, which is no leg"
            )
        elif at_floor(declared[name]) is True:
            problems.append(
                f"leg {name!r} of objective {objective_label!r} is at its floor "
                f"(best {_number(declared[name].get('best')):g} against floor "
                f"{_number(declared[name].get('floor')):g}) and is scheduled — a leg "
                "at its floor cannot pay"
            )
    if len(set(rotation)) != len(rotation):
        problems.append(f"rotation of objective {objective_label!r} repeats a leg")
    if len(rotation) != len(playable):
        problems.append(
            f"rotation of objective {objective_label!r} has {len(rotation)} leg(s) but "
            f"{len(playable)} is playable — a rotation longer than the legs it rotates "
            "gives one tick a second shot"
        )
    for name in playable:
        if name not in rotation:
            problems.append(
                f"rotation of objective {objective_label!r} drops playable leg {name!r}"
            )
    return problems


def _periods(objective: Mapping[str, Any], key: str, label: str) -> tuple[list[int], list[str]]:
    """The integer periods an objective claims, and any shape problem found."""
    listed = objective.get(key)
    if listed is None:
        return [], []
    if not isinstance(listed, list):
        return [], [f"objective {label!r} has a {key!r} value that is not a list"]
    problems = [
        f"objective {label!r} lists {key[:-1]} {item!r}, which is not an integer"
        for item in listed
        if isinstance(item, bool) or not isinstance(item, int)
    ]
    return [item for item in listed if isinstance(item, int) and not isinstance(item, bool)], problems


def validate(data: Any) -> list[str]:
    """Every rule, as short sentences naming the offender; ``[]`` when playable."""
    if not isinstance(data, Mapping):
        return ["the record is not a JSON object"]
    entries = data.get("objectives")
    if not isinstance(entries, list):
        return ["the record has no 'objectives' list"]
    problems: list[str] = []
    ids: dict[str, int] = {}
    seasons: dict[int, str] = {}
    rounds: dict[int, str] = {}
    active: list[str] = []

    for index, objective in enumerate(entries, start=1):
        if not isinstance(objective, Mapping):
            problems.append(f"objective #{index} is not an object")
            continue
        label = _label(objective, index)
        oid = objective.get("id")
        if not isinstance(oid, str) or not oid.strip():
            problems.append(f"objective #{index} has no id")
        else:
            if oid in ids:
                problems.append(f"objective id {oid!r} is declared {ids[oid] + 1} times")
            ids[oid] = ids.get(oid, 0) + 1
        missing = [field for field in REQUIRED_OBJECTIVE_FIELDS if field not in objective]
        if missing:
            problems.append(
                f"objective {label!r} has no {'/'.join(missing)}"
            )
        status = objective.get("status")
        if "status" in objective and status not in STATUSES:
            problems.append(
                f"objective {label!r} declares status {status!r}, not one of "
                f"{'/'.join(STATUSES)}"
            )
        legs = objective.get("legs")
        if status == "active":
            active.append(label)
            if not isinstance(legs, list) or not legs:
                problems.append(f"active objective {label!r} has no legs")
        problems.extend(_leg_problems(label, legs, objective.get("weights")))
        problems.extend(_rotation_problems(label, legs, objective.get("rotation")))
        for key, owned in (("seasons", seasons), ("rounds", rounds)):
            listed, shape = _periods(objective, key, label)
            problems.extend(shape)
            for period in listed:
                owner = owned.get(period)
                if owner is None:
                    owned[period] = label
                elif owner != label:
                    problems.append(
                        f"{key[:-1]} {period} is listed by both {owner!r} and {label!r}"
                    )
        reason = objective.get("reason")
        has_reason = isinstance(reason, str) and reason.strip()
        if objective.get("parent") is not None and not has_reason:
            problems.append(f"fork of {objective.get('parent')!r} into {label!r} has no reason")
        if status in ("retired", "archived") and not has_reason:
            problems.append(f"{status} objective {label!r} has no reason")

    if len(active) > 1:
        problems.append(
            f"{len(active)} objectives are active "
            f"({', '.join(repr(name) for name in active)}); a run plays exactly one"
        )
    parents: dict[str, Optional[str]] = {}
    for index, objective in enumerate(entries, start=1):
        if not isinstance(objective, Mapping):
            continue
        oid = objective.get("id")
        if not isinstance(oid, str) or not oid.strip():
            continue
        parent = objective.get("parent")
        if parent is None:
            parents[oid] = None
        elif isinstance(parent, str) and parent in ids:
            parents[oid] = parent
        else:
            problems.append(f"objective {oid!r} names parent {parent!r}, which is no objective")
            parents[oid] = None
    reported: set[str] = set()
    for start in parents:
        path: list[str] = []
        node: Optional[str] = start
        while node is not None and node not in path:
            path.append(node)
            node = parents.get(node)
        if node is None or node not in path:
            continue
        cycle = path[path.index(node):] + [node]
        if min(cycle) in reported:
            continue
        reported.add(min(cycle))
        problems.append("parent chain " + " -> ".join(repr(name) for name in cycle) + " is a cycle")
    return problems


def active(data: Mapping[str, Any]) -> dict[str, Any]:
    """The one objective a new run plays; refused unless exactly one is active."""
    found = [
        objective
        for objective in data.get("objectives") or []
        if isinstance(objective, Mapping) and objective.get("status") == "active"
    ]
    if len(found) != 1:
        raise ObjectiveError(
            f"found {len(found)} active objective(s); exactly one is played at a time"
        )
    return dict(found[0])


def _payload(objective: Mapping[str, Any], chosen: Mapping[str, Any]) -> dict[str, Any]:
    """One leg as the arguments a run takes; the weight travels with it."""
    weights = objective.get("weights") or {}
    return {
        "objective_id": objective.get("id"),
        "name": chosen.get("name"),
        "direction": chosen.get("direction"),
        "unit": chosen.get("unit"),
        "command": chosen.get("command"),
        "repeats": int(chosen["repeats"]),
        "noise_floor": float(chosen["noise_floor"]),
        "guard": chosen.get("guard") or None,
        "weight": float(weights.get(chosen.get("name"), 1.0)),
        # The pinned denominator travels with the leg: a run's record inherits it,
        # and an objective cannot pin a baseline the validator never saw.
        "baseline": dict(chosen.get("baseline") or {}),
    }


def find_leg(data: Mapping[str, Any], leg: Optional[str] = None) -> dict[str, Any]:
    """A declared leg by name, or the one playable leg, without re-judging the record.

    Kept apart from :func:`resolve_leg` because a close record reads the leg a run
    *was* initialised on: the record still has to be written after the objective has
    moved that leg to its floor.
    """
    objective = active(data)
    legs = [item for item in objective.get("legs") or [] if isinstance(item, Mapping)]
    if leg is None:
        playable = [item for item in legs if at_floor(item) is not True]
        if len(playable) != 1:
            raise ObjectiveError(
                f"objective {objective.get('id')!r} has {len(playable)} playable leg(s) "
                f"({', '.join(str(item.get('name')) for item in playable) or 'none'}); "
                "name one with --objective-leg"
            )
        return _payload(objective, playable[0])
    chosen = next((item for item in legs if item.get("name") == leg), None)
    if chosen is None:
        names = ", ".join(str(item.get("name")) for item in legs)
        raise ObjectiveError(
            f"leg {leg!r} is not declared by objective {objective.get('id')!r} "
            f"(declared: {names})"
        )
    return _payload(objective, chosen)


def resolve_leg(data: Mapping[str, Any], leg: Optional[str] = None) -> dict[str, Any]:
    """The leg a run measures, as the arguments ``init`` takes.

    A multi-leg objective needs the leg named: choosing one would be a silent
    substitution of one objective half for another. A leg at its floor is refused
    for the same reason the schedule drops it — it cannot pay.
    """
    problems = validate(data)
    if problems:
        raise ObjectiveError("; ".join(problems))
    return find_leg(data, leg)
