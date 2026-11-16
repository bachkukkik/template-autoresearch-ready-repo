"""The run record: what a finished run must leave, and the checks that keep it honest.

``report.md`` answers "what did this run do". A later reader's question is "is this
comparable to another run, and is any of the difference mine?" That needs the two
commits, the per-leg reading with the evaluator's own line, the keeps, and a verdict
that says whether the number moved because the work moved it (play) or because the
instrument moved under it (relocation).

Two artefacts, one source: ``record.json`` is the machine record and ``record.md``
its human view. Both are pure functions of the ledger and the run config, so
``--check`` re-renders and compares byte for byte. A ``pending`` run — one that has
not stopped — is refused: a record of an open run is a guess.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from . import config as config_mod
from . import ledger as ledger_mod
from . import measure as measure_mod
from . import objective as objective_mod

RECORD_JSON = "record.json"
RECORD_MD = "record.md"
RECORD_VERSION = 1
GIT_TIMEOUT = 30.0

VERDICTS = ("improved", "held", "displaced")
#: The verdict is a function of the record, never of a reviewer's memory. Definitions
#: come from kb/concepts/relocation-not-play.md: a move is classified by cause first.
VERDICT_DEFINITIONS = {
    "improved": "the leg moved, the work moved it, and the instrument did not",
    "held": "the reading did not move beyond the floor; the baseline stands",
    "displaced": "the number moved but the cost moved elsewhere (a shorter instrument, "
    "a pinned denominator, an upstream change) — relocation, not play",
}
REQUIRED_READING_FIELDS = (
    "name",
    "unit",
    "lower_is_better",
    "before",
    "after",
    "command",
    "raw",
    "verdict",
    "note",
)


class RecordError(RuntimeError):
    """A record that cannot be written or re-rendered; the message carries the reason."""


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _numbers(values: Any) -> list[float]:
    """Every finite number in a repeat series; anything else is dropped."""
    if not isinstance(values, (list, tuple)):
        return []
    return [number for number in (_number(item) for item in values) if number is not None]


#: Two readings of the same run agree to this; a raw line is a re-parse of a float.
TOLERANCE = 1e-9


def _state_label(repo: Any, state_dir: Any) -> str:
    """The state directory as a reader of the record sees it: repo-relative or basename.

    A record travels with the harness, so a host path in it is layout, not evidence.
    """
    label = Path(str(state_dir))
    try:
        relative = os.path.relpath(str(label), str(repo))
    except ValueError:
        return label.name
    return label.name if relative.startswith("..") else relative


def _g(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):g}"


def _short(commit: Any) -> str:
    return str(commit)[:12] if commit else "-"


def _cell(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def _objective_for(cfg) -> Optional[dict[str, Any]]:
    """The objective record a run names, or ``None`` for the degenerate single metric.

    A run that names an objective owes a record that resolves it: silently dropping
    the reference would make the close record's ``objective_id`` a memory.
    """
    if not getattr(cfg, "objective", None):
        return None
    try:
        return objective_mod.load(cfg.objective)
    except objective_mod.ObjectiveError as exc:
        raise RecordError(f"the run's objective record is unreadable: {exc}") from exc


def _leg_of(cfg, objective: Optional[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
    if objective is None:
        return None
    name = getattr(cfg, "objective_leg", None) or cfg.metric_name
    try:
        return objective_mod.find_leg(objective, leg=name)
    except objective_mod.ObjectiveError as exc:
        raise RecordError(f"the run's leg cannot be resolved: {exc}") from exc


def _keeps(trials: Sequence[dict], leg_name: str) -> list[dict]:
    return [
        {"commit": event.get("commit"), "round": event.get("iteration"), "leg": leg_name}
        for event in trials
        if event.get("outcome") == "keep"
    ]


def _mean_delta(trials: Sequence[dict], baseline: Optional[float]) -> Optional[float]:
    """The signed mean move per trial, replayed through the incumbents.

    Signed, not relative: a positive number is worse for a ``lower`` leg, and the
    record never flips a sign to make a loss read like a win.
    """
    incumbent, deltas = baseline, []
    for trial in trials:
        metric = _number(trial.get("metric"))
        if metric is not None and incumbent is not None:
            deltas.append(metric - incumbent)
        if trial.get("outcome") == "keep" and metric is not None:
            incumbent = metric
    return round(statistics.fmean(deltas), 6) if deltas else None


def _reading(
    leg_name: str,
    unit: Optional[str],
    cfg,
    before,
    after,
    raw: str,
    keeps,
    floor,
    series: Sequence[float] = (),
) -> dict:
    improved = bool(keeps) and before is not None and after is not None and after != before
    if improved:
        note = (
            f"kept at iteration {keeps[-1]['round']}: {_g(before)} -> {_g(after)} beyond "
            f"the {floor:g} floor; raw is the evaluator's own line"
        )
    else:
        note = (
            f"no trial cleared the {floor:g} floor; {_g(before)} stands at the "
            "baseline commit"
        )
    row = {
        "name": leg_name,
        "unit": unit,
        "lower_is_better": cfg.direction == "lower",
        "before": before,
        "after": after,
        "command": cfg.verify,
        "raw": raw,
        "verdict": "improved" if improved else "held",
        "note": note,
    }
    if len(series) > 1:
        # A reduced reading carries its repeats: `after` is their median, and the
        # gate re-derives that rather than trusting one line to speak for the series.
        row["values"] = list(series)
    return row


def build(cfg, events: Sequence[dict], objective: Optional[Mapping[str, Any]] = None) -> dict:
    """The close record for one run, derived from its ledger (never from prose)."""
    baseline = next((event for event in events if event.get("type") == "baseline"), None)
    trials = [event for event in events if event.get("type") == "trial"]
    stopped = any(event.get("type") == "stop" for event in events)
    leg = _leg_of(cfg, objective)
    leg_name = (leg or {}).get("name") or cfg.metric_name
    keep_events = [event for event in trials if event.get("outcome") == "keep"]
    keeps = _keeps(trials, leg_name)
    before = _number(baseline.get("metric")) if baseline else None
    after = _number(keep_events[-1].get("metric")) if keep_events else before
    parent_commit = baseline.get("commit") if baseline else None
    close_commit = keep_events[-1].get("commit") if keep_events else parent_commit
    improved_reading = keep_events[-1] if keep_events else (baseline or {})
    raw = improved_reading.get("raw") or ""
    series = _numbers(improved_reading.get("values"))
    declared = dict((leg or {}).get("baseline") or {})
    declared_weight = float((leg or {}).get("weight") or 1.0)
    active = objective_mod.active(objective) if objective else None
    mean = _mean_delta(trials, before)
    reason = (
        f"{len(keeps)} keep(s) of {len(trials)} trial(s); mean delta "
        f"{'n/a' if mean is None else f'{mean:+g}'} on {leg_name!r}; weight "
        f"{declared_weight:g} unchanged — this engine prices one leg per run"
    )
    record: dict[str, Any] = {
        "version": RECORD_VERSION,
        "pending": baseline is None or not stopped,
        "objective_id": getattr(cfg, "objective_id", None) or (leg or {}).get("objective_id"),
        "parent_commit": parent_commit,
        "close_commit": close_commit,
        "baselines": {
            leg_name: {
                "commit": parent_commit,
                "value": before,
                "pinned": declared.get("commit"),
                "declared": declared.get("declared"),
                "credited": declared.get("credited"),
                "uncovered": declared.get("uncovered"),
            }
        },
        "keeps": keeps,
        "readings": [
            _reading(leg_name, (leg or {}).get("unit"), cfg, before, after, raw, keeps,
                     cfg.noise_floor, series)
        ],
        "unmeasured_legs": [
            item.get("name")
            for item in (active or {}).get("legs") or []
            if isinstance(item, Mapping) and item.get("name") != leg_name
        ],
        "review": {
            "means": {leg_name: mean},
            "previous": {leg_name: declared_weight},
            "weights": {leg_name: declared_weight},
            "reason": reason,
        },
        "floor_before": cfg.noise_floor,
        "floor_after": cfg.noise_floor,
        "state_dir": _state_label(cfg.repo, cfg.state_dir),
        "provenance": _provenance_ref(trials),
    }
    return record


def _provenance_ref(trials: Sequence[dict]) -> Optional[dict]:
    """The provenance block of the last adjudicated decision — a reference, not a copy."""
    for event in reversed(list(trials)):
        if isinstance(event.get("provenance"), Mapping):
            return dict(event["provenance"])
    return None


def _is_ancestor(repo, commit: str, close: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, close],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    return proc.returncode == 0


def _series_problems(
    label: str, after: Optional[float], value: float, raw: str, series: Sequence[float]
) -> list[str]:
    """A reduced reading: ``after`` is the repeats' median and ``raw`` is that repeat.

    Re-deriving the reduction is stronger than trusting one line to speak for the
    series, and it is what makes a jittery metric recordable at all.
    """
    problems: list[str] = []
    median = statistics.median(series)
    middle = sorted(series)[(len(series) - 1) // 2]
    if after is None or abs(median - after) > TOLERANCE:
        problems.append(
            f"reading {label!r} says after {after} but its {len(series)} repeats have "
            f"median {median:g} — the point estimate is not the one recorded"
        )
    if abs(value - middle) > TOLERANCE:
        problems.append(
            f"reading {label!r} raw line says {value:g} but the median repeat measured "
            f"{middle:g}: {raw[:60]!r}"
        )
    return problems


def check(record: Mapping[str, Any], repo: Optional[Path | str] = None) -> list[str]:
    """Every honest-verdict check a record can answer mechanically; ``[]`` is clean.

    The rest of the downstream checklist needs a reader (was the unit actually
    served? was the loss artefact kept?) and stays in the PRD as the human list.
    """
    problems: list[str] = []
    if record.get("pending"):
        problems.append("the record is pending — the run has not stopped")
    commits: dict[str, str] = {}
    for name, base in sorted((record.get("baselines") or {}).items()):
        if not isinstance(base, Mapping):
            problems.append(f"baseline for leg {name!r} is not an object")
            continue
        if base.get("commit"):
            commits[name] = str(base["commit"])
        trio = (base.get("declared"), base.get("credited"), base.get("uncovered"))
        given = [value for value in trio if value is not None]
        if 0 < len(given) < 3:
            problems.append(
                f"leg {name!r} records {len(given)} of declared/credited/uncovered — "
                "one number hides which half moved"
            )
        elif len(given) == 3:
            declared, credited, uncovered = (_number(item) for item in trio)
            if declared is None or credited is None or uncovered is None:
                # `float(x or 0.0)` turned '1,027' into a passing 0.0: a gate must
                # name the label it cannot compare, not coerce it into a number.
                problems.append(
                    f"leg {name!r} records declared/credited/uncovered "
                    f"{trio!r}, and at least one is not a number — the denominator "
                    "cannot be checked"
                )
            elif declared != credited + uncovered:
                problems.append(
                    f"leg {name!r} declares {declared:g} but credits {credited:g} and "
                    f"leaves {uncovered:g} — the denominator does not add up"
                )
        pinned = base.get("pinned")
        if pinned and base.get("commit") and str(pinned) != str(base["commit"]):
            problems.append(
                f"leg {name!r} is pinned to {_short(pinned)} but measured at "
                f"{_short(base['commit'])}"
            )
    if len(set(commits.values())) > 1:
        named = ", ".join(f"{name}@{_short(sha)}" for name, sha in commits.items())
        problems.append(f"baseline commits differ across legs ({named}) — not comparable")

    readings = record.get("readings") or []
    if not readings:
        problems.append("the record has no readings")
    for row in readings:
        if not isinstance(row, Mapping):
            problems.append("a reading is not an object")
            continue
        label = row.get("name") or "?"
        missing = [field for field in REQUIRED_READING_FIELDS if field not in row]
        if missing:
            problems.append(f"reading {label!r} has no {'/'.join(missing)}")
        verdict = row.get("verdict")
        if verdict not in VERDICTS:
            problems.append(
                f"reading {label!r} declares verdict {verdict!r}, not one of "
                f"{'/'.join(VERDICTS)}"
            )
        if verdict in ("held", "displaced") and not str(row.get("note") or "").strip():
            problems.append(
                f"reading {label!r} is {verdict} with no note — a relocation without a "
                "note is an anecdote"
            )
        raw = row.get("raw")
        if not isinstance(raw, str) or not raw.strip():
            problems.append(
                f"reading {label!r} has no raw line — the evaluator's own output is missing"
            )
            continue
        value = measure_mod.parse_metric(raw, str(label))
        after = _number(row.get("after"))
        series = _numbers(row.get("values"))
        if value is None:
            problems.append(f"reading {label!r} raw line carries no {label!r} metric: {raw[:60]!r}")
        elif len(series) > 1:
            problems.extend(_series_problems(str(label), after, value, raw, series))
        elif after is not None and abs(value - after) > TOLERANCE:
            problems.append(
                f"reading {label!r} raw line says {value:g} but the record says {after:g}"
            )

    close = record.get("close_commit")
    if not close:
        problems.append("the record names no close commit")
    for keep in record.get("keeps") or []:
        commit = keep.get("commit")
        if not commit:
            problems.append(f"keep at round {keep.get('round')} has no commit")
        elif close and repo and not _is_ancestor(repo, str(commit), str(close)):
            problems.append(
                f"keep {_short(commit)} is not an ancestor of close {_short(close)} — "
                "the tree does not carry it"
            )
    return problems


def dump(record: Mapping[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def render(record: Mapping[str, Any]) -> str:
    """The human view: every count here is read from the record, never typed twice."""
    objective_id = record.get("objective_id") or "_(none — single metric)_"
    lines = ["# run record", ""]
    lines.append(f"- objective: `{objective_id}`")
    lines.append(
        f"- parent: {_short(record.get('parent_commit'))} -> close: "
        f"{_short(record.get('close_commit'))}"
    )
    lines.append(
        f"- floor: {_g(record.get('floor_before'))} -> {_g(record.get('floor_after'))} "
        "(recorded, not re-measured)"
    )
    lines.append(f"- state: `{record.get('state_dir')}`")
    lines.append("")
    lines += ["## Readings", "", "| leg | unit | before | after | verdict | note |",
              "|-----|------|--------|-------|---------|------|"]
    for row in record.get("readings") or []:
        lines.append(
            f"| {_cell(row.get('name'))} | {_cell(row.get('unit'))} | "
            f"{_g(row.get('before'))} | {_g(row.get('after'))} | "
            f"{_cell(row.get('verdict'))} | {_cell(row.get('note'))} |"
        )
    lines.append("")
    for row in record.get("readings") or []:
        lines.append(f"- `{row.get('name')}` raw: `{_cell(row.get('raw'))}`")
        lines.append(f"  verdict definition: {VERDICT_DEFINITIONS.get(row.get('verdict'), '-')}")
    lines.append("")
    lines += ["## Keeps", ""]
    keeps = record.get("keeps") or []
    if keeps:
        lines += ["| round | commit | leg |", "|-------|--------|-----|"]
        for keep in keeps:
            lines.append(
                f"| {_cell(keep.get('round'))} | `{_short(keep.get('commit'))}` | "
                f"{_cell(keep.get('leg'))} |"
            )
    else:
        lines.append("No candidate was kept — there is no improvement to reproduce.")
    lines.append("")
    lines += ["## Review", ""]
    review = record.get("review") or {}
    for key in ("means", "previous", "weights"):
        shown = ", ".join(f"{name}={_g(value)}" for name, value in (review.get(key) or {}).items())
        lines.append(f"- {key}: {shown or '-'}")
    lines.append(f"- reason: {review.get('reason') or '-'}")
    unmeasured = record.get("unmeasured_legs") or []
    if unmeasured:
        lines.append("- unmeasured legs: " + ", ".join(f"`{name}`" for name in unmeasured))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _load(cfg) -> tuple[list[dict], dict]:
    events, problems = ledger_mod.load(cfg.events_path)
    if problems:
        raise RecordError("the ledger is invalid: " + "; ".join(problems))
    record = build(cfg, events, _objective_for(cfg))
    if record["pending"]:
        raise RecordError(
            "the run has not stopped — a pending record is a guess, not evidence"
        )
    issues = check(record, cfg.repo)
    if issues:
        raise RecordError("the record fails its own check: " + "; ".join(issues))
    return events, record


def write(cfg) -> dict[str, Path]:
    """Write ``record.json`` and ``record.md`` beside the report; return both paths."""
    _, record = _load(cfg)
    json_path = Path(cfg.state_dir) / RECORD_JSON
    md_path = Path(cfg.state_dir) / RECORD_MD
    _write(json_path, dump(record))
    _write(md_path, render(record))
    return {"record": json_path, "markdown": md_path}


def verify(cfg) -> dict[str, Path]:
    """Re-render both artefacts and compare byte for byte; any drift is exit 2."""
    json_path = Path(cfg.state_dir) / RECORD_JSON
    md_path = Path(cfg.state_dir) / RECORD_MD
    missing = [path.name for path in (json_path, md_path) if not path.is_file()]
    if missing:
        raise RecordError(
            f"no record under {cfg.state_dir} ({', '.join(missing)} missing) — "
            "run `report --record` first"
        )
    _, record = _load(cfg)
    for path, text in ((json_path, dump(record)), (md_path, render(record))):
        if path.read_text(encoding="utf-8") != text:
            raise RecordError(
                f"{path} differs from a fresh render — the record drifted from the ledger"
            )
    return {"record": json_path, "markdown": md_path}
