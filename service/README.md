# service/ — Autoresearch Service Runbook (template)

> **This file is the agent-facing runbook for the autoresearch service.** It is
> a template: downstream projects copy `service/` and keep this file accurate.
> **Convention:** every agent that changes service behaviour (routes, tools,
> job lifecycle, env vars, concurrency, packaging) MUST update this file in the
> same change. It is the single source for *how to run and use the service*;
> `docs/NN-slug.md` records *what was verified* about it.
>
> Funnel home: component README (like the root `README.md`), not a funnel stage
> 1–6 doc — see the "Where does this text go" table in `AGENTS.md`.

## What this is

One ASGI process exposing the **autoresearch loop** (`prepare.py` → `train.py`,
`val_bpb`, time budget — see `../../program.md` and `kb/concepts/autoresearch-contract.md`)
to **two consumers at once**:

| Surface | Path / protocol | Consumers |
|---|---|---|
| REST | `/api/v1/*` (OpenAPI at `/openapi.json`) | programs, operators, curl |
| MCP | `/mcp` streamable-HTTP (FastMCP v4) | agent harnesses, LiteLLM gateways |

Both share the same operation handlers (one handler = REST route + MCP tool,
flagged in `service/src/main.py::TOOL_FLAG`). Long work is a **durable
job-id/poll** pattern: `research_start` returns a `job_id` immediately; poll
`research_status` until terminal.

## Quick start

```bash
# Option A — container (batteries-included, zero external infra)
docker compose up -d --build
curl localhost:8000/health            # {"status":"ok"}

# Option B — uv, from repo root
cd service
uv sync --locked
AUTH_DISABLED=1 uv run uvicorn src.main:app --port 8000
```

Tests (repo root): `bash tests/run.sh` (unit+integration) and
`bash tests/run.sh --with-e2e` (adds the container tier; start compose first).
Local CI before any PR: `act push -j unit && act push -j integration && act
push -j secret-scan && act push -j doctrine` — never `act push` unqualified on
a host serving this compose project (AGENTS.md §6).

## Environment variables

| Var | Default | Meaning |
|---|---|---|
| `AUTH_BEARER_TOKEN` | unset | Bearer token gating REST (except `/health`) and `/mcp`. Fail-closed: no token ⇒ deny. |
| `AUTH_DISABLED` | `0` | `1` = skip auth (local dev only). |
| `RESEARCH_JOBS_DB` | `data/jobs.db` | SQLite file backing the durable job store (WAL). Survives restarts. |
| `RESEARCH_RUN_TIMEOUT` | `30` | Per-job time budget (seconds) for `prepare.py`→`train.py`. |
| `RESEARCH_WORKLOAD_DIR` | unset | Optional override of the workload source (default: canonical `contract/`). |
| `RESEARCH_MAX_CONCURRENT_JOBS` | `4` | How many research jobs run concurrently in one process (scheduler ThreadPoolExecutor cap). |
| `RESEARCH_WORKSPACES_DIR` | `data/workspaces` | Root for **per-job isolated workspaces** (see Workspaces below; `data/` is gitignored). |
| `RESEARCH_CORPUS_ROOT` | `kb/raw` (host) / `/kb-raw` (compose mount) | Root for `params.corpus.files` paths. Compose mounts `./kb/raw:/kb-raw:ro`. |

## REST API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` (no auth) |
| POST | `/api/v1/research` | `{"topic": str, "params": {"corpus": {...}}, "idempotency_key"?: str}` | `202` + job dict (`queued`) |
| GET | `/api/v1/research/{job_id}` | — | job dict (status + `result` when terminal) |
| GET | `/api/v1/research/{job_id}/results` | — | job dict (alias) |
| DELETE | `/api/v1/research/{job_id}` | — | job dict (`cancelled` if queued/running) |

Errors: `401` (auth), `400` (bad body / **missing corpus file** — fail fast),
`404` (unknown job). All non-`/health` routes require
`Authorization: Bearer <AUTH_BEARER_TOKEN>`.

## MCP surface

Tools at `/mcp` (streamable HTTP, stateless): `research_start`,
`research_status`, `research_results`, `research_cancel` — same handlers as the
REST routes. Bearer auth is applied by the ASGI guard in front of `/mcp`.

## Multi-topic concurrent research (PRD-06)

The service is built to serve **multiple research topics concurrently,
out-of-the-box**. Each job:

