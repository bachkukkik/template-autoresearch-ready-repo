"""PRD 21 — the unattended-loop recipe. IDs: AC-URC-001..024.

Hermetic: every case builds its own scheduler store, profile root and repo under
``tmp_path``. The scheduler is a fake CLI whose argv is logged and whose jobs store
is JSON, so a test asserts both the end state and the commands that produced it —
including the commands that must *not* be issued (no pause, no resume, no copy on a
dry run). The engine is either a stub script (prompt tests) or the real engine on a
throwaway git repo (the marker test).

The red-proofs are deliberate: AC-URC-005 snapshots the tree, AC-URC-017 asserts the
naive literal guard *fails* on the real argv shape, AC-URC-018 parses the AST for
``shell=True`` and a missing timeout with a negative control, and AC-URC-024 runs the
installer against a binding that is not the shipped one.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from importlib import util as importlib_util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = ROOT / "autoresearch" / "supervisor"
RECIPE = SUPERVISOR / "overnight"
ENGINE = ROOT / "autoresearch" / "engine"
CONFIG_NAME = "autoresearch-overnight-launch.config.json"


def _load(name, path):
    """Load a module by path under a name of its own — no package, no sys.path edit."""
    spec = importlib_util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = _load("sup_schema", SUPERVISOR / "schema.py")
guards = _load("sup_guards", SUPERVISOR / "guards.py")
install = _load("sup_install", SUPERVISOR / "install.py")
control = _load("sup_control", SUPERVISOR / "control.py")
launch = _load("sup_launch", RECIPE / "launch.py")
binding = install.load_binding("hermes")


# ─── the fake scheduler ──────────────────────────────────────────────────────

FAKE_BODY = '''
import json
import os
import secrets
import sys
from pathlib import Path

STORE = Path(os.environ["FAKE_JOBS"])
LOG = os.environ.get("FAKE_LOG")
ROOT = Path(os.environ["FAKE_ROOT"])
PROFILE = "default"


def jobs():
    if not STORE.is_file():
        return []
    return json.loads(STORE.read_text()).get("jobs", [])


def save(found):
    STORE.write_text(json.dumps({"jobs": found}, indent=1))
    home = ROOT if PROFILE == "default" else ROOT / "profiles" / PROFILE
    (home / "cron").mkdir(parents=True, exist_ok=True)
    (home / "cron" / "jobs.json").write_text(json.dumps({"jobs": found}, indent=1))


def render(found):
    print("Jobs for profile " + PROFILE + ":")
    for job in found:
        print("  " + job["id"] + " [" + job["state"] + "]")
        print("    Name: " + job["name"])
        print("    Schedule: " + str(job["schedule"]))
        print("    Script: " + str(job["script"]))
        print("    Next run: " + str(job["next_run"]))


def flag(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv):
    global PROFILE
    if LOG:
        with Path(LOG).open("a") as handle:
            handle.write(" ".join(argv) + "\\n")
    if argv[:1] == ["-p"] and len(argv) > 1:
        PROFILE = argv[1]
        argv = argv[2:]
    if argv[:2] == ["cron", "list"]:
        render(jobs())
        return 0
    found = jobs()
    if argv[:2] == ["cron", "create"]:
        new = {"id": secrets.token_hex(6), "state": "active", "name": flag(argv, "--name"),
               "schedule": flag(argv, "--schedule"), "script": flag(argv, "--script"),
               "next_run": "2026-11-17 00:00 UTC"}
        found.append(new)
        if os.environ.get("FAKE_DUPLICATE"):
            found.append({**new, "id": secrets.token_hex(6)})
        save(found)
        print("created")
        return 0
    if argv[:2] == ["cron", "edit"]:
        for job in found:
            if job["id"] == argv[2]:
                job["schedule"] = flag(argv, "--schedule", job["schedule"])
                job["script"] = flag(argv, "--script", job["script"])
        save(found)
        print("edited")
        return 0
    if argv[:2] in (["cron", "pause"], ["cron", "resume"]):
        if not os.environ.get("FAKE_NOOP"):
            wanted = "paused" if argv[1] == "pause" else "active"
            for job in found:
                if job["id"] == argv[2]:
                    job["state"] = wanted
        save(found)
        print(argv[1] + "ed")
        return 0
    print("unsupported: " + " ".join(argv), file=sys.stderr)
    return 2


sys.exit(main(sys.argv[1:]))
'''


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """A profile root, a fake scheduler binary and its store, all under tmp_path."""
    for name in ("HERMES_ROOT", "HERMES_HOME", "HERMES_BIN", "HERMES_PROFILE",
                 "FAKE_DUPLICATE", "FAKE_NOOP"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "harness"
    home = root / "profiles" / "overnight"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("model: x\n", encoding="utf-8")
    binary = tmp_path / "hermes"
    binary.write_text(f"#!{sys.executable}\n" + FAKE_BODY, encoding="utf-8")
    binary.chmod(0o755)
    store = tmp_path / "jobs.json"
    log = tmp_path / "argv.log"
    monkeypatch.setenv("FAKE_JOBS", str(store))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_ROOT", str(root))
    return types.SimpleNamespace(tmp=tmp_path, root=root, home=home, binary=binary,
                                 store=store, log=log)


def jobs_of(harness):
    return json.loads(harness.store.read_text())["jobs"] if harness.store.is_file() else []


def seed(harness, **overrides):
    job = {"id": "abc123", "state": "active", "name": "autoresearch-overnight",
           "schedule": "every 60m", "script": "autoresearch-overnight-launch.py",
           "next_run": "2026-11-17 00:00 UTC"}
    job.update(overrides)
    harness.store.write_text(json.dumps({"jobs": [job]}, indent=1))
    return job


def argv_log(harness):
    return harness.log.read_text().splitlines() if harness.log.is_file() else []


def run_install(harness, *extra):
    return install.main([str(RECIPE), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", str(harness.binary), *extra], binding=binding)


def run_control(harness, verb, *extra):
    return control.main([verb, str(RECIPE), "--profile", "overnight", "--root",
                         str(harness.root), "--bin", str(harness.binary), *extra],
                        binding=binding)


def snapshot(base):
    """Every file and directory under ``base`` with its digest — a tree a dry run may not move."""
    found = {}
    for path in sorted(Path(base).rglob("*")):
        rel = path.relative_to(base).as_posix()
        found[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
    return found


def write_installed_config(harness, data):
    scripts = harness.home / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / CONFIG_NAME).write_text(json.dumps(data), encoding="utf-8")


# ─── recipe schema ───────────────────────────────────────────────────────────


def test_shipped_recipe_validates_and_documents_its_keys():
    """AC-URC-001: the recipe on disk passes the schema, and the schema names every key."""
    recipe, problems = schema.load(RECIPE / "recipe.json")
    assert problems == []
    assert schema.validate(recipe, RECIPE) == []
    assert set(recipe) <= set(schema.SCHEMA), set(recipe) - set(schema.SCHEMA)
    for key in schema.REQUIRED:
        assert key in recipe, key


def test_schema_refuses_a_recipe_that_would_install_nothing(tmp_path):
    """AC-URC-001b: each defect is reported, and a missing source file is one of them."""
    ok = {"name": "r", "schedule": "every 60m", "script": "run.py", "files": {"a.py": "run.py"}}
    (tmp_path / "a.py").write_text("print('x')\n")
    assert schema.validate(ok, tmp_path) == []

    without = lambda key: {k: v for k, v in ok.items() if k != key}
    cases = [
        ("name", without("name")),
        ("schedule", {**ok, "schedule": ""}),
        ("files", {**ok, "files": []}),
        ("files", {**ok, "files": {}}),
        ("script", {**ok, "script": "other.py"}),
        ("config_renames", {**ok, "config_renames": ["workspace", "repo"]}),
        ("no_agent", {**ok, "no_agent": "yes"}),
    ]
    for needle, broken in cases:
        problems = schema.validate(broken, tmp_path)
        assert any(needle in problem for problem in problems), (needle, problems)

    missing = schema.validate({**ok, "files": {"gone.py": "run.py"}}, tmp_path)
    assert any("gone.py" in problem for problem in missing)
    nested = schema.validate({**ok, "files": {"a.py": "sub/run.py"}}, tmp_path)
    assert any("bare filename" in problem for problem in nested)
    assert schema.load(tmp_path / "absent.json")[1]


# ─── install: copies, config, idempotence ────────────────────────────────────


def test_install_copies_byte_equal_files(harness):
    """AC-URC-002: the installed copy is the recipe's bytes, not a re-render."""
    assert run_install(harness) == 0
    recipe, _ = schema.load(RECIPE / "recipe.json")
    for source, installed in recipe["files"].items():
        after = harness.home / "scripts" / installed
        assert after.is_file(), installed
        assert (RECIPE / source).read_bytes() == after.read_bytes(), source


