"""PRD 22 — an objective-driven replay, and the close record it leaves.

IDs: AC-OBJ-201, AC-REC-201.

Every case spawns ``python3 -m autoresearch`` (``PYTHONPATH=engine``) against a
throwaway git checkout. The objective record lives outside the checkout, because
a record *about* a tree must not be an input *to* it. No model, no network.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "autoresearch" / "engine"

SCORE_PY = '''"""The measurement: one number, in the engine's preferred shape."""
import pathlib

value = int(pathlib.Path("src/value.txt").read_text().strip())
print(f"METRIC value={value}")
'''

GUARD_PY = '''"""The guard: a candidate that breaks behaviour has no business scoring."""
import pathlib
import sys

raw = pathlib.Path("src/value.txt").read_text().strip()
sys.exit(0 if raw.lstrip("-").isdigit() and int(raw) >= 0 else 1)
'''

DECREMENT = '''import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(int(path.read_text().strip()) - 3))
print("CHANGE: decrement value by 3")
'''


def engine(*args, cwd, timeout=240):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ENGINE)
    return subprocess.run(
        [sys.executable, "-m", "autoresearch", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env,
    )


def git(repo, *args, timeout=120):
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=timeout
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr.strip()}"
    return proc


def scratch(tmp_path):
    """A checkout whose metric is src/value.txt, and an objective record beside it."""
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "target@example.com")
    git(repo, "config", "user.name", "Target")
    (repo / "src").mkdir()
    (repo / "src" / "value.txt").write_text("10\n", encoding="utf-8")
    (repo / "score.py").write_text(SCORE_PY, encoding="utf-8")
    (repo / "guard.py").write_text(GUARD_PY, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "init")
    objective = {
        "objectives": [{
            "id": "demo-game",
            "parent": None,
            "status": "active",
            "legs": [{
                "name": "value",
                "direction": "lower",
                "unit": "points",
                "command": f"{sys.executable} score.py",
                "repeats": 1,
                "noise_floor": 0.01,
                "guard": f"{sys.executable} guard.py",
            }],
            "weights": {"value": 1.0},
            "seasons": [],
            "rounds": [],
            "reason": "one leg at weight one — the degenerate case",
        }]
    }
    path = tmp_path / "objective.json"
    path.write_text(json.dumps(objective), encoding="utf-8")
    return repo, path


def replay(tmp_path, repo):
    """A real patch from the baseline, as the engine's replay JSONL."""
    (repo / "src" / "value.txt").write_text("7\n", encoding="utf-8")
    patch = git(repo, "diff").stdout
    git(repo, "checkout", "--", "src/value.txt")
    assert patch.strip()
    path = tmp_path / "records.jsonl"
    path.write_text(
        json.dumps({"iteration": 1, "description": "lower value", "patch": patch}) + "\n",
        encoding="utf-8",
    )
    return path


def objective_run(tmp_path):
    """init --objective (no metric flags), one replay keep, a report — the whole path."""
    repo, objective = scratch(tmp_path)
    init = engine("init", "--repo", str(repo), "--scope", "src",
                  "--objective", str(objective), cwd=tmp_path)
    assert init.returncode == 0, init.stderr
    run = engine("run", "--repo", str(repo), "--agent", "replay",
                 "--replay", str(replay(tmp_path, repo)),
                 "--max-iterations", "1", cwd=tmp_path)
    assert run.returncode == 0, run.stderr
    return repo, objective


def test_an_objective_record_drives_a_real_replay(tmp_path):
    """AC-OBJ-201: one leg at weight one initialises and keeps, with no metric flags."""
    repo, objective = objective_run(tmp_path)
    cfg = json.loads((repo / ".autoresearch" / "run.json").read_text(encoding="utf-8"))
    assert cfg["objective_id"] == "demo-game"
    assert cfg["objective_leg"] == "value"
    assert cfg["objective"] == str(objective.resolve())
    assert cfg["metric_name"] == "value"
    assert cfg["direction"] == "lower"
    assert cfg["verify"] == f"{sys.executable} score.py"
    assert cfg["repeats"] == 1
    assert (repo / "src" / "value.txt").read_text(encoding="utf-8").strip() == "7"

    status = engine("status", "--repo", str(repo), cwd=tmp_path)
    assert status.returncode == 0, status.stderr
    assert "ledger: valid" in status.stdout
    assert engine("report", "--repo", str(repo), cwd=tmp_path).returncode == 0
    report = (repo / ".autoresearch" / "report.md").read_text(encoding="utf-8")
    assert "- objective: `demo-game` (leg `value`)" in report
    assert git(repo, "status", "--porcelain").stdout == ""


def test_the_close_record_passes_check_and_re_renders_byte_identically(tmp_path):
    """AC-REC-201: report --record leaves a record --check reproduces byte for byte."""
    repo, _ = objective_run(tmp_path)
    written = engine("report", "--repo", str(repo), "--record", cwd=tmp_path)
    assert written.returncode == 0, written.stderr
    json_path = repo / ".autoresearch" / "record.json"
    md_path = repo / ".autoresearch" / "record.md"
    assert json_path.is_file() and md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["objective_id"] == "demo-game"
    assert record["pending"] is False
    assert record["readings"][0]["verdict"] == "improved"
    assert record["readings"][0]["raw"] == "METRIC value=7"
    assert record["readings"][0]["unit"] == "points"
    assert record["keeps"][0]["leg"] == "value"
    assert record["close_commit"] == record["keeps"][0]["commit"]

    first = engine("report", "--repo", str(repo), "--check", cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    assert "byte-identical" in first.stdout
    assert engine("report", "--repo", str(repo), "--check", cwd=tmp_path).returncode == 0

    md_path.write_text(md_path.read_text(encoding="utf-8") + "!", encoding="utf-8")
    drifted = engine("report", "--repo", str(repo), "--check", cwd=tmp_path)
    assert drifted.returncode == 2
    assert "record.md differs from a fresh render" in drifted.stderr
