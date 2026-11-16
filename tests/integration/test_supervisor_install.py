"""PRD 21 — the install/launch path as the scheduler actually runs it. IDs: AC-URC-201..203.

The unit tier drives the installer in-process; this tier runs the real scripts as
children, which is a different claim: the shebang, the argv the wrapper passes, the
exit codes a scheduler sees, the config written beside the *installed* script, and the
template/charter resolved by their installed names. The scheduler is a fake CLI whose
jobs store is JSON — never a real one — so the tier stays hermetic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "autoresearch" / "supervisor" / "overnight"
INSTALL = ROOT / "autoresearch" / "supervisor" / "install.py"
CONTROL = ROOT / "autoresearch" / "supervisor" / "control.py"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_supervisor_recipe import FAKE_BODY  # noqa: E402  — one fake scheduler, one definition


def build(tmp_path):
    """A profile root, a fake scheduler binary and its store, all under tmp_path."""
    root = tmp_path / "harness"
    home = root / "profiles" / "overnight"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("model: x\n", encoding="utf-8")
    binary = tmp_path / "hermes"
    binary.write_text(f"#!{sys.executable}\n" + FAKE_BODY, encoding="utf-8")
    binary.chmod(0o755)
    stub = tmp_path / "engine"
    stub.write_text(f"#!{sys.executable}\n"
                    "import sys\n"
                    "if 'status' in sys.argv:\n"
                    "    print('round 2 · value 10 -> 10 (held)')\n"
                    "elif 'doctor' in sys.argv:\n"
                    "    print('stub-adapter 1.0')\n"
                    "else:\n"
                    "    print('usage: autoresearch {init,run,status,report,objective,doctor}')\n",
                    encoding="utf-8")
    stub.chmod(0o755)
    env = {**os.environ,
           "FAKE_JOBS": str(tmp_path / "jobs.json"),
           "FAKE_LOG": str(tmp_path / "argv.log"),
           "FAKE_ROOT": str(root)}
    for name in ("HERMES_ROOT", "HERMES_HOME", "HERMES_BIN", "HERMES_PROFILE"):
        env.pop(name, None)
    return {"root": root, "home": home, "binary": binary, "stub": stub, "env": env,
            "store": tmp_path / "jobs.json", "log": tmp_path / "argv.log", "tmp": tmp_path}


def run(argv, env, cwd=None):
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, env=env,
                          cwd=str(cwd or ROOT))


def install_argv(harness, *extra, via_wrapper=False):
    if via_wrapper:
        argv = ["bash", str(RECIPE / "install.sh")]
    else:
        argv = [sys.executable, str(INSTALL), str(RECIPE)]
    return argv + ["--profile", "overnight", "--root", str(harness["root"]),
                   "--bin", str(harness["binary"]), *extra]


def jobs_of(harness):
    store = harness["store"]
    return json.loads(store.read_text())["jobs"] if store.is_file() else []


def test_install_through_the_script_lands_one_job(tmp_path):
    """AC-URC-201: the child install exits 0, copies the bytes and the store shows the job."""
    harness = build(tmp_path)
    done = run(install_argv(harness), harness["env"])
    assert done.returncode == 0, done.stderr
    assert "[installed, verified]" in done.stdout
    jobs = jobs_of(harness)
    assert len(jobs) == 1 and jobs[0]["name"] == "autoresearch-overnight"
    assert jobs[0]["state"] == "active"
    installed = harness["home"] / "scripts" / "autoresearch-overnight-launch.py"
    assert installed.read_bytes() == (RECIPE / "launch.py").read_bytes()

    again = run(install_argv(harness), harness["env"])
    assert again.returncode == 0, again.stderr
    assert len(jobs_of(harness)) == 1
    assert jobs_of(harness)[0]["id"] == jobs[0]["id"]
    assert "cron edit" in harness["log"].read_text()


def test_dry_run_through_the_shell_wrapper_writes_nothing(tmp_path):
    """AC-URC-201b: the recipe's install.sh is the same installer, and a dry run is inert."""
    harness = build(tmp_path)
    before = sorted(str(p.relative_to(harness["root"])) for p in harness["root"].rglob("*"))
    done = run(install_argv(harness, "--dry-run", via_wrapper=True), harness["env"])
    assert done.returncode == 0, done.stderr
    after = sorted(str(p.relative_to(harness["root"])) for p in harness["root"].rglob("*"))
    assert after == before
    assert "nothing written" in done.stdout
    assert jobs_of(harness) == []


def test_installed_launcher_renders_from_repo_state(tmp_path):
    """AC-URC-202: the installed copy renders the real repo's leg, status and charter."""
    harness = build(tmp_path)
    done = run(install_argv(harness, "--set", f"repo={ROOT}", "--set",
                            f"engine={harness['stub']}", "--set", "target_profile=example"),
               harness["env"])
    assert done.returncode == 0, done.stderr
    script = harness["home"] / "scripts" / "autoresearch-overnight-launch.py"
    rendered = run([sys.executable, str(script), "--dry-run"], harness["env"], cwd=tmp_path)
    assert rendered.returncode == 0, rendered.stderr
    text = rendered.stdout
    assert "template-val-bpb" in text and "leg val_bpb" in text
    assert "round 2 · value 10 -> 10 (held)" in text
    assert "stub-adapter 1.0" in text
    assert "Charter (adopter-supplied)" in text and "Overnight charter" in text
    assert "${" not in text
    assert str(harness["stub"]) in text
    assert not (script.parent / "autoresearch-overnight-state.json").exists()
    assert not (script.parent / "autoresearch-overnight.log").exists()


def test_install_never_resumes_a_paused_job_end_to_end(tmp_path):
    """AC-URC-203: pause, reinstall, pause again by hand — the install moved nothing."""
    harness = build(tmp_path)
    assert run(install_argv(harness), harness["env"]).returncode == 0
    paused = run([sys.executable, str(CONTROL), "pause", str(RECIPE), "--profile", "overnight",
                  "--root", str(harness["root"]), "--bin", str(harness["binary"])],
                 harness["env"])
    assert paused.returncode == 0, paused.stderr
    assert jobs_of(harness)[0]["state"] == "paused"

    assert run(install_argv(harness), harness["env"]).returncode == 0
    assert jobs_of(harness)[0]["state"] == "paused"
    status = run([sys.executable, str(CONTROL), "status", str(RECIPE), "--profile", "overnight",
                  "--root", str(harness["root"]), "--bin", str(harness["binary"])],
                 harness["env"])
    assert status.returncode == 0
    assert "state:     paused" in status.stdout or "state:" in status.stdout
    assert "paused" in status.stdout