def test_config_merge_order_keeps_operator_edits_and_set_wins(harness):
    """AC-URC-003: example <- installed <- --set, and an unknown key survives."""
    write_installed_config(harness, {"idle_minutes": 3, "operator_key": "keep"})
    assert run_install(harness, "--set", "idle_minutes=7") == 0
    config = json.loads((harness.home / "scripts" / CONFIG_NAME).read_text())
    assert config["idle_minutes"] == 7
    assert config["operator_key"] == "keep"
    assert config["timezone"] == "UTC"


def test_config_renames_fold_before_the_merge(harness):
    """AC-URC-004: a retired key moves; the new key wins; the old name never lingers."""
    write_installed_config(harness, {"workspace": "/old"})
    assert run_install(harness) == 0
    config = json.loads((harness.home / "scripts" / CONFIG_NAME).read_text())
    assert config["repo"] == "/old"
    assert "workspace" not in config

    write_installed_config(harness, {"workspace": "/old", "repo": "/new"})
    assert run_install(harness) == 0
    config = json.loads((harness.home / "scripts" / CONFIG_NAME).read_text())
    assert config["repo"] == "/new"
    assert "workspace" not in config

    # The rename must reach the file even when nothing else changed: the comparison base
    # is the config on disk, not the dict the rename just mutated.
    example = json.loads((RECIPE / "config.example.json").read_text())
    without_repo = {key: value for key, value in example.items() if key != "repo"}
    write_installed_config(harness, {**without_repo, "workspace": "/moved"})
    assert run_install(harness) == 0
    on_disk = json.loads((harness.home / "scripts" / CONFIG_NAME).read_text())
    assert on_disk["repo"] == "/moved" and "workspace" not in on_disk

    moved = install.apply_renames({"a": 1}, {"a": "b"})
    assert moved == ["a -> b"]
    assert install.apply_renames({"a": 1, "b": 2}, {"a": "b"}) == ["a -> b"]


