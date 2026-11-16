"""Per-job run repos for the engine-backed service (PRD-06 SC1/SC2, PRD-24 SC4).

Every job — a ``research_*`` baseline measurement or a full ``run_*`` loop — gets
its own repository at ``<workspaces_root>/<job_id>/repo``: a copy of a *bundled*
workload (``workloads.get_workload``), committed as the baseline, then configured
with the engine's ``config.init_run``. The engine drives that copy, so two
concurrent jobs never share a working tree, and a run's commits, reverts and
``.autoresearch/`` state stay inside one job.

``research_*`` jobs additionally get the PRD-06 inputs — ``topic.txt``,
``context.json`` and a ``corpus/`` tree — written *before* the baseline commit so
the tree the engine validates is clean.

Workspaces are retained runtime artifacts under an ignored dir
(``autoresearch/service/data/workspaces`` by default): observable for debugging
after terminal jobs, never tracked by git.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from autoresearch import config as config_mod
from autoresearch import gitops

from .workloads import Workload, run_timeout

# The service root — the directory holding autoresearch_service/ (and the
# Dockerfile). Runtime paths resolve against it, so a host run from any working
# directory and the container name one runtime-state home.
SERVICE_ROOT = Path(__file__).resolve().parents[1]


def _service_path(value: str | Path) -> Path:
    """A relative path resolves against the service root, never the process cwd."""
    path = Path(value)
    return path if path.is_absolute() else SERVICE_ROOT / path


# service root/data/workspaces — service/data/* is gitignored; env override for
# compose. `or` (not `get(default)`) so an exported-empty value falls back to the
# default: `Path('')` is the cwd, and that scatters `<job_id>/` into the tracked tree.
DEFAULT_WORKSPACES_DIR = _service_path(
    (os.environ.get("RESEARCH_WORKSPACES_DIR") or "").strip()
    or str(SERVICE_ROOT / "data" / "workspaces")
)
# Repo root/kb/raw on the host, /kb-raw in the compose container (PRD-06).
# parents[3]: this file is autoresearch/service/autoresearch_service/workspace.py.
DEFAULT_CORPUS_ROOT = Path(
    os.environ.get(
        "RESEARCH_CORPUS_ROOT",
        str(Path(__file__).resolve().parents[3] / "kb" / "raw"),
    )
)

# Sanitizes a title into a filesystem-safe slug: keep [A-Za-z0-9_-], else '_'.
_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")

#: Commit identity for the baseline commit. The engine supplies its own identity
#: for the commits it makes; a fresh repo needs one for this first commit.
BASELINE_AUTHOR = {
    "GIT_AUTHOR_NAME": "autoresearch",
    "GIT_AUTHOR_EMAIL": "autoresearch@localhost",
    "GIT_COMMITTER_NAME": "autoresearch",
    "GIT_COMMITTER_EMAIL": "autoresearch@localhost",
}


@dataclass
class CorpusSpec:
    """Corpus requested for one research job (PRD-06 SC2).

    texts: list of {'title': str, 'content': str} inline documents.
    files: paths relative to the corpus root, copied into the workspace.
    """

    texts: list[dict] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def workspace_dir(job_id: str, workspaces_root: Path | None = None) -> Path:
    """``<workspaces_root>/<job_id>`` — the job's own directory."""
    root = Path(workspaces_root) if workspaces_root else DEFAULT_WORKSPACES_DIR
    return root / job_id


def repo_dir(job_id: str, workspaces_root: Path | None = None) -> Path:
    """``<workspaces_root>/<job_id>/repo`` — the job's git repository."""
    return workspace_dir(job_id, workspaces_root) / "repo"


def corpus_spec_from_params(params: dict | None) -> CorpusSpec:
    """Extract the CorpusSpec from a job's params dict (corpus.texts / corpus.files)."""
    corpus = (params or {}).get("corpus") or {}
    return CorpusSpec(
        texts=list(corpus.get("texts") or []),
        files=list(corpus.get("files") or []),
    )


