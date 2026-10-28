"""Command line: ``init``, ``run``, ``status``, ``report``, ``doctor``.

Exit codes are part of the contract, so a wrapper script can branch on them:

    0   stopped normally
    2   configuration or precondition error
    3   ledger invalid
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
from typing import Optional, Sequence

from . import __version__
from . import adapters as adapters_mod
from . import config as config_mod
from . import gitops
from . import ledger as ledger_mod
from . import loop as loop_mod
from . import report as report_mod

EXIT_OK = 0
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

    init = sub.add_parser("init", help="validate the repo and write .autoresearch/run.json")
    init.add_argument("--repo", default=".")
    init.add_argument("--verify", required=True, help="command that prints the metric")
    init.add_argument("--metric-name", required=True)
    init.add_argument("--direction", required=True, choices=list(config_mod.DIRECTIONS))
    init.add_argument("--scope", action="append", required=True,
                      help="repo-relative path prefix the agent may edit (repeatable)")
    init.add_argument("--guard", default=None, help="command that must exit 0")
    init.add_argument("--target", type=float, default=None)
    init.add_argument("--noise-floor", type=float, default=config_mod.DEFAULT_NOISE_FLOOR)
    init.add_argument("--repeats", type=int, default=config_mod.DEFAULT_REPEATS)
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
    run.add_argument("--agent", required=True, choices=list(adapters_mod.AGENTS))
    run.add_argument("--model", default=None)
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
    status.add_argument("--json", dest="json_output", action="store_true")
    status.set_defaults(func=cmd_status)

    report = sub.add_parser("report", help="write report.md and results.tsv")
    report.add_argument("--repo", default=".")
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)

    doctor = sub.add_parser("doctor", help="report the harness binaries and their versions")
    doctor.set_defaults(func=cmd_doctor)

    return parser


# ─── commands ────────────────────────────────────────────────────────────────


def cmd_init(args) -> int:
    # `--force` archives the previous run, so it takes the same lock a run does:
    # archiving the state out from under a live run would corrupt it.
    lock = config_mod.state_lock(args.repo) if args.force else contextlib.nullcontext()
    with lock:
        cfg = config_mod.init_run(
            repo=args.repo,
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
        )
    print(f"initialised run in {cfg.repo}")
    print(f"  verify : {cfg.verify}")
    print(f"  guard  : {cfg.guard or '(none)'}")
    print(f"  metric : {cfg.metric_name} ({cfg.direction} is better)")
    print(f"  scope  : {', '.join(cfg.scope)}")
    if cfg.protected:
        print(f"  protect: {', '.join(cfg.protected_paths())}")
    print(f"  config : {config_mod.run_json_path(cfg.repo)}")
    return EXIT_OK


def cmd_run(args) -> int:
    cfg = config_mod.load(args.repo)

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
    with config_mod.state_lock(cfg.repo):
        return loop_mod.run(cfg, adapter, ledger, opts, emit)


def cmd_status(args) -> int:
    cfg = config_mod.load(args.repo)
    events, problems = ledger_mod.load(cfg.events_path)
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
    cfg = config_mod.load(args.repo)
    paths = report_mod.write(cfg, args.out)
    print(paths["report"])
    return EXIT_OK


def cmd_doctor(args) -> int:
    for name in adapters_mod.HARNESSES:
        binary = adapters_mod.DEFAULT_BINARIES[name]
        resolved = shutil.which(binary)
        if not resolved:
            print(f"{name:9s} MISSING  ({binary} not on PATH)")
            continue
        version = _version_of(resolved)
        print(f"{name:9s} {resolved}  {version}")
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
