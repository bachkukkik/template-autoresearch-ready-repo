"""Unit tier — one package, one lock, one loop (PRD-20 SC1/SC2).

IDs: AC-SVC-001..005.

- AC-SVC-001 (SC1) — there is no `service/` at the repo root, and
  `autoresearch/pyproject.toml` ships BOTH top-level packages from one
  distribution, with the service behind the `service` extra.
- AC-SVC-002 (SC1) — exactly one `uv.lock`, under `autoresearch/`.
- AC-SVC-003 (SC1) — `docker compose build` builds from `./autoresearch`.
- AC-SVC-004 (SC2) — the service imports the engine's loop/measure and carries
  no loop or metric parser of its own. A static AST audit, with a synthetic
  negative control so the audit cannot pass by matching nothing.
- AC-SVC-005 (SC1) — the compose service carries `restart: unless-stopped`, so
  it comes back after a Docker daemon restart; `docker compose stop` still keeps
  it down. A synthetic compose text without the key is reported.

Read-only and stdlib-only: the claims are checked, not the prose.
"""

import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTORESEARCH = REPO_ROOT / "autoresearch"
SERVICE_PKG = AUTORESEARCH / "service" / "autoresearch_service"


def test_one_distribution_ships_both_packages():
    """AC-SVC-001: no root `service/`; one pyproject declares the engine, the
    service and the `service` extra."""
    assert not (REPO_ROOT / "service").exists(), (
        "a root service/ directory exists — the service ships from "
        "autoresearch/service/ under autoresearch/pyproject.toml (PRD-20 SC1)"
    )
    pyproject = tomllib.loads((AUTORESEARCH / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "autoresearch"
    packages = pyproject["tool"]["setuptools"]["packages"]
    assert sorted(packages) == ["autoresearch", "autoresearch_service"]
    package_dir = pyproject["tool"]["setuptools"]["package-dir"]
    assert package_dir["autoresearch"] == "engine/autoresearch"
    assert package_dir["autoresearch_service"] == "service/autoresearch_service"

    extra = " ".join(pyproject["project"]["optional-dependencies"]["service"])
    for dependency in ("fastapi", "uvicorn", "fastmcp", "apscheduler", "pydantic"):
        assert dependency in extra, f"the `service` extra omits {dependency}"
    # The engine itself is stdlib-only: no runtime dependencies at all.
    assert pyproject["project"]["dependencies"] == []


def test_exactly_one_lockfile_under_autoresearch():
    """AC-SVC-002: one `uv.lock`, at autoresearch/uv.lock — not at the root and
    not under the service tree."""
    # `scratchpads/` is a gitignored playground (AGENTS.md funnel rule 1) and
    # `.venv/` is build state; neither is part of what this template ships.
    ignored = {".venv", "scratchpads", ".git", "node_modules"}
    locks = sorted(
        path
        for path in REPO_ROOT.rglob("uv.lock")
        if not ignored.intersection(path.parts)
    )
    assert locks == [AUTORESEARCH / "uv.lock"], f"expected one uv.lock under autoresearch/, found {locks}"


def test_compose_builds_from_the_autoresearch_context():
    """AC-SVC-003: the compose build context is ./autoresearch (so ONE pyproject
    and ONE lockfile are in scope for the image build)."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "context: ./autoresearch" in compose
    assert "dockerfile: service/Dockerfile" in compose


# ─── AC-SVC-004: the one-loop audit ─────────────────────────────────────────

#: Workload scripts a service module must never name: they are the *engine's*
#: inputs, resolved from the workload registry, not strings the service spawns.
_WORKLOAD_SCRIPTS = ("train.py", "prepare.py")


def _audit(sources: dict) -> list:
    """Return the one-loop violations in ``sources`` ({filename: source}).

    A module violates the rule when it (a) parses the metric itself — a regex
    containing ``val_bpb`` — or (b) hard-codes a workload script name in a call,
    i.e. spawns the loop the engine owns. The set as a whole violates it when no
    module imports ``autoresearch.measure`` / ``autoresearch.loop``.
    """
    problems = []
    engine_imports = set()
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "autoresearch" or alias.name.startswith("autoresearch."):
                        engine_imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "autoresearch":
                    # `from autoresearch import measure, loop`
                    engine_imports.update(f"autoresearch.{alias.name}" for alias in node.names)
                elif node.module.startswith("autoresearch."):
                    engine_imports.add(node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "compile"
                    and any(
                        isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and "val_bpb" in arg.value
                        for arg in node.args
                    )
                ):
                    problems.append(f"{name}: parses val_bpb with its own regex")
                for arg in node.args:
                    for sub in ast.walk(arg):
                        if (
                            isinstance(sub, ast.Constant)
                            and sub.value in _WORKLOAD_SCRIPTS
                        ):
                            problems.append(
                                f"{name}: names the workload script {sub.value!r} in a call"
                            )
    if not any(
        module in ("autoresearch.measure", "autoresearch.loop")
        or module.startswith(("autoresearch.measure.", "autoresearch.loop."))
        for module in engine_imports
    ):
        problems.append("no module imports autoresearch.measure or autoresearch.loop")
    return problems


def test_service_has_no_loop_or_metric_parser_of_its_own():
    """AC-SVC-004: every service module passes the audit, and the package does
    import the engine's loop/measure."""
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(SERVICE_PKG.glob("*.py"))
    }
    assert sources, "no service modules found — the audit would pass vacuously"
    assert _audit(sources) == []


def test_audit_rejects_a_private_loop_negative_control():
    """AC-SVC-004 (negative control): a synthetic module that parses `val_bpb`
    and spawns `train.py` is rejected — so the clean result above means the
    audit matched, not that it under-matches."""
    private_loop = '''
import re
import subprocess

METRIC_RE = re.compile(r"val_bpb:\\s*([0-9.]+)")


def run(repo):
    return subprocess.run(["python3", "train.py"], cwd=repo, timeout=30)
'''
    problems = _audit({"private_loop.py": private_loop})
    assert any("val_bpb" in problem for problem in problems)
    assert any("train.py" in problem for problem in problems)

    engine_backed = '''
from autoresearch import measure


def run(cfg):
    return measure.measure(cfg)
'''
    assert _audit({"engine_backed.py": engine_backed}) == []


def _compose_service_restart(compose_text: str):
    """Return the `restart:` value set directly under `services.service`.

    Line-based and stdlib-only — this module parses no YAML, so the compose file
    is read as text like AC-SVC-003 does. Keys directly under `service:` sit at
    4-space indent; a commented-out key never counts.
    """
    lines = compose_text.splitlines()
    service_at = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip() == "service:" and len(line) - len(line.lstrip()) == 2
        ),
        None,
    )
    if service_at is None:
        return None
    for line in lines[service_at + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= 2:  # the service block ended
            break
        if indent == 4 and line.strip().startswith("restart:"):
            return line.split(":", 1)[1].split("#", 1)[0].strip()
    return None


def test_compose_service_restarts_unless_stopped():
    """AC-SVC-005: the service comes back after a Docker daemon restart, and is
    still kept down by `docker compose stop`."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert _compose_service_restart(compose) == "unless-stopped"

    # Negative control: a synthetic service block with no `restart:` — not even a
    # commented-out one — is reported as unset, so the assertion above cannot
    # pass by matching a comment.
    without_policy = """services:
  service:
    build:
      context: ./autoresearch
      dockerfile: service/Dockerfile
    environment:
      # restart: always
      AUTH_DISABLED: "1"
    healthcheck:
      interval: 5s
"""
    assert _compose_service_restart(without_policy) is None
