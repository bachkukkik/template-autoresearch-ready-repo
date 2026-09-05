# 06 — Concurrent Multi-Topic Service

## What

A per-job isolation + corpus-delivery layer on the autoresearch service
(`service/`): every research job runs the canonical autoresearch contract
(`contract/`) inside its own workspace, so multiple topics research
concurrently in one process with distinct inputs and no shared state.

## Why

- Two consumers can use the service at the same time on different topics —
  user1 researches topic A from `kb/raw/transcripts/A.txt` while user2
  researches topic B from `B.txt` — without cross-talk.
- The original runner executed the workload in a single shared directory and
  ignored `topic` (gap 06): results were identical regardless of topic and
  concurrent jobs raced on the same `data.txt`.
- The workload source is now the **canonical contract** (`contract/`, single
  source of truth; the old vendored `service/workload/` copy is gone) — the
  service executes, and copies, the real autoresearch loop.

## How

| Component | File | Notes |
|-----------|------|-------|
| Workspace provisioner | `service/src/workspace.py` | `provision_workspace(job_id, topic, spec)` copies the contract (`resolve_workload_dir()`), writes `topic.txt`, `context.json`, `corpus/`; `validate_corpus_files` = fail-fast SC5 |
| Runner | `service/src/runner.py` | `run_loop(work_dir=...)` executes `prepare.py` → `train.py` inside the workspace; report adds `topic` + `corpus {files, chars}`; parses `val_bpb:` (contract) and `RESULT val_bpb=` (legacy) |
| Service wiring | `service/src/main.py` | `research_start` validates corpus files (ValueError → 400); `_run_job` provisions + runs in the workspace; scheduler executor sized from `RESEARCH_MAX_CONCURRENT_JOBS` (default 4) |
| Workload echo | `contract/train.py` | prints `topic=<...>` and `corpus=<N> files, <M> chars` when a workspace context exists; `val_bpb` unchanged (~3.795 bigram baseline) |
| Env | `.env.example`, compose | `RESEARCH_MAX_CONCURRENT_JOBS`, `RESEARCH_WORKSPACES_DIR` (default `data/workspaces`), `RESEARCH_CORPUS_ROOT` (default `kb/raw`, container `/kb-raw` ro mount), `RESEARCH_WORKLOAD_DIR` override; compose mounts `./kb/raw:/kb-raw:ro` and `./contract:/app/contract:ro` |

Corpus per job (`params.corpus`): `texts` (inline `{title, content}` — always
available) and/or `files` (paths relative to `RESEARCH_CORPUS_ROOT`, copied
into the workspace, missing file → 400 at submit).

Workspace layout: `<workspaces_root>/<job_id>/` = `prepare.py`, `train.py`,
`data.txt` (contract copy), `topic.txt`, `context.json`,
`corpus/texts/…`, `corpus/files/…`. Retained after terminal jobs; `data/` is
gitignored.

Async decision (PRD-06 SC4): REST/MCP handlers stay **sync `def`** — FastAPI
threadpool + APScheduler threads/subprocesses own the work; no handler blocks
the event loop. Guarded by AC-MCP-037.

## Verification

```bash
# tiers 1+2 (no container)
PYTHONPATH=service python3 -m pytest tests/unit tests/integration -q   # 82 passed (66 + 16)

# tier 3 (container up — run.sh does NOT start it)
docker compose up -d --build && docker compose ps   # service healthy
bash tests/run.sh --with-e2e                        # RESULT: PASSED (66 unit + 16 integration + 4 e2e)

# local CI (AGENTS.md §6 — never -j e2e on a deployment host)
act push -j unit && act push -j integration && act push -j secret-scan && act push -j doctrine
# -> all four green (2026-09-05)
```

New IDs: AC-MCP-031..037 (unit: workspace isolation, corpus texts/files,
fail-fast, in-workspace run, concurrent overlap, cap honors env, sync-handler
guard), AC-MCP-231..233 (integration: two topics concurrently, corpus file
from `kb/raw/transcripts`, missing file → 400), AC-MCP-104 (e2e: two topics
in the container).

## What Works

- Two topics with distinct inline corpora complete concurrently with distinct
  `result.topic` and `result.corpus` stats (AC-MCP-231, AC-MCP-104)
- Corpus files resolve under `RESEARCH_CORPUS_ROOT` off `kb/raw/transcripts`
  and land in the job workspace (AC-MCP-032/033/232)
- Missing corpus file → HTTP 400 fail-fast, never a mid-run surprise (AC-MCP-233)
- Per-job workspaces are disjoint; the contract runs inside each (AC-MCP-031/034)
- Concurrent execution is real: overlapping runs proven under a bounded budget
  (AC-MCP-035); the scheduler cap honors `RESEARCH_MAX_CONCURRENT_JOBS` (AC-MCP-036)
- Handlers stay sync by design (AC-MCP-037); `service/README.md` is the agent
  runbook (PRD-06 SC6)

## What Fails

- **Triple subprocess per job:** each workspace run costs two `python3`
  subprocesses plus provisioning — fine for the template's millisecond
  contract, expensive for real training workloads (the budget is per-job
  anyway).
- **Workspaces accumulate:** retained after terminal jobs with no TTL/cleanup
  job in v1 (`data/` is gitignored; a cleanup sweeper is the documented
  upgrade).
- **Corpus files are host-filesystem-dependent:** `params.corpus.files` only
  works when `RESEARCH_CORPUS_ROOT` is mounted (compose mounts `kb/raw`);
  inline `texts` are the portable path.
- **Concurrent session during development:** this verification ran while a
  parallel session refactored the same tree (contract/ move) — the merge of
  both change-sets passed the full suite, but concurrent edits on one working
  tree remain a coordination hazard for future sessions.

## Resolution

- **Subprocess cost:** keep the sandbox posture; per-job time budget bounds it.
- **Workspace growth:** TTL sweeper on `data/workspaces` (documented upgrade
  path in PRD-06).
- **Filesystem-dependent corpus:** document `texts` as the portable path;
  `files` requires the corpus root (README + PRD-06).
- **Concurrency hazard:** out of scope; recorded here so the next session
  checks `git status` before editing (this PR's `docs/gaps/06` flipped to
  resolved).

## Verdict

**works** — 82 unit+integration + 4 e2e green, all four local act jobs green
(2026-09-05); the service now serves multiple research topics concurrently,
out of the box, each in an isolated workspace with topic + corpus wiring.