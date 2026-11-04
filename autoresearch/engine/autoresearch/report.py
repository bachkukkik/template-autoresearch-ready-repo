"""Reporting: the run summary, ``report.md`` and the ``results.tsv`` export.

A report's job is to let a reader *check* the claim rather than believe it, so
the EVIDENCE section carries, for every kept candidate, the commit sha, the
metric and a command that reproduces it from a clean checkout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import config as config_mod
from . import decide as decide_mod
from . import ledger as ledger_mod

RESULTS_HEADER = "iter\tcommit\tmetric\toutcome\tdescription"


def _cell(text) -> str:
    """One markdown table cell: a ``|`` or a newline in agent text must not
    split the row into extra columns."""
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _short(commit) -> str:
    """A commit as the report shows it: seven characters, or ``-`` when a run
    recorded none (an empty ledger has no sha, and ``None`` is not one)."""
    return str(commit)[:7] if commit else "-"


def trial_rows(events: Sequence[dict]) -> List[dict]:
    """Every row the report shows, baseline included as iteration 0."""
    rows: List[dict] = []
    for event in events:
        kind = event.get("type")
        if kind == "baseline":
            rows.append(
                {
                    "iteration": 0,
                    "commit": event.get("commit"),
                    "metric": event.get("metric"),
                    "outcome": "baseline",
                    "description": "baseline",
                }
            )
        elif kind == "trial":
            rows.append(
                {
                    "iteration": event.get("iteration"),
                    "commit": event.get("commit"),
                    "metric": event.get("metric"),
                    "outcome": event.get("outcome"),
                    "description": event.get("description") or "",
                }
            )
    return rows


def summarize(cfg, events: Sequence[dict]) -> dict:
    """The run summary shared by ``status`` and ``report``."""
    baseline = next((e for e in events if e.get("type") == "baseline"), None)
    counts: Dict[str, int] = {}
    keeps: List[dict] = []
    for event in events:
        if event.get("type") != "trial":
            continue
        outcome = str(event.get("outcome"))
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome == "keep":
            keeps.append(event)
    stop = next((e for e in reversed(events) if e.get("type") == "stop"), None)

    baseline_metric = baseline.get("metric") if baseline else None
    best = keeps[-1] if keeps else None
    best_metric = best.get("metric") if best else baseline_metric
    best_commit = best.get("commit") if best else (baseline.get("commit") if baseline else None)

    return {
        "baseline_metric": baseline_metric,
        "baseline_commit": baseline.get("commit") if baseline else None,
        "best_metric": best_metric,
        "best_commit": best_commit,
        "improvement_pct": decide_mod.improvement(
            baseline_metric, best_metric, cfg.direction
        ),
        "iterations": len([e for e in events if e.get("type") == "trial"]),
        "outcomes": counts,
        "stop_reason": stop.get("reason") if stop else None,
        "keeps": keeps,
        "trials": [e for e in events if e.get("type") == "trial"],
    }


def render_markdown(cfg, events: Sequence[dict]) -> str:
    summary = summarize(cfg, events)
    rows = trial_rows(events)
    lines: List[str] = ["# autoresearch report", ""]

    lines += ["## Goal", ""]
    lines.append(cfg.goal.strip() if cfg.goal else "_(no goal recorded)_")
    lines.append("")

    lines += ["## Configuration", ""]
    lines.append(f"- repo: `{cfg.repo}`")
    lines.append(f"- verify: `{cfg.verify}`")
    lines.append(f"- guard: `{cfg.guard}`" if cfg.guard else "- guard: _(none)_")
    lines.append(f"- metric: `{cfg.metric_name}` ({cfg.direction} is better)")
    lines.append(f"- target: {_fmt(cfg.target) if cfg.target is not None else '_(none)_'}")
    lines.append(f"- noise floor: {cfg.noise_floor:g}")
    lines.append(f"- repeats: {cfg.repeats}")
    lines.append("- scope: " + ", ".join(f"`{s}`" for s in cfg.scope))
    if cfg.protected:
        lines.append("- protected: " + ", ".join(f"`{p}`" for p in cfg.protected_paths()))
    lines.append("")

    lines += ["## Result", ""]
    lines.append(f"- baseline: {_fmt(summary['baseline_metric'])} "
                 f"(`{_short(summary['baseline_commit'])}`)")
    lines.append(
        f"- best: {_fmt(summary['best_metric'])} "
        f"(`{_short(summary['best_commit'])}`)"
    )
    change = summary["improvement_pct"]
    lines.append(f"- change: {'n/a' if change is None else f'{change:+.2f}%'}")
    lines.append(f"- iterations: {summary['iterations']}")
    lines.append(f"- stop: {summary['stop_reason'] or '_(none — run incomplete)_'}")
    if summary["outcomes"]:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(summary["outcomes"].items()))
        lines.append(f"- outcomes: {counts}")
    lines.append("")

    lines += ["## Trials", "", "| iter | commit | outcome | metric | description |",
              "|------|--------|---------|--------|-------------|"]
    for row in rows:
        commit = str(row["commit"])[:7] if row["commit"] else "-"
        lines.append(
            f"| {row['iteration']} | {commit} | {_cell(row['outcome'])} | "
            f"{_fmt(row['metric'])} | {_cell(row['description'])} |"
        )
    lines.append("")

    lines += ["## EVIDENCE", ""]
    if summary["keeps"]:
        lines.append(
            "Every kept candidate, with the command that reproduces its metric "
            "from a clean checkout:"
        )
        lines.append("")
        for event in summary["keeps"]:
            sha = str(event.get("commit"))
            lines.append(f"### iteration {event.get('iteration')} — {sha[:7]}")
            lines.append("")
            lines.append(f"- commit: `{sha}`")
            lines.append(f"- metric: `{cfg.metric_name}={_fmt(event.get('metric'))}`")
            lines.append(f"- description: {event.get('description')}")
            lines.append(
                f"- reproduce: `git checkout {sha} && {cfg.verify}`"
            )
            lines.append("")
    else:
        lines.append("No candidate was kept — there is no improvement to reproduce.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def results_tsv(events: Sequence[dict]) -> str:
    lines = [RESULTS_HEADER]
    for row in trial_rows(events):
        metric = "-" if row["metric"] is None else f"{row['metric']:g}"
        commit = row["commit"] or "-"
        description = str(row["description"]).replace("\t", " ").replace("\n", " ")
        lines.append(
            f"{row['iteration']}\t{commit}\t{metric}\t{row['outcome']}\t{description}"
        )
    return "\n".join(lines) + "\n"


def write(cfg, out: Optional[str] = None) -> Dict[str, Path]:
    """Write ``report.md`` and ``results.tsv``; return both paths."""
    events, problems = ledger_mod.load(cfg.events_path)
    if problems:
        raise ledger_mod.LedgerError("; ".join(problems))
    report_path = Path(out) if out else Path(cfg.state_dir) / config_mod.REPORT_MD
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown(cfg, events), encoding="utf-8")
    tsv_path = Path(cfg.state_dir) / config_mod.RESULTS_TSV
    tsv_path.write_text(results_tsv(events), encoding="utf-8")
    return {"report": report_path, "results": tsv_path}


def summary_line(cfg, events: Sequence[dict]) -> str:
    summary = summarize(cfg, events)
    change = summary["improvement_pct"]
    return (
        f"run {cfg.metric_name} ({cfg.direction} is better): "
        f"baseline {_fmt(summary['baseline_metric'])} -> "
        f"best {_fmt(summary['best_metric'])} "
        f"({'n/a' if change is None else f'{change:+.2f}%'}), "
        f"{summary['iterations']} iteration(s), "
        f"stop {summary['stop_reason'] or 'incomplete'}"
    )
