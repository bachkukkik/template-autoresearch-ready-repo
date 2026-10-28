"""The iteration loop.

One iteration is a fixed sequence, and the order is the safety property:

    prompt -> agent -> changed paths -> scope -> protected hashes -> commit
           -> guard -> verify -> decide -> keep | reset

Nothing the agent does can reach the metric without passing scope, the protected
hashes and the guard first, and nothing it does survives a rejection.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import config as config_mod
from . import decide as decide_mod
from . import gitops
from . import ledger as ledger_mod
from . import measure as measure_mod
from . import prompt as prompt_mod

#: Longest log tail kept. The tail is *stored* — in the ledger and in
#: ``last_agent.log`` — so an agent that prints a megabyte must not grow the
#: ledger by a megabyte per iteration.
LOG_TAIL_LIMIT = 4000

#: Outcomes whose log tail explains a failure, and so is worth showing the next
#: attempt: the agent's own output, the guard's, or the verify's.
PROMPT_FAILURE_OUTCOMES = ("agent_error", "guard_failed", "crash")


@dataclass
class Options:
    max_iterations: int = 10
    plateau: int = 5
    max_wall: float = 0.0
    agent_timeout: float = 900.0
    max_crashes: int = 3
    record: Optional[str] = None
    dry_run: bool = False
    json_output: bool = False


@dataclass
class State:
    """The loop's derived view of the ledger."""

    baseline: Optional[dict] = None
    incumbent: Optional[dict] = None
    trials: List[dict] = field(default_factory=list)

    @classmethod
    def from_events(cls, events: Sequence[dict]) -> "State":
        state = cls()
        for event in events:
            kind = event.get("type")
            if kind == "baseline":
                state.baseline = event
                state.incumbent = {
                    "metric": event.get("metric"),
                    "commit": event.get("commit"),
                }
            elif kind == "trial":
                state.trials.append(event)
                if event.get("outcome") == "keep":
                    state.incumbent = {
                        "metric": event.get("metric"),
                        "commit": event.get("commit"),
                    }
        return state

    @property
    def next_iteration(self) -> int:
        return max((int(t.get("iteration", 0)) for t in self.trials), default=0) + 1


class Emitter:
    """Human lines, or one JSON object per event."""

    def __init__(self, json_output: bool = False, stream=None):
        self.json_output = json_output
        self.stream = stream or sys.stdout

    def note(self, text: str) -> None:
        if not self.json_output:
            print(text, file=self.stream, flush=True)

    def __call__(self, event: dict) -> None:
        if self.json_output:
            print(json.dumps(event, sort_keys=True), file=self.stream, flush=True)
            return
        print(self.human(event), file=self.stream, flush=True)

    @staticmethod
    def human(event: dict) -> str:
        kind = event.get("type")
        if kind == "baseline":
            return (
                f"baseline: {event.get('metric')} "
                f"(commit {str(event.get('commit'))[:7]})"
            )
        if kind == "trial":
            metric = event.get("metric")
            shown = "n/a" if metric is None else f"{metric:g}"
            commit = event.get("commit")
            return (
                f"iter {event.get('iteration')}: {event.get('outcome')} "
                f"metric={shown} commit={(commit or '-')[:7]} — {event.get('description')}"
            )
        if kind == "stop":
            return (
                f"stop: {event.get('reason')} after {event.get('iteration')} iteration(s) "
                f"(incumbent {event.get('metric')} at {str(event.get('commit'))[:7]})"
            )
        if kind == "resume":
            return (
                f"resume: continuing after stop {event.get('after')!r} from iteration "
                f"{event.get('iteration')} (incumbent {event.get('metric')} at "
                f"{str(event.get('commit'))[:7]})"
            )
        return f"{kind}: {json.dumps(event, sort_keys=True)}"


# ─── helpers ─────────────────────────────────────────────────────────────────


