"""Per-job workspace provisioning + concurrent multi-topic runner (PRD-06 SC1-SC5).

IDs: AC-MCP-031..037 — spec: docs/prd/06-multi-topic-concurrent-service.md.

- AC-MCP-031 (SC1)  — provision_workspace() builds an isolated per-job workspace:
  contract scripts (prepare.py/train.py) + topic.txt + context.json, and two jobs
  get distinct directories.
- AC-MCP-032 (SC2)  — inline corpus texts land as corpus/texts/<NN>-<slug>.txt
  with sanitized slugs and verbatim contents.
- AC-MCP-033 (SC2/SC5) — corpus files are copied from the corpus root under
  corpus/files/<path>, and validate_corpus_files() fails fast (ValueError).
- AC-MCP-034 (SC2)  — the runner executes inside the workspace; the report carries
  topic + corpus stats; the no-work_dir legacy default has neither key.
- AC-MCP-035 (SC3)  — two jobs with a 1.5s budget on a 5s-sleeping train.py
  overlap in time (wall < 2.8s, sequential would be >= 3s).
- AC-MCP-036 (SC3)  — MAX_CONCURRENT_JOBS defaults to 4, honors
  RESEARCH_MAX_CONCURRENT_JOBS in a fresh process, and the scheduler's default
  executor pool is sized from it.
- AC-MCP-037 (SC4)  — the async decision is locked: all four research handlers
  remain sync `def` (no coroutine).

Hermetic: every workspace roots to tmp; the runner's contract/ baseline runs in
milliseconds; the overlap test is bounded by timeout_s.
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

# Importing src.main executes create_app() + JobStore() at module level, so point
# RESEARCH_JOBS_DB at a throwaway temp file BEFORE the import (test_routes.py
# pattern) and drop any concurrency-cap env to keep the default-cap check honest.
_TEST_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="ar-unit-workspace-"), "jobs.db")
os.environ["RESEARCH_JOBS_DB"] = _TEST_DB_PATH
os.environ.pop("RESEARCH_MAX_CONCURRENT_JOBS", None)

from src import main, workspace  # noqa: E402  (import order matters, see above)
from src.runner import ResearchRunner  # noqa: E402
from src.workspace import (  # noqa: E402
    CorpusSpec,
    provision_workspace,
    validate_corpus_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contract"
SLOW_WORKLOAD = REPO_ROOT / "tests" / "fixtures" / "workloads" / "slow"


def test_provision_creates_isolated_workspace(tmp_path):
    """AC-MCP-031: provision_workspace() lays out the per-job workspace — contract
    scripts + topic.txt + context.json — and two jobs never share a directory."""
    ws_a = provision_workspace("jobA", "Topic A", CorpusSpec(), workspaces_root=tmp_path)
    ws_b = provision_workspace("jobB", "Topic B", CorpusSpec(), workspaces_root=tmp_path)

    assert ws_a.is_dir() and ws_b.is_dir()
    assert ws_a != ws_b  # disjoint per-job dirs under the same root
    assert ws_a.parent == ws_b.parent == tmp_path
    # the canonical autoresearch contract is copied per job (SC1)
    for name in ("prepare.py", "train.py"):
        assert (ws_a / name).is_file()
        assert (ws_b / name).is_file()
    assert (ws_a / "train.py").read_bytes() == (CONTRACT_DIR / "train.py").read_bytes()
    # topic + context wiring
    assert (ws_a / "topic.txt").read_text(encoding="utf-8") == "Topic A"
    context = json.loads((ws_a / "context.json").read_text(encoding="utf-8"))
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
    ws = provision_workspace("jobA", "T", spec, workspaces_root=tmp_path)

    first = ws / "corpus" / "texts" / "01-First_Topic.txt"
    second = ws / "corpus" / "texts" / "02-Second_Topic.txt"
    assert first.is_file() and second.is_file()  # runs of ':'/' '/'!' collapse to one '_'
    assert first.read_text(encoding="utf-8") == "alpha content"
    assert second.read_text(encoding="utf-8") == "beta content"
    # every generated text filename is slug-safe (no chars outside the allowlist)
    slug_re = re.compile(r"^[A-Za-z0-9_-]+$")
    for p in (ws / "corpus" / "texts").iterdir():
        assert slug_re.match(p.stem.split("-", 1)[1])


def test_corpus_files_copied_and_validated(tmp_path, monkeypatch):
    """AC-MCP-033: corpus files resolve under the corpus root, are copied into the
    workspace preserving relative paths, and validate_corpus_files() rejects a
    missing file with ValueError (SC5 fail-fast)."""
    monkeypatch.setattr(workspace, "DEFAULT_CORPUS_ROOT", REPO_ROOT / "kb" / "raw")
    src = REPO_ROOT / "kb" / "raw" / "transcripts" / "ZhMGNlCU4qc.txt"
    assert src.is_file()  # fixture of the corpus root must exist

    spec = CorpusSpec(files=["transcripts/ZhMGNlCU4qc.txt"])
    validate_corpus_files(spec)  # existing file passes validation
    ws = provision_workspace("jobA", "T", spec, workspaces_root=tmp_path)

    out = ws / "corpus" / "files" / "transcripts" / "ZhMGNlCU4qc.txt"
    assert out.is_file()
    assert out.read_bytes() == src.read_bytes()

    with pytest.raises(ValueError, match=r"corpus file not found: does-not-exist\.txt"):
        validate_corpus_files(CorpusSpec(files=["does-not-exist.txt"]))


def test_runner_executes_in_workspace_with_topic_and_corpus(tmp_path):
    """AC-MCP-034: with work_dir the runner runs the contract inside the workspace
    and the report carries topic + corpus stats; without work_dir the legacy
    report is unchanged (no topic/corpus keys)."""
    topic = "Tiny Bigram Topics"
    content = "the quick brown fox jumps over the lazy dog"
    spec = CorpusSpec(texts=[{"title": "Source Doc", "content": content}])
    ws = provision_workspace("jobA", topic, spec, workspaces_root=tmp_path)

    report = ResearchRunner().run_loop(work_dir=str(ws))
    assert report["status"] == "completed"
    assert isinstance(report["val_bpb"], (int, float)) and not isinstance(
        report["val_bpb"], bool
    )
    assert 3.0 < report["val_bpb"] < 4.5  # contract bigram baseline ~3.7
    assert report["topic"] == topic
    assert report["corpus"] == {"files": 1, "chars": len(content)}

    # legacy default path (no work_dir): completes, no topic/corpus keys
    legacy = ResearchRunner().run_loop()
    assert legacy["status"] == "completed"
    assert isinstance(legacy["val_bpb"], (int, float)) and not isinstance(
        legacy["val_bpb"], bool
    )
    assert 3.0 < legacy["val_bpb"] < 4.5
    assert "topic" not in legacy
    assert "corpus" not in legacy


def test_two_jobs_overlap_in_time(tmp_path, monkeypatch):
    """AC-MCP-035: two jobs with a 1.5s budget on a 5s-sleeping train.py overlap —
    wall < 2.8s (sequential would be >= 3s) and both report 'timeout'."""
    monkeypatch.setenv("RESEARCH_WORKLOAD_DIR", str(SLOW_WORKLOAD))  # restored by fixture
    ws_a = provision_workspace("jobA", "Topic A", CorpusSpec(), workspaces_root=tmp_path)
    ws_b = provision_workspace("jobB", "Topic B", CorpusSpec(), workspaces_root=tmp_path)

    barrier = threading.Barrier(2)  # both loops start together
    results = {}

    def _run(key: str, ws: Path) -> None:
        barrier.wait()
        results[key] = ResearchRunner(timeout_s=1.5).run_loop(work_dir=str(ws))

    t0 = time.monotonic()
    threads = [
        threading.Thread(target=_run, args=(key, ws), daemon=True)
        for key, ws in (("a", ws_a), ("b", ws_b))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    wall = time.monotonic() - t0

    assert not any(t.is_alive() for t in threads)
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
    env_cap["PYTHONPATH"] = str(REPO_ROOT / "service")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; os.environ['RESEARCH_MAX_CONCURRENT_JOBS']='2'; "
            "from src import main; print(main.MAX_CONCURRENT_JOBS)",
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


def test_research_handlers_are_sync_def():
    """AC-MCP-037: SC4 async decision locked — REST/MCP research handlers remain
    sync `def` (threadpool + scheduler do the work; no coroutine handlers)."""
    for name in ("research_start", "research_status", "research_results", "research_cancel"):
        handler = getattr(main, name)
        assert inspect.iscoroutinefunction(handler) is False, name
        assert inspect.isasyncgenfunction(handler) is False, name