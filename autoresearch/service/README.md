# autoresearch/service/ — Autoresearch Service Runbook (template)

> **This file is the agent-facing runbook for the autoresearch service.** It is
> a template: downstream projects copy `autoresearch/service/` and keep this file accurate.
> **Convention:** every agent that changes service behaviour (routes, tools,
> job lifecycle, env vars, concurrency, packaging) MUST update this file in the
> same change. It is the single source for *how to run and use the service*;
> `docs/NN-slug.md` records *what was verified* about it.
>
> Funnel home: component README (like the root `README.md`), not a funnel stage
> 1–6 doc — see the "Where does this text go" table in `AGENTS.md`.

## What this is

One ASGI process exposing the **engine's** autoresearch loop
(`autoresearch.loop` / `autoresearch.measure` — see `../engine/README.md` and
`../contract/program.md`) to **two consumers at once**:

| Surface | Path / protocol | Consumers |
|---|---|---|
| REST | `/api/v1/*` (OpenAPI at `/openapi.json`) | programs, operators, curl |
| MCP | `/mcp` streamable-HTTP (FastMCP v4) | agent harnesses, LiteLLM gateways |

Both share the same operation handlers (one handler = REST route + MCP tool,
flagged in `autoresearch_service/main.py::TOOL_FLAG`). Long work is a **durable
job-id/poll** pattern: the start call returns a `job_id` immediately; poll the
status call until terminal.

The service owns **jobs, policy and the HTTP/tool surface** — not the loop. The
keep/discard loop, the metric parser and the report are imported from the engine
package, so the REST/MCP surface cannot drift from the CLI's semantics.

Two operation families:

| Family | Operations | Execution |
|---|---|---|
| `research_*` (PRD-05/06) | `research_start`, `research_status`, `research_results`, `research_cancel` | **one** engine measurement of the bundled `contract` workload |
| `run_*` / `doctor` (PRD-20) | `run_start`, `run_status`, `run_report`, `run_cancel`, `doctor` | a full engine keep/discard loop over a bundled workload |

## Quick start

```bash
# Option A — container (batteries-included, zero external infra)
docker compose up -d --build
curl localhost:8000/health            # {"status":"ok"}

# Option B — uv, from the repo root (one pyproject, `service` extra)
cd autoresearch
uv sync --locked --extra service
AUTH_DISABLED=1 uv run --no-sync uvicorn autoresearch_service.main:app --port 8000
```

The image installs `git`: the engine initialises, commits, resets and applies
patches in every job repo, so git is a runtime dependency, not a build tool.

Tests (repo root): `bash tests/run.sh` (unit+integration) and
`bash tests/run.sh --with-e2e` (adds the container tier; start compose first).
Local CI before any PR: run the pre-PR chain stated in `AGENTS.md` §6 — never
`act push` unqualified on a host serving this compose project.

## Environment variables

| Var | Default | Meaning |
|---|---|---|
| `AUTH_BEARER_TOKEN` | unset | Bearer token gating REST (except `/health`) and `/mcp`. Fail-closed: no token ⇒ deny. |
| `AUTH_DISABLED` | `0` | `1` = skip auth (local dev only). |
| `RESEARCH_JOBS_DB` | `autoresearch/service/data/jobs.db` | SQLite file backing the durable job store (WAL); a relative value resolves from the process cwd (compose sets `data/jobs.db`, i.e. `/app/data` in the container). Survives restarts. |
| `RESEARCH_RUN_TIMEOUT` | `30` | Bound (seconds) on one engine verify run **and** one guard run — the job's whole time budget. |
| `RESEARCH_WORKLOAD_DIR` | unset | Optional override of the bundled workload source (default: canonical `autoresearch/contract/`). A custom dir still runs through the same engine config. |
| `RESEARCH_MAX_CONCURRENT_JOBS` | `4` | How many jobs run concurrently in one process (scheduler ThreadPoolExecutor cap). |
| `RESEARCH_WORKSPACES_DIR` | `autoresearch/service/data/workspaces` | Root for **per-job run repos** (see Workspace layout; that dir is gitignored). |
| `RESEARCH_CORPUS_ROOT` | `kb/raw` (host) / `/kb-raw` (compose mount) | Root for `params.corpus.files` paths. Compose mounts `./kb/raw:/kb-raw:ro`. |
| `RESEARCH_ALLOWED_AGENTS` | empty | Comma list of harness agents the API may drive: `claude`, `opencode`, `hermes`, `dsh`. Empty = only `replay`. `command` is **never** allowed over the API, listed or not. |