def _binary_available(binary: str) -> bool:
    """True when ``binary`` is on ``PATH`` or is an executable path itself."""
    if shutil.which(binary):
        return True
    path = Path(binary)
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def _require_adapter_binary(adapter) -> None:
    """Fail as a config error when the harness binary cannot be executed.

    The dry run preflights this, but so must a real run: a missing binary is a
    precondition error (exit 2), not an agent failure, and it must be caught
    *before* the baseline is measured so a run that cannot start leaves no
    baseline behind.
    """
    binary = adapter.resolve_binary()
    if binary is None or _binary_available(binary):
        return
    raise config_mod.ConfigError(f"adapter binary {binary!r} is not on PATH")


def _cap(text: str, limit: int = LOG_TAIL_LIMIT) -> str:
    """Keep the last ``limit`` characters of a log tail."""
    text = text or ""
    return text if len(text) <= limit else text[-limit:]


def _unlink(cfg, paths: Sequence[str]) -> None:
    """Delete exactly these repo-relative paths, wherever the agent left them.

    The path is used *unresolved*: a symlink aimed outside the repo resolves to
    its target, which is outside the root, so resolving first skipped the link
    and left the tree dirty forever. Only the link's own directory is resolved —
    that is the check that the path really is inside the repository.
    """
    root = Path(cfg.repo).resolve()
    for rel in paths:
        if gitops.is_state_path(rel):
            continue  # the engine's own bookkeeping is never a candidate
        link = root / rel
        try:
            link.parent.resolve().relative_to(root)
        except (OSError, ValueError):
            continue
        try:
            if os.path.islink(link) or not link.is_dir():
                os.unlink(link)
            elif link.is_dir():
                shutil.rmtree(link)
        except OSError:
            continue


def _reset(cfg, commit: str, extra_untracked: Sequence[str] = ()) -> None:
    """Return the worktree to ``commit``.

    ``git reset --hard`` restores tracked files; ``git clean -fd`` is scoped to
    the declared scopes so the operator's unrelated untracked work is never
    removed. ``extra_untracked`` covers the cases that scoping cannot: a file the
    agent *created* outside the scope in this very iteration, or an ignored file
    it created *inside* the scope (ignored files are not ``git clean``ed without
    ``-x``, which would take the operator's ignored work too).
    """
    gitops.reset_hard(cfg.repo, commit)
    gitops.clean_scopes(cfg.repo, cfg.scope)
    _unlink(cfg, extra_untracked)


def _revert(cfg, commit: str, extra_untracked: Sequence[str] = ()) -> None:
    """The loop's **only** way back to the incumbent.

    Every non-keep outcome — agent error, scope or protected violation, guard
    failure, crash, discard, interrupt — ends here. Scoping ``git clean`` alone
    is not enough: a file the agent created outside the scope (or an ignored one
    inside it) would survive and the next invocation would refuse to start on a
    dirty tree. The tree was clean when the iteration began (``require_clean``),
    so every untracked path git reports now was created by this iteration and can
    be removed by name — anywhere outside ``.autoresearch/``.
    """
    paths = list(extra_untracked) + _untracked_new(cfg, gitops.status_paths(cfg.repo))
    _reset(cfg, commit, paths)


def _sweep_artifacts(cfg, before: Sequence[str]) -> None:
    """Remove untracked files verify/guard created since ``before``.

    Only untracked paths are touched — by this point the agent's work is
    committed, and a tracked file a verify modified is a candidate change, not an
    artifact. Without this, a verify that writes ``results.json`` would be
    attributed to the agent on the next iteration and every candidate would be
    rejected as a scope violation.
    """
    seen = set(before)
    new = [p for p in gitops.status_paths(cfg.repo) if p not in seen]
    if new:
        _unlink(cfg, _untracked_new(cfg, new))


def _untracked_new(cfg, paths: Sequence[str]) -> List[str]:
    """The subset of ``paths`` that git does not track (i.e. the agent created)."""
    out: List[str] = []
    for rel in paths:
        proc = gitops.git(
            cfg.repo, "ls-files", "--error-unmatch", "--", rel, check=False, timeout=30
        )
        if proc.returncode != 0:
            out.append(rel)
    return out