def _contained_corpus_path(path: str, root: Path) -> Path:
    """Resolve one corpus-relative path, refusing anything outside ``root``.

    A corpus file is a non-empty, '/'-separated path relative to the corpus
    root that resolves inside it (PRD-06 SC5): absolute paths, ``..`` segments,
    backslash separators and symlink escapes are each refused with one clear
    error naming the path and the rule.
    """
    text = path if isinstance(path, str) else str(path)
    if not text.strip():
        raise ValueError("corpus file path is empty")
    if "\\" in text:
        raise ValueError(f"corpus file path must use '/' separators: {text}")
    candidate = Path(text)
    if candidate.is_absolute():
        raise ValueError(f"corpus file path must be relative to the corpus root: {text}")
    if ".." in candidate.parts:
        raise ValueError(f"corpus file path must not contain '..': {text}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"corpus file path resolves outside the corpus root: {text}")
    return resolved


def validate_corpus_files(spec: CorpusSpec, corpus_root: Path | None = None) -> None:
    """Fail fast (PRD-06 SC5): every referenced corpus file must exist inside the
    corpus root — a path that escapes it is refused before any read."""
    root = Path(corpus_root) if corpus_root else DEFAULT_CORPUS_ROOT
    for path in spec.files:
        if not _contained_corpus_path(path, root).is_file():
            raise ValueError(f"corpus file not found: {path}")


def provision_run_repo(
    job_id: str,
    workload: Workload,
    *,
    topic: str | None = None,
    spec: CorpusSpec | None = None,
    workspaces_root: Path | None = None,
    corpus_root: Path | None = None,
) -> Path:
    """Copy a bundled workload into a committed, engine-configured repo.

    Layout (PRD-24 SC4 — one repo per job, always under the workspaces root)::

        <workspaces_root>/<job_id>/
          repo/                      <- the job's git repo (the engine drives it)
            prepare.py, train.py, program.md   <- copied from the workload source
            topic.txt, context.json            <- research_* only (PRD-06)
            corpus/texts/, corpus/files/       <- research_* only (PRD-06)
            .autoresearch/run.json             <- written by config.init_run
          records.jsonl, events.out            <- run_* artifacts (service-level)

    The copy and the topic/corpus inputs are committed together as the baseline,
    so ``init_run`` (which refuses a dirty tree) and every later iteration start
    from a clean repository.
    """
    repo = repo_dir(job_id, workspaces_root)
    repo.mkdir(parents=True, exist_ok=True)

    for src in sorted(workload.source_dir.iterdir()):
        if src.is_file() and src.suffix in (".py", ".md"):
            shutil.copy2(src, repo / src.name)

    if topic is not None or spec is not None:
        _write_research_inputs(
            repo,
            topic=topic or "",
            spec=spec or CorpusSpec(),
            corpus_root=Path(corpus_root) if corpus_root else DEFAULT_CORPUS_ROOT,
        )

    _commit_baseline(repo)

    # A workload dir may ship no program.md (a custom RESEARCH_WORKLOAD_DIR);
    # init_run treats a named-but-missing program file as an error, so only pass
    # one that was actually copied.
    program = workload.program if workload.program and (repo / workload.program).is_file() else None
    budget = run_timeout()
    config_mod.init_run(
        repo=repo,
        verify=workload.verify,
        metric_name=workload.metric_name,
        direction=workload.direction,
        scope=list(workload.scope),
        guard=workload.guard,
        noise_floor=workload.noise_floor,
        verify_timeout=budget,
        guard_timeout=budget,
        protect=list(workload.protect),
        program=program,
    )
    return repo


def _write_research_inputs(
    repo: Path, *, topic: str, spec: CorpusSpec, corpus_root: Path
) -> None:
    """Write topic.txt, context.json and the corpus tree into ``repo`` (PRD-06)."""
    (repo / "topic.txt").write_text(topic, encoding="utf-8")
    context = {
        "job_id": repo.parent.name,
        "topic": topic,
        "corpus_spec": {"texts": len(spec.texts), "files": list(spec.files)},
    }
    (repo / "context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")

    corpus_dir = repo / "corpus"
    # Inline texts -> corpus/texts/<NN>-<slug>.txt
    for i, item in enumerate(spec.texts, start=1):
        doc = item or {}
        title = doc.get("title") or ""
        slug = _SLUG_RE.sub("_", title).strip("_") or "text"
        out = corpus_dir / "texts" / "{:02d}-{}.txt".format(i, slug)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc.get("content") or "", encoding="utf-8")
    # Corpus files -> corpus/files/<relative path>, parents preserved. The
    # destination boundary is corpus/files/ itself, not the corpus root the
    # source check already guarded (issue #54 — never trust the caller).
    for path in spec.files:
        src = _contained_corpus_path(path, corpus_root)
        files_dir = corpus_dir / "files"
        out = files_dir / path
        if not out.resolve().is_relative_to(files_dir.resolve()):
            raise ValueError(f"corpus file path escapes the workspace: {path}")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)


def _commit_baseline(repo: Path) -> None:
    """``git init`` the job repo and commit what was copied into it."""
    gitops.git(repo, "init", "-b", "main")
    gitops.git(repo, "add", "-A")
    gitops.git(
        repo,
        "commit",
        "--no-verify",
        "-m",
        "autoresearch: baseline",
        env_extra=BASELINE_AUTHOR,
    )


def topic_of(repo: Path) -> str:
    """Topic string from topic.txt (missing/unreadable -> empty string)."""
    try:
        return (Path(repo) / "topic.txt").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def corpus_stats(repo: Path) -> dict:
    """Corpus stats: file count + total chars under repo/corpus (0/0 absent)."""
    files, chars = 0, 0
    corpus_dir = Path(repo) / "corpus"
    if corpus_dir.is_dir():
        for p in corpus_dir.rglob("*"):
            if p.is_file():
                files += 1
                try:
                    chars += len(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    return {"files": files, "chars": chars}