## REST API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` (no auth) |
| POST | `/api/v1/research` | `{"topic": str, "params": {"corpus": {...}}, "idempotency_key"?: str}` | `202` + job dict (`queued`) |
| GET | `/api/v1/research/{job_id}` | — | job dict (status + `result` when terminal) |
| GET | `/api/v1/research/{job_id}/results` | — | job dict (alias) |
| DELETE | `/api/v1/research/{job_id}` | — | job dict (`cancelled` if queued/running) |
| POST | `/api/v1/runs` | `{"workload"?, "agent"?, "max_iterations"?, "records"?, "model"?, "idempotency_key"?}` | `202` + job dict (`queued`) |
| GET | `/api/v1/runs/{job_id}` | — | job dict + `engine` summary (below) |
| GET | `/api/v1/runs/{job_id}/report` | — | `{"report": <markdown>, "results": [rows]}` |
| DELETE | `/api/v1/runs/{job_id}` | — | job dict (`cancelled` if queued/running) |
| GET | `/api/v1/doctor` | — | allowed agents, harness binaries, bundled workloads |

Errors: `401` (auth), `400` (bad body, **missing corpus file**, unknown
workload, refused agent, malformed/oversized replay records — all fail fast,
before a job exists), `404` (unknown job). All non-`/health` routes require
the bearer token from `AUTH_BEARER_TOKEN` in an `Authorization` header.

A run's `engine` summary is the engine's own view of the ledger:
`{metric_name, direction, baseline_metric, incumbent_metric, trials, outcomes,
stop_reason}` — `null` until the repo is configured.

## Runs (engine-backed)

```bash
# Replay a recorded patch set (no harness binary, no credentials):
curl -s -X POST localhost:8000/api/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"workload":"contract","agent":"replay","max_iterations":2,
       "records":[{"iteration":1,"description":"window","patch":"--- a/train.py\n+++ b/train.py\n@@ ..."}]}'
# -> 202 {"id": "<32 hex>", "status": "queued", ...}

curl -s localhost:8000/api/v1/runs/<job_id>          # poll: status + engine summary
curl -s localhost:8000/api/v1/runs/<job_id>/report   # report markdown + results rows
curl -s -X DELETE localhost:8000/api/v1/runs/<job_id>

# What can this instance run?
curl -s localhost:8000/api/v1/doctor
```

Request fields and limits (all validated **before** a job is created):

| Field | Default | Rule |
|---|---|---|
| `workload` | `contract` | A name in the bundled registry — never a path. Unknown ⇒ `400`. |
| `agent` | `replay` | `replay` always; the four harnesses only when listed in `RESEARCH_ALLOWED_AGENTS`; `command` never. |
| `max_iterations` | `3` | Integer `1..20`. |
| `records` | — | Required for `replay`: `1..50` objects of `{iteration: int ≥ 1, patch: str, description?: str}`, each patch ≤ 200 KB. Written to `records.jsonl` in the job workspace and loaded by the engine's replay adapter. |
| `model` | — | Optional model flag forwarded to the harness adapter. |

## Bundled workloads

A workload is a **bundled** source tree plus the engine config it implies. The
registry lives in `autoresearch_service/workloads.py`; there is no request field
that accepts a directory, so the API cannot be pointed at host code.

| Name | Source | verify | guard | metric | direction | scope | protected | program |
|---|---|---|---|---|---|---|---|---|
| `contract` | `autoresearch/contract/` (`prepare.py`, `train.py`, `program.md`) | `python3 -m train` | `python3 prepare.py` | `val_bpb` | lower | `train.py` | `prepare.py` | `program.md` |

`verify` names the module (`-m train`), not the path: the engine protects every
file named as a path token in the verify/guard commands, and `train.py` is the
file the agent edits — `python3 train.py` would protect the very artifact under
test and revert every candidate as a protected violation.

## Agent allowlist (safe by default)

Over REST/MCP the only agent allowed without configuration is **`replay`**: it
re-executes a patch the caller already sent, needs no harness binary, no
credentials and no network.

`claude`, `opencode`, `hermes` and `dsh` each run a model with the service
host's credentials, so they must be listed explicitly:

```bash
RESEARCH_ALLOWED_AGENTS=claude,opencode docker compose up -d
```

`command` — an arbitrary shell template — is **refused over the API even when
listed**: its argv comes from the request, so no allowlist can bound it. It
stays available to the CLI, where the operator owns the machine.