def _streak(trials: Sequence[dict], predicate) -> int:
    count = 0
    for trial in reversed(list(trials)):
        if predicate(trial):
            count += 1
        else:
            break
    return count


def _append_record(path: str, iteration: int, description: str, patch: str) -> None:
    record = {"iteration": iteration, "description": description, "patch": patch}
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


# ─── phases ──────────────────────────────────────────────────────────────────


def _baseline(cfg, ledger: ledger_mod.Ledger, state: State, emit: Emitter) -> None:
    before = gitops.status_paths(cfg.repo)
    try:
        guard_ok, guard_log = measure_mod.run_guard(cfg)
        if not guard_ok:
            raise config_mod.ConfigError(
                "guard fails at baseline: " + (guard_log.splitlines() or [""])[-1]
            )
        measurement = measure_mod.measure(cfg)
        if not measurement.ok:
            raise config_mod.ConfigError(
                "verify produced no metric at baseline: "
                + (measurement.log_tail.splitlines() or [""])[-1]
            )
    finally:
        # A verify that writes an artifact must not leave it behind: the tree is
        # a precondition for the very next step (and for the next invocation).
        _sweep_artifacts(cfg, before)
    commit = gitops.head(cfg.repo)
    event = ledger.append(
        {
            "type": "baseline",
            "metric": measurement.value,
            "values": measurement.values,
            "commit": commit,
            "direction": cfg.direction,
            "noise_floor": cfg.noise_floor,
            "guard": cfg.guard,
            "verify": cfg.verify,
            "seconds": round(measurement.seconds, 3),
        }
    )
    state.baseline = event
    state.incumbent = {"metric": measurement.value, "commit": commit}
    emit(event)


