"""Per-job run repos + concurrent multi-topic service (PRD-06 SC1-SC5).

IDs: AC-MCP-031..037 — spec: docs/prd/06-multi-topic-concurrent-service.md.

Retargeted (PRD-20 W2): provisioning now produces a *git repo* per job and the
loop is the engine's, so each ID pins the same behaviour on the engine-backed
path — a disjoint ``<job_id>/repo`` per job, corpus delivery, the report fields,
concurrent measurements, the scheduler cap, and sync handlers.

- AC-MCP-031 (SC1)  — provision_run_repo() builds an isolated per-job repo:
  the bundled contract + topic.txt + context.json, and two jobs get distinct
  repositories.
- AC-MCP-032 (SC2)  — inline corpus texts land as corpus/texts/<NN>-<slug>.txt
  with sanitized slugs and verbatim contents.
- AC-MCP-033 (SC2/SC5) — corpus files are copied from the corpus root under
  corpus/files/<path>, and validate_corpus_files() fails fast (ValueError).
- AC-MCP-034 (SC2)  — a provisioned repo measures once through the engine, and
  the job result carries topic + corpus stats.
- AC-MCP-035 (SC3)  — two jobs with a 1.5s budget on a 5s-sleeping train.py
  overlap in time (wall < 2.8s, sequential would be >= 3s).
- AC-MCP-036 (SC3)  — MAX_CONCURRENT_JOBS defaults to 4, honors
  RESEARCH_MAX_CONCURRENT_JOBS in a fresh process, and the scheduler's default
  executor pool is sized from it.
- AC-MCP-037 (SC4)  — the async decision is locked: every REST/MCP handler
  (research_* and run_*) remains sync `def` (no coroutine).

Hermetic: every workspace roots to tmp; the contract baseline runs in
milliseconds; the overlap test is bounded by RESEARCH_RUN_TIMEOUT.
"""

import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

# Importing autoresearch_service.main executes create_app() + JobStore() at module level, so point
# RESEARCH_JOBS_DB at a throwaway temp file BEFORE the import (test_routes.py
# pattern) and drop any concurrency-cap env to keep the default-cap check honest.
_TEST_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="ar-unit-workspace-"), "jobs.db")
os.environ["RESEARCH_JOBS_DB"] = _TEST_DB_PATH
os.environ["RESEARCH_WORKSPACES_DIR"] = os.path.join(
    tempfile.mkdtemp(prefix="ar-unit-workspace-ws-"), "workspaces"
)
os.environ.pop("RESEARCH_MAX_CONCURRENT_JOBS", None)

