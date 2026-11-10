# autoresearch/

The template's autoresearch loop, grouped in one root and shipped as **one
distribution**. `engine/` owns the keep/discard loop, `contract/` is the canonical
karpathy-style workload the loop runs, and `service/` exposes the same loop over REST and
MCP. The service carries no loop or metric parser of its own — it imports the engine's.

```text
autoresearch/
├── pyproject.toml        # ONE distribution: `autoresearch` (engine) + `autoresearch_service` [service]
├── uv.lock               # one lock for both packages
├── engine/
│   ├── bin/autoresearch  # CLI wrapper (no PYTHONPATH needed)
│   └── autoresearch/     # stdlib-only loop: cli, config, loop, measure, ledger, adapters, report
├── contract/             # program.md / prepare.py / train.py + examples/ (the bundled workload)
└── service/
    ├── Dockerfile        # build context is this directory
    ├── README.md         # the service runbook (routes, env vars, workspace layout)
    └── autoresearch_service/   # auth, policy, jobs, workloads, workspace, main (ASGI app)
```

`[tool.setuptools.package-dir]` maps `autoresearch` → `engine/autoresearch` and
`autoresearch_service` → `service/autoresearch_service`; the engine's dependencies are
empty, and FastAPI, uvicorn, FastMCP, APScheduler and pydantic sit behind the `service`
extra. `docker-compose.yml` builds from this directory.

## Run it — CLI

```bash
autoresearch/engine/bin/autoresearch doctor
autoresearch/engine/bin/autoresearch init --repo <repo> \
  --verify "python3 -m train" --guard "python3 prepare.py" \
  --metric-name val_bpb --direction lower --scope train.py
autoresearch/engine/bin/autoresearch run --repo <repo> --agent claude --max-iterations 8
autoresearch/engine/bin/autoresearch status --repo <repo>
autoresearch/engine/bin/autoresearch report --repo <repo>
```

## Run it — service

```bash
docker compose up -d --build                    # from the repo root; health on :8000
# or, no container:
cd autoresearch && uv sync --locked --extra service
AUTH_DISABLED=1 uv run --no-sync uvicorn autoresearch_service.main:app --port 8000
```

| Surface | Endpoint | Notes |
|---|---|---|
| REST | `/api/v1/research*`, `/api/v1/runs*`, `/api/v1/doctor` | job id + poll; bearer auth unless `AUTH_DISABLED=1` |
| MCP | `/mcp` (streamable HTTP) | 9 tools: `research_*`, `run_*`, `doctor` |

Over the API only `replay` is allowed without configuration —
`RESEARCH_ALLOWED_AGENTS=claude,opencode` opens more; `command` is never allowed there.
The full runbook is [service/README.md](service/README.md).

## Run it — agent mode

```text
/ar-init    # register the run: verify, guard, metric, scope, protected files
/ar-run     # bounded keep/discard loop (--agent claude|opencode|hermes|dsh|replay)
/ar-status  # replay-validate the ledger
/ar-report  # write .autoresearch/report.md + results.tsv
```

The commands live once in `.agents/commands/` and are symlinked from
`.claude/commands/` and `.opencode/commands/`; any other harness follows
`.agents/skills/autoresearch-engine/SKILL.md`, which documents the same flow.

## Read next

- [engine/README.md](engine/README.md) — the loop, its config and its adapters.
- [contract/examples/README.md](contract/examples/README.md) — five worked examples,
  including the NLTK 3.9.1 ex5 under a four-stage guard.
- [service/README.md](service/README.md) — REST/MCP surface, env vars, per-job workspaces.
- [../docs/20-autoresearch-as-a-service.md](../docs/20-autoresearch-as-a-service.md) —
  the empirical record: what was verified on each surface and what still fails.