def _one_iteration(
    cfg, adapter, state: State, iteration: int, opts: Options, last_failure_log: str = ""
) -> dict:
    """Run one candidate through the whole pipeline; return the trial fields."""
    repo = cfg.repo
    incumbent = state.incumbent
    if incumbent is None:  # the baseline phase always sets it
        raise config_mod.ConfigError("no baseline in the ledger — cannot iterate")
    fields: Dict[str, object] = {
        "iteration": iteration,
        "direction": cfg.direction,
        "noise_floor": cfg.noise_floor,
        "metric": None,
        "values": [],
        "commit": None,
        "guard": None,
        "description": f"iteration {iteration}",
        "log_tail": "",
    }

    def done(outcome: str, **extra) -> dict:
        fields.update(extra)
        fields["outcome"] = outcome
        return fields

    prompt = prompt_mod.build_prompt(
        cfg,
        prompt_mod.PromptState(
            baseline=(state.baseline or {}).get("metric"),
            incumbent=incumbent["metric"],
            incumbent_commit=incumbent["commit"],
            trials=state.trials,
            last_failure_log=last_failure_log,
        ),
    )
    # What the tree looked like before the agent ran: only the delta is the
    # agent's, so only the delta can be a scope violation. An artifact an
    # earlier phase left behind is not this iteration's edit.
    before_agent = set(gitops.status_paths(repo))
    ignored_before = gitops.ignored_snapshot(repo, cfg.scope)
    try:
        result = adapter.run(prompt, repo, opts.agent_timeout, iteration=iteration)
    except (FileNotFoundError, PermissionError) as exc:
        # The preflight passed but the executable was gone (or not executable)
        # when the fork happened. That is still an outcome, not a traceback.
        _revert(cfg, incumbent["commit"])
        fields["log_tail"] = _cap(f"agent could not be started: {exc}")
        fields["description"] = f"iteration {iteration} (could not start)"
        return done("agent_error", exit_code=127)
    fields["log_tail"] = _cap(result.output_tail)
    fields["description"] = result.description
    fields["agent_seconds"] = round(result.seconds, 3)

    ignored_changed, ignored_added = gitops.ignored_delta(
        ignored_before, gitops.ignored_snapshot(repo, cfg.scope)
    )

    if not result.ok:
        _revert(cfg, incumbent["commit"], extra_untracked=ignored_added)
        return done("agent_error", exit_code=result.exit_code)

    if ignored_changed or ignored_added:
        # `git status` cannot see an ignored path, so a write to one inside the
        # scope used to read as `no_change` and survive the revert unguarded.
        _revert(cfg, incumbent["commit"], extra_untracked=ignored_added)
        return done(
            "scope_violation",
            paths=sorted(set(ignored_changed) | set(ignored_added))[:20],
            reason="ignored file changed",
        )

    changed = [path for path in gitops.status_paths(repo) if path not in before_agent]
    if not changed:
        # Nothing of the agent's is left, but the helper still runs: it is the
        # loop's single way back to the incumbent, and it is what makes
        # "no_change" a statement about the tree rather than about git's view.
        _revert(cfg, incumbent["commit"])
        return done("no_change")

    outside = [p for p in changed if not config_mod.under_scope(p, cfg.scope)]
    if outside:
        _revert(cfg, incumbent["commit"])
        return done("scope_violation", paths=outside[:20])

    mismatched = config_mod.protected_mismatches(cfg)
    if mismatched:
        _revert(cfg, incumbent["commit"])
        return done("protected_violation", paths=mismatched)

    gitops.add(repo, changed)
    patch = gitops.staged_diff(repo, incumbent["commit"]) if opts.record else None
    commit = gitops.commit_staged(
        repo, f"autoresearch: iter {iteration}: {fields['description']}"
    )
    fields["commit"] = commit
    if opts.record:
        _append_record(opts.record, iteration, fields["description"], patch or "")

    # Anything that appears from here on was written by guard/verify, and is
    # swept before the next iteration so it is not mistaken for an agent edit.
    before_measure = gitops.status_paths(repo)
    guard_ok, guard_log = measure_mod.run_guard(cfg)
    fields["guard"] = "pass" if guard_ok else "fail"
    if not guard_ok:
        _revert(cfg, incumbent["commit"])
        fields["log_tail"] = _cap(guard_log or fields["log_tail"])
        return done("guard_failed")

    measurement = measure_mod.measure(cfg)
    fields["values"] = measurement.values
    fields["metric"] = measurement.value
    fields["seconds"] = round(measurement.seconds, 3)
    if not measurement.ok:
        _revert(cfg, incumbent["commit"])
        fields["log_tail"] = _cap(measurement.log_tail or fields["log_tail"])
        return done("crash")

    decision = decide_mod.decide(
        measurement.value, incumbent["metric"], cfg.direction, cfg.noise_floor
    )
    if decision == decide_mod.KEEP:
        state.incumbent = {"metric": measurement.value, "commit": commit}
        _sweep_artifacts(cfg, before_measure)
        return done("keep")

    _revert(cfg, incumbent["commit"])
    return done("discard")


def _planned_stops(cfg, opts: Options) -> List[str]:
    stops: List[str] = []
    if cfg.target is not None:
        op = "<=" if cfg.direction == "lower" else ">="
        stops.append(f"target {op} {cfg.target:g}")
    stops.append(f"plateau {opts.plateau} consecutive non-keeps")
    stops.append(f"max-iterations {opts.max_iterations}")
    stops.append(
        "max-wall " + (f"{opts.max_wall:g}s" if opts.max_wall else "unlimited")
    )
    stops.append(f"max-crashes {opts.max_crashes} consecutive")
    return stops