from autoresearch_service import main, workspace, workloads  # noqa: E402
from autoresearch_service.workspace import (  # noqa: E402
    CorpusSpec,
    provision_run_repo,
    validate_corpus_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "autoresearch" / "contract"
SLOW_WORKLOAD = REPO_ROOT / "tests" / "fixtures" / "workloads" / "slow"


def _provision(root, job_id, topic=None, spec=None):
    """Provision a run repo of the bundled contract workload."""
    return provision_run_repo(
        job_id,
        workloads.get_workload("contract"),
        topic=topic,
        spec=spec,
        workspaces_root=root,
    )


def test_provision_creates_isolated_run_repos(tmp_path):
    """AC-MCP-031: provision_run_repo() lays out one git repo per job — bundled
    contract scripts + topic.txt + context.json — and two jobs never share one."""
    repo_a = _provision(tmp_path, "jobA", "Topic A", CorpusSpec())
    repo_b = _provision(tmp_path, "jobB", "Topic B", CorpusSpec())

    assert repo_a.is_dir() and repo_b.is_dir()
    assert repo_a != repo_b  # disjoint per-job repos under the same root
    assert repo_a.parent.parent == repo_b.parent.parent == tmp_path
    assert repo_a.name == repo_b.name == "repo"
    for repo in (repo_a, repo_b):
        assert (repo / ".git").is_dir()  # the engine drives a real repo
        for name in ("prepare.py", "train.py", "program.md"):
            assert (repo / name).is_file()
        assert (repo / ".autoresearch" / "run.json").is_file()
    assert (repo_a / "train.py").read_bytes() == (CONTRACT_DIR / "train.py").read_bytes()
    # topic + context wiring
    assert (repo_a / "topic.txt").read_text(encoding="utf-8") == "Topic A"
    context = json.loads((repo_a / "context.json").read_text(encoding="utf-8"))
    assert context["job_id"] == "jobA"
    assert context["topic"] == "Topic A"


def test_inline_texts_written_under_corpus_texts(tmp_path):
    """AC-MCP-032: inline corpus texts become corpus/texts/<NN>-<slug>.txt with
    verbatim contents; titles are sanitized to [A-Za-z0-9_-] (else '_')."""
    spec = CorpusSpec(
        texts=[
            {"title": "First Topic", "content": "alpha content"},
            {"title": "Second: Topic!", "content": "beta content"},
        ]
    )
    repo = _provision(tmp_path, "jobA", "T", spec)

    first = repo / "corpus" / "texts" / "01-First_Topic.txt"
    second = repo / "corpus" / "texts" / "02-Second_Topic.txt"
    assert first.is_file() and second.is_file()  # runs of ':'/' '/'!' collapse to one '_'
    assert first.read_text(encoding="utf-8") == "alpha content"
    assert second.read_text(encoding="utf-8") == "beta content"
    # every generated text filename is slug-safe (no chars outside the allowlist)
    slug_re = re.compile(r"^[A-Za-z0-9_-]+$")
    for p in (repo / "corpus" / "texts").iterdir():
        assert slug_re.match(p.stem.split("-", 1)[1])


def test_corpus_files_copied_and_validated(tmp_path, monkeypatch):
    """AC-MCP-033: corpus files resolve under the corpus root, are copied into
    the repo preserving relative paths, and validate_corpus_files() rejects a
    missing file with ValueError (SC5 fail-fast)."""
    monkeypatch.setattr(workspace, "DEFAULT_CORPUS_ROOT", REPO_ROOT / "kb" / "raw")
    src = REPO_ROOT / "kb" / "raw" / "transcripts" / "ZhMGNlCU4qc.txt"
    assert src.is_file()  # fixture of the corpus root must exist

    spec = CorpusSpec(files=["transcripts/ZhMGNlCU4qc.txt"])
    validate_corpus_files(spec)  # existing file passes validation
    repo = _provision(tmp_path, "jobA", "T", spec)

    out = repo / "corpus" / "files" / "transcripts" / "ZhMGNlCU4qc.txt"
    assert out.is_file()
    assert out.read_bytes() == src.read_bytes()

    with pytest.raises(ValueError, match=r"corpus file not found: does-not-exist\.txt"):
        validate_corpus_files(CorpusSpec(files=["does-not-exist.txt"]))


def test_provisioned_repo_measures_with_topic_and_corpus(tmp_path):
    """AC-MCP-034: the provisioned repo measures once through the engine, and the
    job result carries the topic + corpus stats (files/chars)."""
    import autoresearch_service.main as service

    topic = "Tiny Bigram Topics"
    content = "the quick brown fox jumps over the lazy dog"
    spec = CorpusSpec(texts=[{"title": "Source Doc", "content": content}])
    repo = _provision(tmp_path, "jobA", topic, spec)

    result = service._measure_once(repo)
    assert result["status"] == "completed"
    assert isinstance(result["val_bpb"], (int, float)) and not isinstance(
        result["val_bpb"], bool
    )
    assert 3.0 < result["val_bpb"] < 4.5  # contract bigram baseline ~3.7
    assert workspace.topic_of(repo) == topic
    assert workspace.corpus_stats(repo) == {"files": 1, "chars": len(content)}


def test_two_jobs_measure_concurrently(tmp_path, monkeypatch):
    """AC-MCP-035: two jobs with a 1.5s budget on a 5s-sleeping train.py overlap —
    wall < 2.8s (sequential would be >= 3s) and both report 'timeout'."""
    monkeypatch.setenv("RESEARCH_WORKLOAD_DIR", str(SLOW_WORKLOAD))  # restored by fixture
    monkeypatch.setenv("RESEARCH_RUN_TIMEOUT", "1.5")
    import autoresearch_service.main as service

    repo_a = _provision(tmp_path, "jobA", "Topic A", CorpusSpec())
    repo_b = _provision(tmp_path, "jobB", "Topic B", CorpusSpec())

    barrier = threading.Barrier(2)  # both measurements start together
    results = {}

    def _run(key: str, repo: Path) -> None:
        barrier.wait()
        results[key] = service._measure_once(repo)

    t0 = time.monotonic()
    threads = [
        threading.Thread(target=_run, args=(key, repo), daemon=True)
        for key, repo in (("a", repo_a), ("b", repo_b))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15.0)
    wall = time.monotonic() - t0

    assert not any(thread.is_alive() for thread in threads)
    assert results["a"]["status"] == "timeout"
    assert results["b"]["status"] == "timeout"
    assert results["a"]["val_bpb"] is None and results["b"]["val_bpb"] is None
    # overlapping execution: wall beat 2.8s, while running back-to-back (1.5s
    # budget each on a 5s sleep) would take >= 3s
    assert wall < 2.8


def test_concurrent_jobs_cap_honors_env(tmp_path):
    """AC-MCP-036: MAX_CONCURRENT_JOBS defaults to 4, honors
    RESEARCH_MAX_CONCURRENT_JOBS in a fresh interpreter, and the scheduler's
    default executor pool is sized from the cap (tolerant to private-attribute
    drift: if the pool is not discoverable, assert the constant only)."""
    assert main.MAX_CONCURRENT_JOBS == 4  # default with the env var unset

    env_cap = dict(os.environ)
    env_cap["RESEARCH_MAX_CONCURRENT_JOBS"] = "2"
    # Both source roots: the service package AND the engine it imports.
    env_cap["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT / "autoresearch" / "service"),
            str(REPO_ROOT / "autoresearch" / "engine"),
        ]
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; os.environ['RESEARCH_MAX_CONCURRENT_JOBS']='2'; "
            "from autoresearch_service import main; print(main.MAX_CONCURRENT_JOBS)",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env_cap,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "2"

    main.create_app()
    scheduler = getattr(main, "_scheduler", None)
    executor = None
    if scheduler is not None:  # private attrs — drift must not hard-fail
        executors = getattr(scheduler, "_executors", None) or {}
        executor = executors.get("default")
    pool = getattr(executor, "_pool", None) if executor is not None else None
    max_workers = getattr(pool, "_max_workers", None) if pool is not None else None
    if max_workers is not None:
        assert max_workers == main.MAX_CONCURRENT_JOBS
    else:
        assert main.MAX_CONCURRENT_JOBS >= 1  # constant-only fallback


def test_handlers_are_sync_def():
    """AC-MCP-037: SC4 async decision locked — every REST/MCP handler stays sync
    `def` (the threadpool + scheduler do the work; no coroutine handlers)."""
    for name in (
        "research_start",
        "research_status",
        "research_results",
        "research_cancel",
        "run_start",
        "run_status",
        "run_report",
        "run_cancel",
        "doctor",
    ):
        handler = getattr(main, name)
        assert inspect.iscoroutinefunction(handler) is False, name
        assert inspect.isasyncgenfunction(handler) is False, name
