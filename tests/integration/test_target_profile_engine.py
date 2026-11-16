"""PRD 22 — profile → engine plan → a real replay. IDs: AC-TPR-201, AC-TPR-202.

A temporary harness (a copy of ``autoresearch/{target,engine}``) declares a demo
profile, and its CLI prints the plan for a scratch checkout. The plan then runs
for real: ``init`` on the checkout, a replay iteration that improves the metric,
and a ledger that validates. No model, no network.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")

EVALUATOR = '''"""The harness evaluator: one METRIC line, or the hard gate."""
import argparse
import pathlib
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--target-repo", default=".")
parser.add_argument("guard", nargs="?")
args = parser.parse_args()
value = int((pathlib.Path(args.target_repo) / "src" / "value.txt").read_text().strip())
if args.guard:
    sys.exit(0 if value >= 0 else 1)
print(f"METRIC value={value}")
'''

PROFILE = {
    "$comment": [
        "harness-relative: engine, referee, guard_command, runs_dir.",
        "target-relative: program, scopes, protected, docker_free_tier, e2e_dir,",
        "context_dir, dockerfile, fresh_script, guard_steps, fresh_instruction,",
        "arena_test_files.",
    ],
    "name": "demo",
    "engine": "autoresearch/engine/bin/autoresearch",
    "referee": "evaluator.py",
    "guard_command": "python3 {referee} --target-repo {target} guard",
    "runs_dir": "runs/demo",
    "metric_name": "value",
    "direction": "lower",
    "program": "",
    "scopes": {"better": ["src"]},
    "protected": [],
    "docker_free_tier": "",
    "e2e_dir": "",
    "context_dir": "",
    "dockerfile": "",
    "fresh_script": "",
    "guard_steps": [],
    "fresh_instruction": "",
    "arena_test_files": [],
}


def git(repo, *args, timeout=120):
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=timeout
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr.strip()}"
    return proc


def harness_copy(tmp_path):
    """A harness of its own, with one declared profile and a harness-side evaluator."""
    harness = tmp_path / "harness"
    for name in ("target", "engine"):
        shutil.copytree(ROOT / "autoresearch" / name, harness / "autoresearch" / name, ignore=IGNORE)
    (harness / "autoresearch" / "targets").mkdir()
    (harness / "evaluator.py").write_text(EVALUATOR, encoding="utf-8")
    (harness / "autoresearch" / "targets" / "demo.json").write_text(
        json.dumps(PROFILE), encoding="utf-8"
    )
    return harness


def scratch_repo(path, value=10):
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "target@example.com")
    git(path, "config", "user.name", "Target")
    (path / "src").mkdir()
    (path / "src" / "value.txt").write_text(f"{value}\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-m", "init")
    return path


def profile_plan(harness, repo, name="demo", cwd=None):
    """Run the harness CLI the way an operator does — from the target's own directory."""
    binary = harness / "autoresearch" / "engine" / "bin" / "autoresearch"
    return subprocess.run(
        [str(binary), "profile", name, "--repo", str(repo), "--json"],
        cwd=str(cwd or repo),
        capture_output=True,
        text=True,
        timeout=120,
        env={k: v for k, v in os.environ.items() if k != "AUTORESEARCH_TARGET_REPO"},
    )


def replay_record(repo, tmp_path, value=7):
    """One real diff from the baseline, written as the engine's replay JSONL."""
    (repo / "src" / "value.txt").write_text(f"{value}\n", encoding="utf-8")
    patch = git(repo, "diff").stdout
    git(repo, "checkout", "--", "src/value.txt")
    assert patch.strip(), "the replay patch is empty"
    path = tmp_path / "records.jsonl"
    path.write_text(
        json.dumps({"iteration": 1, "description": "lower value", "patch": patch}) + "\n",
        encoding="utf-8",
    )
    return path


