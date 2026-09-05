"""Per-job workspace provisioning for the concurrent multi-topic service
(PRD-06, SC1/SC2 — see docs/prd/06-multi-topic-concurrent-service.md).

Each research job gets an isolated workspace at
`<workspaces_root>/<job_id>/`: a copy of the canonical autoresearch
contract (`contract/` — the single source of truth; the
`RESEARCH_WORKLOAD_DIR` env override is honored via `resolve_workload_dir`)
plus `topic.txt`, `context.json`, and a `corpus/` tree (inline texts and/or
files copied from the corpus root). The runner executes inside that
directory, so two concurrent jobs never share a working directory and
never race on `data.txt`.

Workspaces are retained runtime artifacts under an ignored dir
(`data/workspaces` by default — `/data/*` is gitignored): observable for
debugging after terminal jobs, never tracked by git.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .runner import resolve_workload_dir

# Repo root/data/workspaces — /data/* is gitignored; env override for compose.
DEFAULT_WORKSPACES_DIR = Path(os.environ.get(
    "RESEARCH_WORKSPACES_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "workspaces"),
))
# Repo root/kb/raw on the host, /kb-raw in the compose container (PRD-06).
DEFAULT_CORPUS_ROOT = Path(os.environ.get(
    "RESEARCH_CORPUS_ROOT",
    str(Path(__file__).resolve().parents[2] / "kb" / "raw"),
))

# Sanitizes a title into a filesystem-safe slug: keep [A-Za-z0-9_-], else '_'.
_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass
class CorpusSpec:
    """Corpus requested for one research job (PRD-06 SC2).

    texts: list of {'title': str, 'content': str} inline documents.
    files: paths relative to the corpus root, copied into the workspace.
    """

    texts: list[dict] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def corpus_spec_from_params(params: dict | None) -> CorpusSpec:
    """Extract the CorpusSpec from a job's params dict (corpus.texts / corpus.files)."""
    corpus = (params or {}).get("corpus") or {}
    return CorpusSpec(
        texts=list(corpus.get("texts") or []),
        files=list(corpus.get("files") or []),
    )


def validate_corpus_files(spec: CorpusSpec, corpus_root: Path | None = None) -> None:
    """Fail fast (PRD-06 SC5): every referenced corpus file must exist."""
    root = Path(corpus_root) if corpus_root else DEFAULT_CORPUS_ROOT
    for path in spec.files:
        if not (root / path).is_file():
            raise ValueError(f"corpus file not found: {path}")


def provision_workspace(
    job_id: str,
    topic: str,
    spec: CorpusSpec,
    workspaces_root: Path | None = None,
    corpus_root: Path | None = None,
) -> Path:
    """Provision the isolated workspace for one job; return its path (PRD-06 SC1).

    Layout:
      <workspaces_root>/<job_id>/
        prepare.py, train.py           <- copied from contract/ (resolve_workload_dir())
        topic.txt                        <- the topic string
        context.json                     <- job_id, topic, corpus_spec summary
        corpus/
          texts/<NN>-<slug>.txt          <- inline texts (1-based, zero-padded)
          files/<relative path>          <- copied from corpus root, parents kept
    """
    root = Path(workspaces_root) if workspaces_root else DEFAULT_WORKSPACES_DIR
    croot = Path(corpus_root) if corpus_root else DEFAULT_CORPUS_ROOT
    ws = root / job_id
    ws.mkdir(parents=True, exist_ok=True)

    # Contract copy (canonical autoresearch contract resolved via the same
    # resolve_workload_dir as the runner): every *.py / *.txt file present.
    workload_dir = resolve_workload_dir()
    for src in workload_dir.glob("*"):
        if src.is_file() and src.suffix in (".py", ".txt"):
            shutil.copy2(src, ws / src.name)

    (ws / "topic.txt").write_text(topic, encoding="utf-8")

    context = {
        "job_id": job_id,
        "topic": topic,
        "corpus_spec": {
            "texts": len(spec.texts),
            "files": list(spec.files),
        },
    }
    (ws / "context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")

    corpus_dir = ws / "corpus"
    # Inline texts -> corpus/texts/<NN>-<slug>.txt
    for i, item in enumerate(spec.texts, start=1):
        doc = item or {}
        title = doc.get("title") or ""
        slug = _SLUG_RE.sub("_", title).strip("_") or "text"
        out = corpus_dir / "texts" / "{:02d}-{}.txt".format(i, slug)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc.get("content") or "", encoding="utf-8")
    # Corpus files -> corpus/files/<relative path>, parents preserved.
    for path in spec.files:
        out = corpus_dir / "files" / path
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(croot / path, out)

    return ws