1. gets its own **isolated workspace** — `data/workspaces/<job_id>/` containing
   a copy of the **canonical autoresearch contract** (`contract/` — the single
   source of truth; `prepare.py`, `train.py`, `data.txt`), `topic.txt`,
   `context.json`, and a `corpus/` directory;
2. runs `prepare.py` → `train.py` **inside that workspace** (subprocess, time
   budget, no shell) — no shared cwd, no races;
3. carries a result with `topic` + corpus stats (`{"files": N, "chars": M}`).

Up to `RESEARCH_MAX_CONCURRENT_JOBS` jobs overlap in one process; each runs in
its own thread + own subprocess pair. Queued jobs beyond the cap wait in the
scheduler queue.

### Corpus sources (per job)

`params.corpus` accepts **both**, and they may be combined:

```jsonc
{
  "topic": "What does Karpathy say about eval legitimacy?",
  "params": {
    "corpus": {
      "texts": [{"title": "my note", "content": "raw text..."}],
      "files": ["transcripts/ZhMGNlCU4qc.txt", "articles/autoresearch-template-research-conclusions.md"]
    }
  }
}
```

- `texts` — inline `{title, content}` pairs; always available, no filesystem
  dependency.
- `files` — paths **relative to `RESEARCH_CORPUS_ROOT`** (compose: the repo's
  `kb/raw/` mounted read-only at `/kb-raw`). Missing files are rejected at
  submit with `400`, never discovered mid-run.

Example — user1 researches topic A from one transcript while user2 researches
topic B from another:

```bash
TOKEN=changeme
curl -s -X POST localhost:8000/api/v1/research -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"topic":"topic A","params":{"corpus":{"files":["transcripts/ZhMGNlCU4qc.txt"]}}}'
curl -s -X POST localhost:8000/api/v1/research -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"topic":"topic B","params":{"corpus":{"files":["transcripts/U4kZ0t7Onhw.txt"]}}}'
# poll GET /api/v1/research/<job_id> — both complete; results carry distinct topic + corpus stats
```

## Job lifecycle

```
queued → running → completed | failed | cancelled | timeout
```

- Durable in SQLite (WAL); jobs survive a service restart.
- `idempotency_key` (optional, ≤200 chars): a repeat submit returns the
  existing job instead of creating a second.
- Cancel on queued/running jobs; a terminal state always wins.
- Workspaces are **retained** after terminal jobs as observable artifacts
  (TTL cleanup is a documented upgrade path).

## Workspace layout

```
data/workspaces/<job_id>/
├── prepare.py          # copy of the canonical autoresearch contract (immutable step)
├── train.py            # copy of the canonical autoresearch contract (agent-edited step)
├── data.txt            # prepare output, per-workspace (no cross-job race)
├── topic.txt           # the job's topic
├── context.json        # {job_id, topic, corpus_spec}
└── corpus/
    ├── texts/          # inline corpus texts (01-<slug>.txt, ...)
    └── files/          # corpus files copied from RESEARCH_CORPUS_ROOT, path preserved
```

## Why the handlers are sync (async decision, PRD-06 SC4)

REST and MCP handlers are **sync `def` by design**, and this will not change:

- FastAPI runs sync handlers on its **threadpool** — a handler doing a fast
  SQLite read/write never blocks the event loop.
- The research loop runs in **APScheduler worker threads as subprocesses** —
  blocking I/O and CPU live outside the event loop entirely.
- Making handlers async would add nothing (no I/O-bound awaits in the handler
  path) and would invite a future regression where `run_loop` gets awaited
  inline and stalls the server. The structural guard lives in
  `tests/unit/test_workspace.py` (AC-MCP-037).

## Security

- Bearer auth everywhere except `/health`; constant-time compares
  (`hmac.compare_digest`); fail-closed when misconfigured.
- Runner sandbox: explicit `subprocess.run([...])` args (no `shell=True`),
  always a timeout, output captured, per-job cwd.
- No secrets in code or docs — everything from env; never log a token.
- Corpus files are read-only input copied into the workspace; both corpus
  (`/kb-raw`) and contract (`/app/contract`) mounts are `:ro`.

## Maintaining this file

- Update it in the same change that alters service behaviour.
- Sections to keep accurate: env table, REST/MCP surfaces, job lifecycle,
  workspace layout, concurrency model, async rationale.
- The three-tier test suite (`tests/unit`, `tests/integration`, `tests/e2e`)
  is the executable check that this README is true.