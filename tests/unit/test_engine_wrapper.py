"""The wrapper must never import a repo-local ``autoresearch`` module.

IDs: AC-ENG-080. ``python3 -m`` puts the working directory at the front of
``sys.path``, so running the wrapper from a repo that happens to contain
``autoresearch.py`` executed *that* file instead of the engine. ``-P`` removes
the cwd from the path; the caller's ``PYTHONPATH`` still applies.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "engine" / "bin" / "autoresearch"


def test_the_wrapper_ignores_a_repo_local_autoresearch_module(tmp_path):
    """AC-ENG-080: a shadowing module in the cwd is not imported."""
    (tmp_path / "autoresearch.py").write_text(
        "print('PWNED')\nraise SystemExit(9)\n", encoding="utf-8"
    )
    # A package directory would shadow the engine just as well as a module.
    shadow_pkg = tmp_path / "autoresearch"
    shadow_pkg.mkdir()
    (shadow_pkg / "__init__.py").write_text("print('PWNED')\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(WRAPPER), "--version"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0
    assert "PWNED" not in combined
    assert proc.stdout.strip()


def test_the_wrapper_runs_the_engine_from_the_repo_root(tmp_path):
    """AC-ENG-080b: the wrapper works from anywhere, and its exit codes pass
    through (a missing run is a config error, exit 2)."""
    proc = subprocess.run(
        ["bash", str(WRAPPER), "status", "--repo", str(tmp_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "no run configured" in proc.stderr