def _dry_run(cfg, adapter, state: State, opts: Options, emit: Emitter) -> int:
    """Validate everything, print the plan, touch nothing."""
    mismatched = config_mod.protected_mismatches(cfg)
    if mismatched:
        raise config_mod.ConfigError(
            "protected files do not match their recorded hashes: " + ", ".join(mismatched)
        )

    binary = adapter.resolve_binary()
    if binary and shutil.which(binary) is None:
        raise config_mod.ConfigError(f"adapter binary {binary!r} is not on PATH")

    before = gitops.status_paths(cfg.repo)
    try:
        guard_ok, guard_log = measure_mod.run_guard(cfg)
        if not guard_ok:
            raise config_mod.ConfigError(
                "guard fails: " + (guard_log.splitlines() or [""])[-1]
            )
        measurement = measure_mod.measure(cfg)
        if not measurement.ok:
            raise config_mod.ConfigError(
                "verify produced no metric: "
                + (measurement.log_tail.splitlines() or [""])[-1]
            )
    finally:
        # "touch nothing" includes the artifacts a verify writes.
        _sweep_artifacts(cfg, before)

    incumbent = state.incumbent or {
        "metric": measurement.value,
        "commit": gitops.head(cfg.repo),
    }
    prompt = prompt_mod.build_prompt(
        cfg,
        prompt_mod.PromptState(
            baseline=(state.baseline or {}).get("metric", measurement.value),
            incumbent=incumbent["metric"],
            incumbent_commit=incumbent["commit"],
            trials=state.trials,
        ),
    )
    argv = adapter.argv(prompt, cfg.repo)
    placeholder = f"<prompt: {len(prompt)} chars>"
    prompt_file = str(adapter.prompt_path(cfg.repo))
    shown = [
        placeholder if token in (prompt, prompt_file) else token for token in argv
    ]

    plan = {
        "dry_run": True,
        "metric": measurement.value,
        "metric_name": cfg.metric_name,
        "direction": cfg.direction,
        "argv": shown,
        "stops": _planned_stops(cfg, opts),
    }
    if emit.json_output:
        print(json.dumps(plan, sort_keys=True), file=emit.stream, flush=True)
        return 0

    emit.note(f"dry run — validated config, clean tree, protected hashes, adapter ({adapter.name})")
    emit.note(
        f"metric: {cfg.metric_name}={measurement.value:g} "
        f"({'lower' if cfg.direction == 'lower' else 'higher'} is better)"
    )
    emit.note("adapter argv: " + " ".join(shown))
    # The prompt is an argv element for the harness adapters and a file for the
    # command adapter, so its size is also stated on its own line.
    emit.note(f"prompt: {placeholder}")
    emit.note("stops: " + "; ".join(plan["stops"]))
    emit.note("nothing was committed and no events were written")
    return 0


def _resume(cfg, ledger: ledger_mod.Ledger, events: Sequence[dict], state: State, emit: Emitter) -> None:
    """Supersede the ledger's final stop with a ``resume`` when a run continues.

    Resuming is a supported operation, so a second invocation must not simply
    append a second final stop: the ledger is a sequence of segments, and the
    stop that ended the previous one stays true for that segment only. The
    resume event is written before any new work, so an interrupted resume leaves
    a ledger that still replays.
    """
    if not events or events[-1].get("type") != "stop":
        return
    incumbent = state.incumbent or {}
    event = ledger.append(
        {
            "type": "resume",
            "iteration": state.next_iteration - 1,
            "metric": incumbent.get("metric"),
            "commit": incumbent.get("commit"),
            "after": events[-1].get("reason"),
        }
    )
    emit(event)


# ─── entry point ─────────────────────────────────────────────────────────────


