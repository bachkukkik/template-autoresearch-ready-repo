"""Command line: ``init``, ``run``, ``status``, ``report``, ``doctor``.

Exit codes are part of the contract, so a wrapper script can branch on them:

    0   stopped normally
    1   an objective record is invalid (every problem listed)
    2   configuration or precondition error
    3   ledger invalid
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
from typing import List, Optional, Sequence

from . import __version__
from . import adapters as adapters_mod
from . import config as config_mod
from . import gitops
from . import ledger as ledger_mod
from . import loop as loop_mod
from . import objective as objective_mod
from . import record as record_mod
from . import report as report_mod

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_CONFIG = 2
EXIT_LEDGER = 3

DOCTOR_TIMEOUT = 20.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description="Script-owned keep/discard research loop: verify prints the "
        "metric, guard decides if a candidate may win, the ledger records both.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="validate the repo and write its run.json")
    init.add_argument("--repo", default=".")
    init.add_argument("--state-dir", dest="state", default=None, metavar="PATH",
                      help="where run.json and the ledger live (default: <repo>/.autoresearch; "
                           "relative paths resolve against the current directory)")
    init.add_argument("--verify", default=None,
                      help="command that prints the metric (derived from --objective when omitted)")
    init.add_argument("--metric-name", default=None,
                      help="the metric the verify command prints (derived from --objective)")
    init.add_argument("--direction", default=None, choices=list(config_mod.DIRECTIONS),
                      help="lower|higher (derived from --objective)")
    init.add_argument("--objective", default=None, metavar="PATH",
                      help="a tracked objective record to initialise from; its active leg "
                           "derives --verify/--metric-name/--direction/--repeats/--noise-floor")
    init.add_argument("--objective-leg", dest="objective_leg", default=None, metavar="NAME",
                      help="the leg to measure when the active objective prices more than one")
    init.add_argument("--scope", action="append", required=True,
                      help="repo-relative path prefix the agent may edit (repeatable)")
    init.add_argument("--guard", default=None, help="command that must exit 0")
    init.add_argument("--target", type=float, default=None)
    init.add_argument("--noise-floor", type=float, default=None)
    init.add_argument("--repeats", type=int, default=None)
    init.add_argument("--verify-timeout", type=float, default=config_mod.DEFAULT_VERIFY_TIMEOUT)
    init.add_argument("--guard-timeout", type=float, default=config_mod.DEFAULT_GUARD_TIMEOUT)
    init.add_argument("--protect", action="append", default=[],
                      help="extra protected file (repeatable)")
    init.add_argument("--program", default=None, help="program file of standing instructions")
    init.add_argument("--goal", default=None)
    init.add_argument("--force", action="store_true",
                      help="archive the existing run and start a new one")
    init.set_defaults(func=cmd_init)

    run = sub.add_parser("run", help="run the keep/discard loop")
    run.add_argument("--repo", default=".")
    run.add_argument("--state-dir", dest="state", default=None, metavar="PATH",
                     help="the run's state directory (default: <repo>/.autoresearch)")
    run.add_argument("--agent", required=True, choices=list(adapters_mod.AGENTS))
    run.add_argument("--model", default=None,
                     help="model name recorded in provenance — a name, not a "
                          "gateway URL carrying credentials")
    run.add_argument("--agent-cmd", default=None,
                     help="command adapter template; {prompt_file} and {repo} are substituted")
    run.add_argument("--agent-arg", action="append", default=[],
                     help="extra argv appended to the adapter command (repeatable)")
    run.add_argument("--replay", default=None, help="JSONL record file for --agent replay")
    run.add_argument("--record", default=None, help="append each candidate patch to this JSONL")
    run.add_argument("--max-iterations", type=int, default=10)
    run.add_argument("--plateau", type=int, default=5)
    run.add_argument("--max-wall", type=float, default=0.0, help="0 = unlimited")
    run.add_argument("--agent-timeout", type=float, default=900.0)
    run.add_argument("--max-crashes", type=int, default=3)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--json", dest="json_output", action="store_true")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="replay-validate the ledger and summarise the run")
    status.add_argument("--repo", default=".")
    status.add_argument("--state-dir", dest="state", default=None, metavar="PATH",
                        help="the run's state directory (default: <repo>/.autoresearch)")
    status.add_argument("--json", dest="json_output", action="store_true")
    status.add_argument(
        "--require-provenance",
        action="store_true",
        help="fail (exit 3) when a keep/discard decision carries no provenance block",
    )
    status.set_defaults(func=cmd_status)

    report = sub.add_parser("report", help="write report.md and results.tsv")
    report.add_argument("--repo", default=".")
    report.add_argument("--state-dir", dest="state", default=None, metavar="PATH",
                        help="the run's state directory (default: <repo>/.autoresearch)")
    report.add_argument("--out", default=None)
    mode = report.add_mutually_exclusive_group()
    mode.add_argument("--record", action="store_true",
                      help="write record.json + record.md (the close record) beside the report")
    mode.add_argument("--check", action="store_true",
                      help="re-render the record and exit 0 only on byte identity")
    report.set_defaults(func=cmd_report)

    objective = sub.add_parser(
        "objective",
        help="validate or resolve a tracked objective record "
        "(exit 1: invalid record; exit 2: the file cannot be read)",
    )
    objective.set_defaults(func=lambda args: EXIT_CONFIG)
    objective_modes = objective.add_subparsers(dest="objective_command", required=True)
    validate = objective_modes.add_parser(
        "validate",
        help="list every problem in one pass (exit 1 invalid record, 2 unreadable file)",
    )
    validate.add_argument("--file", default=None, metavar="PATH",
                          help="the record (default: autoresearch/objective/registry.json); "
                               "a missing or unreadable file exits 2, invalid content exits 1")
    validate.set_defaults(func=cmd_objective_validate)
    resolve = objective_modes.add_parser("resolve", help="print the init arguments a leg implies")
    resolve.add_argument("--file", default=None, metavar="PATH")
    resolve.add_argument("--leg", default=None, metavar="NAME")
    resolve.add_argument("--json", dest="json_output", action="store_true")
    resolve.set_defaults(func=cmd_objective_resolve)

    doctor = sub.add_parser("doctor", help="report the harness binaries and their versions")
    doctor.set_defaults(func=cmd_doctor)

    return parser


# ─── commands ────────────────────────────────────────────────────────────────


def cmd_init(args) -> int:
    # `--force` archives the previous run, so it takes the same lock a run does:
    # archiving the state out from under a live run would corrupt it.
    lock = (
        config_mod.state_lock(args.repo, args.state)
        if args.force
        else contextlib.nullcontext()
    )
    with lock:
        cfg = config_mod.init_run(
            repo=args.repo,
            state=args.state,
            verify=args.verify,
            metric_name=args.metric_name,
            direction=args.direction,
            scope=args.scope,
            guard=args.guard,
            target=args.target,
            noise_floor=args.noise_floor,
            repeats=args.repeats,
            verify_timeout=args.verify_timeout,
            guard_timeout=args.guard_timeout,
            protect=args.protect,
            program=args.program,
            goal=args.goal,
            force=args.force,
            objective=args.objective,
            objective_leg=args.objective_leg,
        )
    print(f"initialised run in {cfg.repo}")
    print(f"  verify : {cfg.verify}")
    print(f"  guard  : {cfg.guard or '(none)'}")
    print(f"  metric : {cfg.metric_name} ({cfg.direction} is better)")
    if cfg.objective_id:
        print(f"  objective: {cfg.objective_id} (leg {cfg.objective_leg})")
    print(f"  scope  : {', '.join(cfg.scope)}")
    if cfg.protected:
        print(f"  protect: {', '.join(cfg.protected_paths())}")
    print(f"  config : {config_mod.run_json_path(cfg.repo, cfg.state)}")
    return EXIT_OK


def cmd_run(args) -> int:
    cfg = config_mod.load(args.repo, args.state)

    records = None
    if args.agent == "replay":
        if not args.replay:
            raise config_mod.ConfigError("--agent replay needs --replay FILE")
        records = adapters_mod.load_records(args.replay)
    elif args.replay:
        raise config_mod.ConfigError("--replay only applies to --agent replay")
    if args.agent == "command" and not args.agent_cmd:
        raise config_mod.ConfigError("--agent command needs --agent-cmd")

    if args.max_iterations < 1:
        raise config_mod.ConfigError("--max-iterations must be >= 1")
    if args.plateau < 1:
        raise config_mod.ConfigError("--plateau must be >= 1")
    if args.max_crashes < 1:
        raise config_mod.ConfigError("--max-crashes must be >= 1")
    if not math.isfinite(args.agent_timeout) or args.agent_timeout <= 0:
        raise config_mod.ConfigError("--agent-timeout must be a finite number > 0")
    if not math.isfinite(args.max_wall) or args.max_wall < 0:
        raise config_mod.ConfigError("--max-wall must be a finite number >= 0")
    if args.model and ledger_mod.embeds_credentials(args.model):
        # `--model` is recorded verbatim in an append-only ledger, so a secret
        # there can only be rotated away. Refused in preflight, before any write.
        raise config_mod.ConfigError(
            "--model embeds credentials — pass the model name, not a URL with userinfo"
        )

    adapter = adapters_mod.make_adapter(
        args.agent,
        model=args.model,
        extra=args.agent_arg,
        agent_cmd=args.agent_cmd,
        records=records,
    )
    opts = loop_mod.Options(
        max_iterations=args.max_iterations,
        plateau=args.plateau,
        max_wall=args.max_wall,
        agent_timeout=args.agent_timeout,
        max_crashes=args.max_crashes,
        record=args.record,
        dry_run=args.dry_run,
        json_output=args.json_output,
    )
    ledger = ledger_mod.Ledger(cfg.events_path)
    emit = loop_mod.Emitter(json_output=args.json_output)
    # One run per repo at a time: a second process would interleave commits and
    # resets with the first, so it is refused (exit 2) rather than serialised.
    with config_mod.state_lock(cfg.repo, cfg.state):
        return loop_mod.run(cfg, adapter, ledger, opts, emit)


def cmd_status(args) -> int:
    cfg = config_mod.load(args.repo, args.state)
    events, problems = ledger_mod.load(
        cfg.events_path, require_provenance=args.require_provenance
    )
    if args.json_output:
        payload = report_mod.summarize(cfg, events)
        payload["valid"] = not problems
        payload["problems"] = problems
        print(json.dumps(payload, sort_keys=True, default=str))
    else:
        print(report_mod.summary_line(cfg, events))
        if problems:
            print(f"ledger: INVALID ({len(problems)} violation(s))", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
        else:
            print("ledger: valid")
    return EXIT_LEDGER if problems else EXIT_OK


def cmd_report(args) -> int:
    cfg = config_mod.load(args.repo, args.state)
    if args.check:
        record_mod.verify(cfg)
        print(f"record: byte-identical under {cfg.state_dir}")
        return EXIT_OK
    if args.record:
        paths = record_mod.write(cfg)
        print(paths["record"])
        return EXIT_OK
    paths = report_mod.write(cfg, args.out)
    print(paths["report"])
    return EXIT_OK


def cmd_objective_validate(args) -> int:
    path = objective_mod.record_path(args.file)
    try:
        data = objective_mod.read(path)
    except objective_mod.ObjectiveReadError as exc:
        # Exit 2: the operator named a path that cannot be opened. Exit 1 below is
        # reserved for a record that was read and found inconsistent.
        print(f"autoresearch objective: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except objective_mod.ObjectiveError as exc:
        print(f"autoresearch objective: {exc}", file=sys.stderr)
        return EXIT_INVALID
    problems = objective_mod.validate(data)
    if problems:
        print(
            f"objective record {path} is invalid ({len(problems)} problem(s)):",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_INVALID
    print(f"objective record {path}: valid")
    return EXIT_OK


def cmd_objective_resolve(args) -> int:
    try:
        leg = objective_mod.resolve_leg(objective_mod.load(args.file), leg=args.leg)
    except objective_mod.ObjectiveReadError as exc:
        print(f"autoresearch objective: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except objective_mod.ObjectiveError as exc:
        print(f"autoresearch objective: {exc}", file=sys.stderr)
        return EXIT_INVALID
    argv = [
        "--verify", leg["command"],
        "--metric-name", leg["name"],
        "--direction", leg["direction"],
        "--repeats", str(leg["repeats"]),
        "--noise-floor", f"{leg['noise_floor']:g}",
    ]
    if leg["guard"]:
        argv += ["--guard", leg["guard"]]
    if args.json_output:
        print(json.dumps({"leg": leg, "argv": argv}, sort_keys=True))
    else:
        print(shlex.join(argv))
    return EXIT_OK


def probe_harnesses() -> List[dict]:
    """One row per harness: its binary, where it resolved, its version.

    The single source of "what can this host run" — ``cmd_doctor`` prints it and
    a wrapper (e.g. the REST service's ``doctor``) returns it. Only names, paths
    and version strings are collected: no credential value is ever read.
    """
    rows: List[dict] = []
    for name in adapters_mod.HARNESSES:
        binary = adapters_mod.DEFAULT_BINARIES[name]
        resolved = shutil.which(binary)
        rows.append(
            {
                "agent": name,
                "binary": binary,
                "path": resolved,
                "version": _version_of(resolved) if resolved else None,
                "available": resolved is not None,
            }
        )
    return rows


def cmd_doctor(args) -> int:
    for row in probe_harnesses():
        if not row["available"]:
            print(f"{row['agent']:9s} MISSING  ({row['binary']} not on PATH)")
            continue
        print(f"{row['agent']:9s} {row['path']}  {row['version']}")
    state = "set" if os.environ.get("OPENAI_API_KEY") else "unset"
    # Name only — the value is never read, printed or logged.
    print(f"dsh       OPENAI_API_KEY is {state}")
    return EXIT_OK


def _version_of(binary: str) -> str:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=DOCTOR_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"(version unavailable: {type(exc).__name__})"
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0] if text else f"(exit {proc.returncode})"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except config_mod.ConfigError as exc:
        print(f"autoresearch: error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except gitops.GitError as exc:
        # A git that failed or hung is a precondition error, not a traceback.
        print(f"autoresearch: error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except ledger_mod.LedgerError as exc:
        print(f"autoresearch: ledger invalid: {exc}", file=sys.stderr)
        return EXIT_LEDGER
    except record_mod.RecordError as exc:
        print(f"autoresearch: record: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except objective_mod.ObjectiveError as exc:
        print(f"autoresearch: objective: {exc}", file=sys.stderr)
        return EXIT_CONFIG