def test_dry_run_writes_nothing_and_issues_only_reads(harness, capsys):
    """AC-URC-005: the tree is identical after a dry run, and only the listing ran."""
    before = snapshot(harness.root)
    assert run_install(harness, "--dry-run") == 0
    assert snapshot(harness.root) == before
    assert not (harness.home / "scripts").exists()
    assert argv_log(harness) == ["-p overnight cron list --all"]
    out = capsys.readouterr().out
    assert "would copy" in out and "would run" in out and "[dry-run, nothing written]" in out
    # The recipe's own note is printed with the plan — the operator reads the schedule's
    # reason before installing it, not after.
    note = json.loads((RECIPE / "recipe.json").read_text())["note"]
    assert f"note: {note}" in out


def _copied_recipe(tmp_path, example_text=None):
    """A writable copy of the shipped recipe, for cases that must corrupt one file."""
    target = tmp_path / "recipe"
    target.mkdir(parents=True)
    for name in ("recipe.json", "config.example.json", "launch.py", "prompt.tmpl.txt",
                 "charter.md"):
        (target / name).write_text((RECIPE / name).read_text(), encoding="utf-8")
    if example_text is not None:
        (target / "config.example.json").write_text(example_text, encoding="utf-8")
    return target


def test_malformed_configs_are_refused_cleanly(harness, tmp_path, capsys):
    """AC-URC-003b: a config that is not an object is exit 2, never a traceback."""
    before = snapshot(harness.root)

    arrays = _copied_recipe(tmp_path / "arrays", example_text="[1, 2, 3]\n")
    assert install.main([str(arrays), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", str(harness.binary)], binding=binding) == 2
    err = capsys.readouterr().err
    assert "config example" in err and "not a JSON object" in err

    broken = _copied_recipe(tmp_path / "broken", example_text="{not json")
    assert install.main([str(broken), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", str(harness.binary)], binding=binding) == 2
    assert "cannot read the recipe's config example" in capsys.readouterr().err
    assert snapshot(harness.root) == before

    write_installed_config(harness, [1, 2, 3])
    before = snapshot(harness.root)
    assert install.main([str(RECIPE), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", str(harness.binary)], binding=binding) == 2
    err = capsys.readouterr().err
    assert "installed config" in err and "not a JSON object" in err
    assert snapshot(harness.root) == before
    assert not harness.store.exists(), "a refused install must not create a job"


# ─── root resolution and its gate ────────────────────────────────────────────


def test_root_resolution_order_never_reads_home(monkeypatch):
    """AC-URC-006: --root -> HERMES_ROOT -> HERMES_HOME -> cwd, with the source named."""
    env = {"HERMES_ROOT": "/root-env", "HERMES_HOME": "/home-root/profiles/p", "HOME": "/decoy"}
    assert install.resolve_root(binding, "/arg", env, "/cwd") == (Path("/arg"), "--root")
    assert install.resolve_root(binding, None, env, "/cwd") == (Path("/root-env"), "HERMES_ROOT")
    assert install.resolve_root(binding, None, {"HERMES_HOME": "/home-root/profiles/p"},
                                "/cwd") == (Path("/home-root"), "HERMES_HOME")
    assert install.resolve_root(binding, None, {"HERMES_HOME": "/plain/home"},
                                "/cwd") == (Path("/plain/home"), "HERMES_HOME")
    assert install.resolve_root(binding, None, {"HOME": "/decoy/.hermes"},
                                "/cwd") == (Path("/cwd"), "cwd")
    monkeypatch.setenv("HOME", "/decoy")
    assert install._expand("~/x") != Path("/decoy/x")


def test_root_gate_refuses_a_directory_that_is_not_a_profile(harness, capsys):
    """AC-URC-007: no profile marker -> exit 2, nothing copied, nothing called."""
    elsewhere = harness.tmp / "elsewhere"
    elsewhere.mkdir()
    before = snapshot(harness.tmp)
    code = install.main([str(RECIPE), "--profile", "overnight", "--root", str(elsewhere),
                         "--bin", str(harness.binary)], binding=binding)
    assert code == 2
    assert snapshot(harness.tmp) == before
    assert argv_log(harness) == []
    assert "not a profile" in capsys.readouterr().err


# ─── install: create-vs-edit, duplicates, verification, no resume ────────────


def test_second_install_edits_the_same_job(harness):
    """AC-URC-008: one job after two installs, and the second command is an edit of its id."""
    assert run_install(harness) == 0
    first = jobs_of(harness)
    assert len(first) == 1
    assert run_install(harness) == 0
    second = jobs_of(harness)
    assert len(second) == 1
    log = argv_log(harness)
    assert any("cron create --name autoresearch-overnight" in line for line in log)
    assert any(f"cron edit {first[0]['id']}" in line for line in log)


def test_duplicate_job_is_refused_with_both_ids(harness, capsys):
    """AC-URC-009: two jobs of the recipe's name -> exit 2 naming both, nothing written."""
    harness.store.write_text(json.dumps({"jobs": [
        {"id": "aaa111", "state": "active", "name": "autoresearch-overnight",
         "schedule": "every 60m", "script": "x.py", "next_run": "-"},
        {"id": "bbb222", "state": "paused", "name": "autoresearch-overnight",
         "schedule": "every 60m", "script": "x.py", "next_run": "-"},
    ]}), encoding="utf-8")
    before = snapshot(harness.root)
    assert run_install(harness) == 2
    err = capsys.readouterr().err
    assert "aaa111" in err and "bbb222" in err
    assert snapshot(harness.root) == before


def test_state_hint_with_no_listed_job_refuses_to_create(harness, capsys):
    """AC-URC-009b: a hint the listing cannot see is a refusal, not a create.

    The state file says this profile already owns a job of the recipe's name; the listing
    (which decides) shows none. Creating there mints the duplicate job downstream paid
    for, so the install stops at exit 2 and names the stored id.
    """
    (harness.home / "cron").mkdir(parents=True)
    (harness.home / "cron" / "jobs.json").write_text(json.dumps({"jobs": [
        {"id": "st0red", "state": "active", "name": "autoresearch-overnight",
         "schedule": "every 60m", "script": "x.py", "next_run": "-"}]}), encoding="utf-8")
    before = snapshot(harness.root)

    assert run_install(harness) == 2
    err = capsys.readouterr().err
    assert "st0red" in err and "control.py status" in err
    assert "refusing to create" in err
    assert not harness.store.exists(), "a refused install must not create a job"
    assert snapshot(harness.root) == before


def test_unreadable_listing_is_never_an_empty_match_list(harness, tmp_path, capsys):
    """AC-URC-010: a listing that fails -> exit 2, and create is not guessed."""
    broken = tmp_path / "broken-scheduler"
    broken.write_text(f"#!{sys.executable}\nimport sys\nprint('no scheduler', file=sys.stderr)\n"
                      f"sys.exit(3)\n", encoding="utf-8")
    broken.chmod(0o755)
    before = snapshot(harness.root)
    code = install.main([str(RECIPE), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", str(broken)], binding=binding)
    assert code == 2
    assert snapshot(harness.root) == before
    assert "refusing to guess create vs edit" in capsys.readouterr().err


def test_install_never_resumes_a_paused_job(harness):
    """AC-URC-011: install leaves the state alone, and never issues pause or resume."""
    seed(harness, state="paused")
    assert run_install(harness) == 0
    assert jobs_of(harness)[0]["state"] == "paused"
    assert not [line for line in argv_log(harness) if "cron pause" in line or "cron resume" in line]


def test_post_install_verify_fails_when_the_listing_shows_two(harness, monkeypatch, capsys):
    """AC-URC-012: a create that minted a second job is a failed install (exit 1)."""
    monkeypatch.setenv("FAKE_DUPLICATE", "1")
    assert run_install(harness) == 1
    assert "expected exactly one job" in capsys.readouterr().err


# ─── control: status, pause, resume re-read after mutating ───────────────────


def test_control_status_pause_resume(harness, capsys):
    """AC-URC-013: status is read-only; pause/resume re-read and only then exit 0."""
    seed(harness)
    assert run_control(harness, "status") == 0
    out = capsys.readouterr().out
    assert "abc123" in out and "state:" in out and "next run:" in out
    assert not [line for line in argv_log(harness) if "cron pause" in line]

    assert run_control(harness, "pause") == 0
    assert jobs_of(harness)[0]["state"] == "paused"
    assert run_control(harness, "resume") == 0
    assert jobs_of(harness)[0]["state"] == "active"


def test_control_fails_closed_on_no_job_duplicates_and_a_noop_mutation(harness, monkeypatch,
                                                                       capsys):
    """AC-URC-013b: 0 or 2 matches exit 2; a mutation that did not move exits 1."""
    assert run_control(harness, "status") == 2
    assert "install it first" in capsys.readouterr().err

    harness.store.write_text(json.dumps({"jobs": [
        {"id": "a1", "state": "active", "name": "autoresearch-overnight",
         "schedule": "s", "script": "x", "next_run": "-"},
        {"id": "b2", "state": "active", "name": "autoresearch-overnight",
         "schedule": "s", "script": "x", "next_run": "-"},
    ]}), encoding="utf-8")
    assert run_control(harness, "pause") == 2
    assert "remove the duplicates first" in capsys.readouterr().err

    seed(harness)
    monkeypatch.setenv("FAKE_NOOP", "1")
    assert run_control(harness, "pause") == 1
    assert "exited 0 but the job reads" in capsys.readouterr().err


# ─── the guard ladder, as pure functions ─────────────────────────────────────


def _at(hour, minute=0):
    return datetime(2026, 11, 16, hour, minute, tzinfo=timezone.utc)


def test_window_boundaries_and_zones():
    """AC-URC-014: [start, end), wrap, equal-hours, and a named zone that is not UTC."""
    assert guards.in_window(_at(0), 0, 7, "UTC") is True
    assert guards.in_window(_at(6, 59), 0, 7, "UTC") is True
    assert guards.in_window(_at(7, 0), 0, 7, "UTC") is False
    assert guards.in_window(_at(23), 22, 6, "UTC") is True
    assert guards.in_window(_at(3), 22, 6, "UTC") is True
    assert guards.in_window(_at(12), 22, 6, "UTC") is False
    assert guards.in_window(_at(12), 5, 5, "UTC") is True
    assert guards.in_window(_at(12), 0, 7, "Asia/Bangkok") is False
    with pytest.raises(Exception):
        guards.in_window(_at(12), 0, 7, "Not/AZone")


def test_busy_session_reads_every_session_and_the_idle_floor():
    """AC-URC-015: streaming blocks, a quiet floor blocks, another profile does not."""
    now = 1_800_000_000.0
    streaming = [{"session_id": "s1", "profile": "p", "is_streaming": True, "updated_at": 0}]
    assert guards.busy_session(streaming, now=now, idle_minutes=10, profile="p") == "s1"
    recent = [{"session_id": "s2", "profile": "p", "updated_at": now - 120}]
    assert guards.busy_session(recent, now=now, idle_minutes=10, profile="p") == "s2"
    old = [{"session_id": "s3", "profile": "p", "updated_at": now - 11 * 60}]
    assert guards.busy_session(old, now=now, idle_minutes=10, profile="p") is None
    other = [{"session_id": "s4", "profile": "q", "updated_at": now - 60}]
    assert guards.busy_session(other, now=now, idle_minutes=10, profile="p") is None
    assert guards.busy_session([], now=now, idle_minutes=10, profile="p") is None


def test_marker_state_fails_closed(tmp_path):
    """AC-URC-016: absent -> clear; live -> block; dead pid -> clear; unreadable -> block."""
    marker = tmp_path / "round.marker"
    assert guards.marker_state(marker) == (False, "no marker")

    marker.write_text(json.dumps({"pid": os.getpid(), "epoch": time.time(), "started": "now"}))
    blocking, reason = guards.marker_state(marker)
    assert blocking is True and "run pid" in reason

    live = subprocess.Popen([sys.executable, "-c", "pass"])
    live.wait()
    marker.write_text(json.dumps({"pid": live.pid, "epoch": time.time(), "started": "then"}))
    assert guards.marker_state(marker)[0] is False

    marker.write_text("{not json")
    assert guards.marker_state(marker)[0] is True
    marker.write_text(json.dumps({"started": "no pid"}))
    assert guards.marker_state(marker)[0] is True
    marker.write_text(json.dumps({"pid": os.getpid(), "started": "no epoch"}))
    assert guards.marker_state(marker)[0] is True


REAL_RUN = "python3 -P -m autoresearch run --repo /r --agent command --max-iterations 2"
FLAGGED_RUN = "python3 -P -m autoresearch --repo /r run --agent command"
NON_ROUNDS = [
    "python3 -P -m autoresearch status --repo /r",
    "python3 -P -m autoresearch objective resolve --leg val_bpb",
    "vim autoresearch/README.md",
    "bash bin/autoresearch doctor",
    "grep -r autoresearch/ docs/",
]


def test_round_marker_matches_the_argv_shape_actually_used():
    """AC-URC-017: the broad prefilter sees the line, the specific pattern decides."""
    assert guards.process_in_flight([REAL_RUN]) == REAL_RUN
    assert guards.process_in_flight([FLAGGED_RUN]) == FLAGGED_RUN
    for line in NON_ROUNDS:
        assert guards.process_in_flight([line]) is None, line
    for line in [REAL_RUN, FLAGGED_RUN]:
        assert re.search(guards.ROUND_PREFILTER, line)

    naive = re.compile(r"autoresearch run")
    assert naive.search(REAL_RUN)
    assert not naive.search(FLAGGED_RUN), "the literal guard must fail on flags — that was PR #40"
    assert guards.ROUND_PATTERN.search(FLAGGED_RUN)


def _subprocess_problems(paths):
    problems = []
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "run" or getattr(node.func.value, "id", "") != "subprocess":
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords}
            shell = keywords.get("shell")
            if isinstance(shell, ast.Constant) and shell.value:
                problems.append(f"{path}:{node.lineno} shell=True")
            if "timeout" not in keywords:
                problems.append(f"{path}:{node.lineno} no timeout")
    return problems


def test_no_shell_true_and_every_child_is_timed():
    """AC-URC-018: the new modules never use a shell and every child has a timeout."""
    paths = sorted(SUPERVISOR.glob("*.py")) + [RECIPE / "launch.py",
                                               ENGINE / "autoresearch" / "marker.py"]
    assert _subprocess_problems(paths) == []

    snippet = "import subprocess\nsubprocess.run(['x'], shell=True)\n"
    probe = Path(__file__).parent / f"_probe_shell_{os.getpid()}.py"
    probe.write_text(snippet, encoding="utf-8")
    try:
        found = _subprocess_problems([probe])
    finally:
        probe.unlink()
    assert any("shell=True" in item for item in found)
    assert any("no timeout" in item for item in found)


# ─── the prompt: rendered from repo state, naming only real commands ─────────

STUB_ENGINE = '''
import sys

if "status" in sys.argv:
    print("round 4 · value 10 -> 9 (kept)")
elif "doctor" in sys.argv:
    print("stub-adapter 1.0")
elif "--help" in sys.argv:
    print("usage: autoresearch {init,run,status,report,objective,doctor} ...")
else:
    print("unexpected argv: " + " ".join(sys.argv[1:]), file=sys.stderr)
    sys.exit(2)
'''


def stub_engine(tmp_path):
    path = tmp_path / "engine"
    path.write_text(f"#!{sys.executable}\n" + STUB_ENGINE, encoding="utf-8")
    path.chmod(0o755)
    return path


def prompt_context(tmp_path, state=None):
    engine = stub_engine(tmp_path)
    state = state or (tmp_path / "state")
    state.mkdir(exist_ok=True)
    cfg = launch.merge_config({"repo": str(ROOT), "engine": str(engine),
                               "state_dir": str(state)})
    return launch.gather_context(cfg, ROOT, str(engine)), engine, state


def test_prompt_renders_the_active_leg_record_and_charter(tmp_path):
    """AC-URC-019: objective leg, engine status/doctor, last verdict, charter — no placeholder."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "record.json").write_text(json.dumps({
        "verdict": "improved",
        "readings": [{"name": "val_bpb", "before": 1.2, "after": 1.1, "unit": "bits/byte"}],
    }), encoding="utf-8")
    ctx, engine, _ = prompt_context(tmp_path, state)
    text = launch.render(ctx, template_text=(RECIPE / "prompt.tmpl.txt").read_text())

    assert "template-val-bpb" in text and "val_bpb" in text
    assert "round 4 · value 10 -> 9" in text
    assert "stub-adapter 1.0" in text
    assert "verdict improved" in text and "1.2 -> 1.1" in text
    assert "ADOPTER-SUPPLIED" in text and "Overnight charter" in text
    assert "${" not in text and "<seconds>" not in text
    # The config speaks minutes; the engine's --max-wall takes seconds. One derived value.
    assert "--max-wall 2700" in text
    assert str(engine) in text


def test_prompt_objective_line_degrades_without_raising():
    """AC-URC-019b: a missing or broken record is a labelled string, never an exception."""
    assert "did not parse" in launch.objective_line("{not json")
    assert "no active objective" in launch.objective_line(json.dumps({"objectives": []}))
    line = launch.objective_line(json.dumps({"objectives": [{
        "id": "only", "status": "active", "legs": [{"name": "m", "direction": "higher",
                                                    "unit": "u", "command": "c",
                                                    "repeats": 1, "noise_floor": 0.1}],
        "weights": {"m": 1.0}, "rotation": ["m"]}]}))
    assert "only (active): leg m" in line and "higher is better" in line
    assert "guard '(none)'" in line


def test_prompt_names_only_commands_the_engine_has(tmp_path):
    """AC-URC-020: every verb the prompt names exists; an invented verb would fail."""
    from autoresearch import cli

    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    verbs = set(sub.choices) | {"profile"}
    ctx, engine, _ = prompt_context(tmp_path)
    text = launch.render(ctx, template_text=(RECIPE / "prompt.tmpl.txt").read_text())
    named = set(re.findall(re.escape(str(engine)) + r" ([a-z][a-z-]*)", text))
    assert named, text[:400]
    assert named <= verbs, named - verbs
    assert "frobnicate" not in verbs


# ─── the launcher: dry-run inert, ladder order, fire ─────────────────────────


def launcher_script(tmp_path, config):
    """An installed-shape directory: config, template and charter beside the script."""
    base = tmp_path / "scripts"
    base.mkdir()
    (base / "autoresearch-overnight-launch.config.json").write_text(json.dumps(config), encoding="utf-8")
    (base / "autoresearch-overnight-prompt.tmpl.txt").write_text(
        (RECIPE / "prompt.tmpl.txt").read_text(), encoding="utf-8")
    (base / "autoresearch-overnight-charter.md").write_text(
        (RECIPE / "charter.md").read_text(), encoding="utf-8")
    return base / "autoresearch-overnight-launch.py"


def base_config(tmp_path, **overrides):
    engine = stub_engine(tmp_path)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    config = {"repo": str(ROOT), "engine": str(engine), "state_dir": str(state),
              "webui_url": "http://127.0.0.1:9", "profile": "default",
              "overnight_start_hour": 0, "overnight_end_hour": 7, "timezone": "UTC"}
    config.update(overrides)
    return config


def test_launcher_dry_run_touches_nothing_and_consults_no_guard(tmp_path, monkeypatch, capsys):
    """AC-URC-021: --dry-run renders and returns before the guard helpers are even loaded."""
    script = launcher_script(tmp_path, base_config(tmp_path))
    before = snapshot(tmp_path)

    def explode(*args, **kwargs):
        raise AssertionError("a dry run must not load the guards")

    monkeypatch.setattr(launch, "helpers", explode)
    assert launch.main(["--dry-run"], script=script) == 0
    out = capsys.readouterr().out
    assert "template-val-bpb" in out and "${" not in out
    assert snapshot(tmp_path) == before


class StubBinding:
    """A binding-shaped object: the launcher's half of the interface only."""

    NAME = "stub"

    def __init__(self, sessions=None, error=None):
        self._sessions = sessions or []
        self._error = error
        self.fired = []

    def sessions(self, url, profile):
        if self._error:
            raise self._error
        return self._sessions

    def fire(self, url, profile, repo, prompt):
        self.fired.append(prompt)
        return "sid-1"


def wire(monkeypatch, stub, window=True, process=None):
    monkeypatch.setattr(launch, "helpers", lambda repo, name="hermes": (guards, stub))
    monkeypatch.setattr(guards, "in_window", lambda **kwargs: window)
    monkeypatch.setattr(guards, "live_process", lambda: process)


def test_launcher_api_error_logs_and_never_fires(tmp_path, monkeypatch):
    """AC-URC-022: an unreadable session API is a logged skip, not a blind fire."""
    script = launcher_script(tmp_path, base_config(tmp_path))
    stub = StubBinding(error=RuntimeError("connection refused"))
    wire(monkeypatch, stub)
    assert launch.main(["--force"], script=script) == 0
    log = (script.parent / "autoresearch-overnight.log").read_text()
    assert "api-error RuntimeError" in log and "not firing blind" in log
    assert stub.fired == []


def test_launcher_outside_the_window_is_silent(tmp_path, monkeypatch):
    """AC-URC-022b: outside [start, end) the tick ends with no log line and no call."""
    script = launcher_script(tmp_path, base_config(tmp_path))
    stub = StubBinding(sessions=[])
    wire(monkeypatch, stub, window=False)
    assert launch.main([], script=script) == 0
    assert not (script.parent / "autoresearch-overnight.log").exists()
    assert stub.fired == []


def test_launcher_busy_session_and_live_marker_both_block(tmp_path, monkeypatch):
    """AC-URC-022c: a working session blocks; so does a marker for a live run."""
    config = base_config(tmp_path)
    script = launcher_script(tmp_path, config)

    busy = StubBinding(sessions=[{"session_id": "s-live", "profile": "default",
                                  "is_streaming": True, "updated_at": 0}])
    wire(monkeypatch, busy)
    assert launch.main(["--force"], script=script) == 0
    assert busy.fired == []
    assert "s-live is live — no fire" in (script.parent / "autoresearch-overnight.log").read_text()

    marker = Path(config["state_dir"]) / "round.marker"
    marker.write_text(json.dumps({"pid": os.getpid(), "epoch": time.time(), "started": "now"}))
    idle = StubBinding(sessions=[])
    wire(monkeypatch, idle)
    assert launch.main(["--force"], script=script) == 0
    assert idle.fired == []
    assert "a run is in play" in (script.parent / "autoresearch-overnight.log").read_text()


def test_launcher_fires_once_and_records_the_session(tmp_path, monkeypatch, capsys):
    """AC-URC-022d: the idle tick fires one session with the rendered prompt and records it."""
    config = base_config(tmp_path)
    script = launcher_script(tmp_path, config)
    stub = StubBinding(sessions=[])
    wire(monkeypatch, stub)
    assert launch.main(["--force"], script=script) == 0
    assert len(stub.fired) == 1
    assert "template-val-bpb" in stub.fired[0] and "Overnight charter" in stub.fired[0]
    state = json.loads((script.parent / "autoresearch-overnight-state.json").read_text())
    assert state["session_id"] == "sid-1"
    assert "fired autoresearch session sid-1" in capsys.readouterr().out


def test_launcher_state_write_failure_does_not_fail_the_tick(tmp_path, monkeypatch, capsys):
    """AC-URC-022e: a fired session with an unwritable state file is still exit 0."""
    config = base_config(tmp_path)
    script = launcher_script(tmp_path, config)
    stub = StubBinding(sessions=[])
    wire(monkeypatch, stub)
    # An unwritable target, without depending on permissions: a directory where the JSON
    # file belongs makes read_text and write_text both raise OSError.
    (script.parent / "autoresearch-overnight-state.json").mkdir()

    assert launch.main(["--force"], script=script) == 0
    assert len(stub.fired) == 1
    log = (script.parent / "autoresearch-overnight.log").read_text()
    assert "fired sid-1 but the state file is unwritable" in log
    assert "fired autoresearch session sid-1" in capsys.readouterr().out


# ─── the engine writes the marker ───────────────────────────────────────────


def test_engine_run_writes_and_clears_the_round_marker(tmp_path):
    """AC-URC-023: a run announces itself in the marker file and removes it at exit."""
    from test_engine_support import init_run, make_target, run_args, run_cli, write_agent
    from autoresearch import marker as marker_mod

    # One spelling of both names across the writer and the guard, or the file the run
    # writes is not the file the ladder reads.
    assert (marker_mod.ENV, marker_mod.FILENAME) == (guards.MARKER_ENV, guards.MARKER_NAME)

    repo = make_target(tmp_path)
    init_run(repo)
    marker = repo / ".autoresearch" / "round.marker"
    seen = tmp_path / "seen.json"
    agent = write_agent(tmp_path, f'''
import json, pathlib
marker = pathlib.Path({str(marker)!r})
pathlib.Path({str(seen)!r}).write_text(marker.read_text() if marker.is_file() else "ABSENT")
print("CHANGE: nothing to do")
''')
    assert run_cli(run_args(repo, agent, extra=["--max-iterations", "1"])) == 0
    assert not marker.exists()
    payload = json.loads(seen.read_text())
    assert isinstance(payload, dict) and payload["pid"] > 0
    assert payload["repo"] == str(repo)


# ─── the installer is scheduler-agnostic ────────────────────────────────────


class FakeBinding:
    """A second scheduler: every name the installer and controller use, no Hermes anywhere."""

    NAME = "fake"
    ROOT_ENV = ("FAKE_ROOT", "FAKE_SCOPE")
    BIN_ENV = "FAKE_BIN"
    PROFILE_ENV = "FAKE_PROFILE"

    def __init__(self):
        self.calls = []
        self.jobs = []

    def root_from_home(self, value):
        path = Path(value)
        return path.parent.parent if path.parent.name == "profiles" else path

    def profile_home(self, root, profile):
        root = Path(root)
        return root if profile == "default" else root / "profiles" / profile

    def is_profile(self, home):
        return (Path(home) / "config.yaml").is_file()

    def cli_env(self, root):
        return {**os.environ, "FAKE_SCOPE": str(root)}

    def list_jobs(self, binary, profile, root):
        self.calls.append("list")
        return list(self.jobs), None

    def job_argv(self, binary, profile, recipe, job_id=None):
        self.calls.append(("job", job_id))
        if job_id is None:
            self.jobs = [{"id": "fake-1", "state": "active", "name": recipe["name"],
                          "schedule": recipe["schedule"], "script": recipe["script"],
                          "next_run": "later"}]
        return [sys.executable, "-c", "pass"]

    def state_argv(self, binary, profile, verb, job_id):
        return [sys.executable, "-c", "pass"]

    def sessions(self, url, profile):
        return []

    def fire(self, url, profile, repo, prompt):
        return "sid"

    def read_hint(self, home, name):
        return None


def test_install_runs_against_a_binding_that_is_not_hermes(harness):
    """AC-URC-024: the installer's only scheduler knowledge is the binding it is given."""
    fake = FakeBinding()
    code = install.main([str(RECIPE), "--profile", "overnight", "--root", str(harness.root),
                         "--bin", "fake-scheduler"], binding=fake)
    assert code == 0
    assert fake.calls == ["list", ("job", None), "list"]
    assert (harness.home / "scripts" / "autoresearch-overnight-launch.py").is_file()
    # The seam, in source: no caller carries a scheduler command, env name or alias. The
    # binding module is exempt — it *is* the scheduler.
    for name in ("install.py", "control.py", "overnight/launch.py"):
        source = (SUPERVISOR / name).read_text(encoding="utf-8")
        for coupling in ("cron list", "cron create", "cron edit", "cron pause", "cron resume",
                         "HERMES_", "--hermes-root"):
            assert coupling not in source, (name, coupling)


def test_launcher_helpers_resolve_from_the_real_repo():
    """AC-URC-024b: the real modules load by path — unpatched, so a broken helper is red.

    Every launcher test patches ``helpers``; a helper that cannot be imported would then
    stay green while every real fire skipped. This case imports the shipped pair the way
    a fire does and asserts the functions the ladder calls are on them.
    """
    guard_mod, binding_mod = launch.helpers(ROOT, "hermes")

    assert guard_mod.__file__ == str(SUPERVISOR / "guards.py")
    assert binding_mod.__file__ == str(SUPERVISOR / "hermes_binding.py")
    for name in ("in_window", "busy_session", "marker_state", "marker_path",
                 "live_process", "log_skip"):
        assert callable(getattr(guard_mod, name)), name
    for name in ("NAME", "URL_ENV", "sessions", "fire", "list_jobs", "profile_home"):
        assert hasattr(binding_mod, name), name
    assert binding_mod.NAME == "hermes"
    # The failures are a named exception, not an ImportError from the loader.
    with pytest.raises(launch.HelpersUnavailable):
        launch.helpers(ROOT / "no-such-repo", "hermes")
    with pytest.raises(launch.HelpersUnavailable):
        launch.helpers(ROOT, "no-such-binding")