def run(cfg, adapter, ledger: ledger_mod.Ledger, opts: Options, emit: Emitter) -> int:
    """Drive the loop to a stop condition; return the process exit code."""
    started = time.monotonic()
    events = ledger.read()
    problems = ledger_mod.validate(events) if events else []
    if problems:
        raise ledger_mod.LedgerError("; ".join(problems))
    state = State.from_events(events)

    config_mod.require_clean(cfg.repo, what="working tree")

    if opts.dry_run:
        return _dry_run(cfg, adapter, state, opts, emit)

    # Preflight the harness before the baseline: an agent that cannot be
    # executed is a broken invocation, and measuring first would record a
    # baseline for a run that can never iterate.
    _require_adapter_binary(adapter)

    if state.baseline is None:
        try:
            _baseline(cfg, ledger, state, emit)
        except KeyboardInterrupt:
            # Ctrl-C before there is a baseline. There is no incumbent to
            # restore and nothing worth recording: a stop event without a
            # baseline would make the ledger unreplayable, so the run ends with
            # an empty history and the next invocation measures again.
            emit.note("interrupted during the baseline — nothing was recorded")
            return 0
        incumbent = state.incumbent
        if incumbent is not None and decide_mod.target_met(
            incumbent["metric"], cfg.target, cfg.direction
        ):
            return _finish(cfg, ledger, state, emit, "target", 0)

    if state.incumbent is None:
        raise config_mod.ConfigError(
            "the ledger has no baseline — cannot determine an incumbent"
        )
    incumbent_commit = state.incumbent["commit"]

    current = gitops.head(cfg.repo)
    if current != incumbent_commit:
        raise config_mod.ConfigError(
            f"HEAD is {current[:7]} but the incumbent is "
            f"{str(incumbent_commit)[:7]} — check out the incumbent or "
            "start a new run; the engine will not reset your worktree silently"
        )
    config_mod.require_clean(cfg.repo, what="working tree")

    # A stopped run that is started again is a *resumed* run: the resume event
    # supersedes the final stop (see ledger.validate) instead of leaving the
    # ledger with two stops and no seam. Written only once every precondition
    # has passed, so a refused invocation does not touch the history.
    _resume(cfg, ledger, events, state, emit)

    iteration = state.next_iteration
    last_log = ""
    last_failure = ""

    try:
        while True:
            if opts.max_wall and (time.monotonic() - started) >= opts.max_wall:
                return _finish(cfg, ledger, state, emit, "max_wall", iteration - 1)
            if iteration > opts.max_iterations:
                return _finish(cfg, ledger, state, emit, "max_iterations", iteration - 1)

            trial = _one_iteration(
                cfg, adapter, state, iteration, opts, last_failure
            )
            # The tail is *stored*, capped, so it is both in the ledger and in
            # last_agent.log — an operator reading the history sees what the
            # agent said, without the history growing without bound.
            trial["log_tail"] = _cap(str(trial.get("log_tail") or ""))
            last_log = trial["log_tail"] or last_log
            if trial.get("outcome") in PROMPT_FAILURE_OUTCOMES and last_log:
                # What the agent is told next depends on why this one failed:
                # an agent error carries its own output, a guard failure the
                # guard's, a crash the verify's. Silently dropping it made the
                # next attempt repeat the same mistake.
                last_failure = last_log
            event = ledger.append({"type": "trial", **trial})
            state.trials.append(event)
            _write_log(cfg, last_log)
            emit(event)

            reason = _stop_reason(cfg, state, opts, iteration, started)
            if reason:
                return _finish(cfg, ledger, state, emit, reason, iteration)
            iteration += 1
    except KeyboardInterrupt:
        _revert(cfg, state.incumbent["commit"])
        emit.note("interrupted — worktree restored to the incumbent")
        return _finish(cfg, ledger, state, emit, "interrupted", iteration - 1)


def _stop_reason(cfg, state: State, opts: Options, iteration: int, started: float) -> Optional[str]:
    if decide_mod.target_met(
        (state.incumbent or {}).get("metric"), cfg.target, cfg.direction
    ):
        return "target"
    if _streak(state.trials, lambda t: t.get("outcome") in ledger_mod.CRASH_OUTCOMES) >= opts.max_crashes:
        return "max_crashes"
    if _streak(state.trials, lambda t: t.get("outcome") != "keep") >= opts.plateau:
        return "plateau"
    if iteration >= opts.max_iterations:
        return "max_iterations"
    if opts.max_wall and (time.monotonic() - started) >= opts.max_wall:
        return "max_wall"
    return None


def _write_log(cfg, log_tail: str) -> None:
    try:
        path = Path(cfg.state_dir) / config_mod.LAST_AGENT_LOG
        path.write_text(_cap(log_tail) + "\n", encoding="utf-8")
    except OSError:
        pass


def _finish(cfg, ledger: ledger_mod.Ledger, state: State, emit: Emitter, reason: str, iteration: int) -> int:
    event = ledger.append(
        {
            "type": "stop",
            "reason": reason,
            "iteration": iteration,
            "metric": state.incumbent["metric"] if state.incumbent else None,
            "commit": state.incumbent["commit"] if state.incumbent else None,
        }
    )
    emit(event)
    return 0