def engine(binary, *args, cwd, timeout=240):
    return subprocess.run(
        [str(binary), *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )


def test_profile_plan_runs_a_real_replay_on_a_scratch_checkout(tmp_path):
    """AC-TPR-201: the printed argv initialises the checkout and a replay keeps a win."""
    harness = harness_copy(tmp_path)
    repo = scratch_repo(tmp_path / "checkout")
    assert git(repo, "status", "--porcelain").stdout == ""

    plan = profile_plan(harness, repo)
    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    argv = payload["argv"]
    assert argv[0] == str(harness / "autoresearch/engine/bin/autoresearch")
    assert payload["target"] == str(repo.resolve())
    assert git(repo, "status", "--porcelain").stdout == "", "profile wrote into the target"

    init = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, timeout=240)
    assert init.returncode == 0, init.stderr
    ledger = json.loads((harness / "runs/demo/state/run.json").read_text(encoding="utf-8"))
    assert ledger["repo"] == str(repo.resolve())
    assert ledger["scope"] == ["src"]
    assert str(harness / "evaluator.py") in ledger["verify"]
    assert not (repo / ".autoresearch").exists(), "the measured checkout kept a state dir"
    state_dir = ledger["state_dir"]
    assert state_dir == str((harness / "runs/demo/state").resolve())

    records = replay_record(repo, tmp_path)
    run = engine(
        harness / "autoresearch/engine/bin/autoresearch",
        "run", "--repo", str(repo), "--state-dir", state_dir,
        "--agent", "replay", "--replay", str(records),
        "--max-iterations", "1", "--json",
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stderr
    trials = [json.loads(line) for line in run.stdout.splitlines() if line.strip()]
    assert [event["outcome"] for event in trials if event.get("type") == "trial"] == ["keep"]
    assert (repo / "src" / "value.txt").read_text(encoding="utf-8").strip() == "7"

    status = engine(
        harness / "autoresearch/engine/bin/autoresearch", "status", "--repo", str(repo),
        "--state-dir", state_dir, cwd=tmp_path,
    )
    assert status.returncode == 0, status.stderr
    assert "ledger: valid" in status.stdout
    assert not (repo / ".autoresearch").exists()


def test_a_profile_init_writes_no_state_into_the_measured_checkout(tmp_path):
    """AC-TPR-203: the plan's --state-dir keeps every byte of run state in the harness."""
    harness = harness_copy(tmp_path)
    repo = scratch_repo(tmp_path / "checkout")
    payload = json.loads(profile_plan(harness, repo).stdout)
    argv = payload["argv"]
    state_dir = argv[argv.index("--state-dir") + 1]
    assert state_dir.startswith(str(harness) + os.sep)

    init = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, timeout=240)
    assert init.returncode == 0, init.stderr
    assert state_dir in init.stdout
    written = sorted(p.name for p in Path(state_dir).iterdir())
    assert {"run.json", ".gitignore"} <= set(written)
    assert sorted(p.name for p in harness.glob("runs/*")) == ["demo"]
    assert not (repo / ".autoresearch").exists()
    assert git(repo, "status", "--porcelain").stdout == ""

    # A later command is told where the state is; it is never guessed from the checkout.
    binary = harness / "autoresearch/engine/bin/autoresearch"
    blind = engine(binary, "status", "--repo", str(repo), cwd=tmp_path)
    assert blind.returncode == 2
    assert ".autoresearch" in blind.stderr
    told = engine(binary, "status", "--repo", str(repo), "--state-dir", state_dir, cwd=tmp_path)
    assert told.returncode == 0, told.stderr
    assert "ledger: valid" in told.stdout
    assert not (repo / ".autoresearch").exists()


def test_cli_resolves_harness_keys_here_and_target_keys_there(tmp_path):
    """AC-TPR-202: from the target's cwd the plan still names the harness; refusals exit 2."""
    harness = harness_copy(tmp_path)
    repo = scratch_repo(tmp_path / "checkout")
    payload = json.loads(profile_plan(harness, repo, cwd=repo).stdout)
    argv = payload["argv"]
    assert argv[0].startswith(str(harness) + os.sep)
    assert payload["profile"].startswith(str(harness) + os.sep)
    assert argv[argv.index("--scope") + 1] == "src"
    assert "src" in (repo / "src").as_posix()
    assert "--protect" not in argv
    state_dir = argv[argv.index("--state-dir") + 1]
    assert state_dir == str((harness / "runs/demo/state").resolve())
    assert not state_dir.startswith(str(repo) + os.sep)

    refused = profile_plan(harness, repo, name="../demo", cwd=repo)
    assert refused.returncode == 2
    assert "declared name" in refused.stderr
    assert git(repo, "status", "--porcelain").stdout == ""

    undeclared = profile_plan(harness, repo, name="absent", cwd=repo)
    assert undeclared.returncode == 2
    assert "not declared" in undeclared.stderr