`GET /api/v1/doctor` reports what this instance can actually do: the effective
`allowed_agents`, the `refused_agents`, each harness's binary/path/version
(reused from the engine's own doctor probe), and the bundled workloads. It
reports credential state by *name* only — never a value.

## MCP surface

Tools at `/mcp` (streamable HTTP, stateless), same handlers as the REST routes:

- `research_start`, `research_status`, `research_results`, `research_cancel`
- `run_start`, `run_status`, `run_report`, `run_cancel`, `doctor`

Bearer auth is applied by the ASGI guard in front of `/mcp`.

## Multi-topic concurrent research

The service is built to serve **multiple research topics concurrently,
out-of-the-box**. Each job:

1. gets its own **run repo** — `<workspaces>/<job_id>/repo/` containing a copy of
   a bundled workload (`prepare.py`, `train.py`, `program.md`), plus
   `topic.txt`, `context.json` and a `corpus/` tree for `research_*` jobs, all
   committed as the baseline so the engine starts from a clean tree;
2. is configured by the engine (`config.init_run` → `.autoresearch/run.json`) and
   measured/driven **inside that repo** (no shell, bounded timeouts) — no shared
   working tree, no races;
3. carries a result with `topic` + corpus stats (`{"files": N, "chars": M}`).

Up to `RESEARCH_MAX_CONCURRENT_JOBS` jobs overlap in one process; each runs in
its own scheduler thread and its own repo. Queued jobs beyond the cap wait in
the scheduler queue.

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
TOKEN="$AUTH_BEARER_TOKEN"   # the token the service is running with
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
- Both families share the store; a run job's params carry `"kind": "run"`.
- `idempotency_key` (optional, ≤200 chars): a repeat submit returns the
  existing job instead of creating a second.
- Cancel on queued/running jobs; a terminal state always wins — a worker that
  finishes after a cancel cannot overwrite it.
- Workspaces are **retained** after terminal jobs as observable artifacts
  (TTL cleanup is a documented upgrade path).

`research_*` result fields (unchanged from PRD-05/06): `status`, `val_bpb`,
`output`, `duration_s`, `command`, `topic`, `corpus` — `val_bpb` is the engine
measurement's value, `status` is mapped from it (`completed` | `timeout` |
`failed`).

## Workspace layout

```
<RESEARCH_WORKSPACES_DIR>/<job_id>/
├── repo/                       # the job's git repository (the engine drives it)
│   ├── .git/
│   ├── prepare.py             # copy of the bundled workload (immutable evaluator)
│   ├── train.py               # copy of the bundled workload (the agent-edited artifact)
│   ├── program.md             # standing instructions for the agent
│   ├── topic.txt              # research_* only: the job's topic
│   ├── context.json           # research_* only: {job_id, topic, corpus_spec}
│   ├── corpus/                # research_* only
│   │   ├── texts/             # inline corpus texts (01-<slug>.txt, ...)
│   │   └── files/             # corpus files copied from RESEARCH_CORPUS_ROOT
│   └── .autoresearch/         # engine state: run.json, events.jsonl, prompt.txt,
│                              # last_agent.log, report.md, results.tsv (self-ignored)
├── records.jsonl              # run_* only: the replay records, as submitted
└── events.out                 # run_* only: the loop's JSON event stream
```

## Why the handlers are sync (async decision, PRD-06 SC4)

REST and MCP handlers are **sync `def` by design**, and this will not change:

- FastAPI runs sync handlers on its **threadpool** — a handler doing a fast
  SQLite read/write never blocks the event loop.
- The engine work runs in **APScheduler worker threads** (subprocesses, git) —
  blocking I/O and CPU live outside the event loop entirely.
- Making handlers async would add nothing (no I/O-bound awaits in the handler
  path) and would invite a future regression where the loop gets awaited inline
  and stalls the server. The structural guard lives in
  `tests/unit/test_workspace.py` (AC-MCP-037).

## Security

- Bearer auth everywhere except `/health`; constant-time compares
  (`hmac.compare_digest`); fail-closed when misconfigured.
- **No code-execution tool over REST/MCP**: the operations are fixed, the
  workload is a registry name (never a path), and `command` is refused even when
  allowlisted.
- Agent allowlist: `replay` only by default; harnesses opt in through
  `RESEARCH_ALLOWED_AGENTS`.
- No shell anywhere: the engine runs explicit argv (`shlex.split` for its
  configured commands), always with a timeout; the service itself spawns nothing.
- Every job runs on its own copy under the workspaces dir — a request cannot
  name a host path.
- No secrets in code or docs — everything from env; never log a token. `doctor`
  reports credential state by name only.
- Corpus files are read-only input copied into the job repo; both corpus
  (`/kb-raw`) and contract (`/app/contract`) mounts are `:ro`.

## Maintaining this file

- Update it in the same change that alters service behaviour.
- Sections to keep accurate: env table, REST/MCP surfaces, bundled workloads,
  agent allowlist, job lifecycle, workspace layout, concurrency model, async
  rationale.
- The three-tier test suite (`tests/unit`, `tests/integration`, `tests/e2e`)
  is the executable check that this README is true; `tests/unit/test_service_readme.py`
  pins the section list above.
