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

RESULTS_HEADER = (
    "iter\tcommit\tmetric\toutcome\tdescription\ttokens\twall_seconds"
)

#: Outcomes that settle a trial: a verdict was reached about a candidate. The
#: cost ratios count these and nothing else — an agent that never measured has
#: no score to divide by its spend.
SETTLED_OUTCOMES = (
    decide_mod.KEEP, decide_mod.DISCARD, decide_mod.INCONCLUSIVE
)

#: Two decimals. The denominators here are measured, not exact, so a third
#: digit would claim precision the measurement does not have.
COST_DECIMALS = 2

UNSETTLED_LINE = (
    "unsettled: {count} attempt(s) — the totals above are a lower bound"
)


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
    """Every row the report shows, baseline included as iteration 0.

    ``tokens`` and ``wall_seconds`` are the row's own cost, ``None`` when the
    event recorded none — the baseline never has one, and an unknown count is
    not a measured zero.
    """
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
                    "tokens": None,
                    "wall_seconds": None,
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
                    "tokens": _tokens_of(event),
                    "wall_seconds": _wall_of(event),
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
        "attempts": len([e for e in events if e.get("type") == "attempt"]),
        "unsettled": any(e.get("type") == "attempt" for e in events),
        "outcomes": counts,
        "stop_reason": stop.get("reason") if stop else None,
        "keeps": keeps,
        "trials": [e for e in events if e.get("type") == "trial"],
    }


#: How a claim is graded here: was one stated, and did its sign hold. The
#: magnitude is deliberately not scored — most honest predictions would fail an
#: error band, and a metric nobody can pass measures nothing.
CALIBRATION_NA = "calibration: n/a (no numeric predictions measured)"


def calibration_line(events: Sequence[dict]) -> Optional[str]:
    """How many settled trials stated a claim, and how many of those held.

    ``None`` when not one trial carries a ``hypothesis`` key: the flag was off,
    so the report says nothing about claims rather than claiming zero of zero.
    """
    asked = [
        event
        for event in events
        if event.get("type") == "trial" and "hypothesis" in event
    ]
    if not asked:
        return None
    claims = [
        event["hypothesis"]
        for event in asked
        if isinstance(event.get("hypothesis"), dict)
    ]
    if not any(claim.get("predict") is not None for claim in claims):
        return CALIBRATION_NA
    matches = sum(1 for claim in claims if claim.get("sign_match") is True)
    return (
        f"calibration: {len(claims)}/{len(asked)} claims read, "
        f"{matches} sign matches"
    )


def cost_of(event: dict) -> dict:
    """The trial's recorded cost, or an empty dict when it recorded none."""
    cost = event.get("cost")
    return cost if isinstance(cost, dict) else {}


def _tokens_of(event: dict) -> Optional[int]:
    """The recorded token count, or ``None`` — a bool is not a count."""
    value = cost_of(event).get("tokens")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _wall_of(event: dict) -> Optional[float]:
    """The recorded wall time, or ``None``."""
    value = cost_of(event).get("wall_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def settled_trials(events: Sequence[dict]) -> List[dict]:
    """The trials that reached a verdict, in ledger order."""
    return [
        event
        for event in events
        if event.get("type") == "trial"
        and event.get("outcome") in SETTLED_OUTCOMES
    ]


def _ratio(keeps: int, denominator: float) -> str:
    return f"{keeps / denominator:.{COST_DECIMALS}f}"


def cost_lines(events: Sequence[dict]) -> List[str]:
    """The *Cost* section: keeps against what the settled trials spent.

    Numerator and denominator are read from the *same* subset, so a trial that
    reported no tokens can neither inflate nor deflate a rate: keeps per 100k
    tokens counts the keeps among the trials that reported tokens. Where that
    subset is empty the line says ``n/a`` and why — the alternative is
    dividing by an unknown, which is how a partial total starts reading as
    a complete one. ``0`` is not a denominator either: zero recorded tokens means none were
    recorded, not that the run was free.
    """
    settled = settled_trials(events)
    keeps = sum(
        1 for event in settled if event.get("outcome") == decide_mod.KEEP
    )
    lines = [f"keeps: {keeps} / {len(settled)} settled"]

    paid = [event for event in settled if _tokens_of(event) is not None]
    tokens = sum(
        int(value) for value in (_tokens_of(event) for event in paid)
        if value is not None
    )
    if tokens > 0:
        kept = sum(1 for e in paid if e.get("outcome") == decide_mod.KEEP)
        lines.append(f"keeps / 100k tokens: {_ratio(kept, tokens / 100_000)}")
    else:
        lines.append("keeps / 100k tokens: n/a (no token usage)")

    timed = [event for event in settled if _wall_of(event) is not None]
    seconds = sum(
        value for value in (_wall_of(event) for event in timed)
        if value is not None
    )
    if seconds > 0:
        kept = sum(1 for e in timed if e.get("outcome") == decide_mod.KEEP)
        lines.append(f"keeps / hour: {_ratio(kept, seconds / 3600)}")
    else:
        lines.append("keeps / hour: n/a (no wall time)")
    return lines


def unsettled_line(events: Sequence[dict]) -> Optional[str]:
    """One line saying the totals above are a floor, or ``None``.

    A run that wrote an ``attempt`` event tried something that never settled, so
    every total beside it is a lower bound. Saying so is the whole point: the
    veteran's defect was a partial total published as a complete one.
    """
    attempts = sum(1 for event in events if event.get("type") == "attempt")
    if not attempts:
        return None
    return UNSETTLED_LINE.format(count=attempts)


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
    if getattr(cfg, "objective_id", None):
        lines.append(f"- objective: `{cfg.objective_id}` (leg `{cfg.objective_leg}`)")
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
    calibration = calibration_line(events)
    if calibration:
        lines.append("")
        lines.append(calibration)
    unsettled = unsettled_line(events)
    if unsettled:
        lines.append("")
        lines.append(unsettled)
    lines.append("")

    lines += ["## Cost", ""] + cost_lines(events) + [""]

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


def _tsv_cost(value) -> str:
    """A cost cell: empty when the number is unknown.

    Empty, never ``0``: a spreadsheet reads a blank as "not recorded" and a zero
    as "measured, and it cost nothing" — the exact substitution this record
    exists to prevent.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def results_tsv(events: Sequence[dict]) -> str:
    lines = [RESULTS_HEADER]
    for row in trial_rows(events):
        metric = "-" if row["metric"] is None else f"{row['metric']:g}"
        commit = row["commit"] or "-"
        description = str(row["description"]).replace("\t", " ").replace("\n", " ")
        lines.append(
            f"{row['iteration']}\t{commit}\t{metric}\t{row['outcome']}\t"
            f"{description}\t{_tsv_cost(row['tokens'])}\t"
            f"{_tsv_cost(row['wall_seconds'])}"
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
