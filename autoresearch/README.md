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
├── target/               # target-profile contract (PRD 22): relativity split + evaluator guard
├── targets/              # declared target profiles, one `<name>.json` each (PRD 22)
├── objective/            # the tracked objective record — what a run optimises (PRD 22)
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
autoresearch/engine/bin/autoresearch objective validate
autoresearch/engine/bin/autoresearch objective resolve
autoresearch/engine/bin/autoresearch report --repo <repo> --record   # close record + readings
autoresearch/engine/bin/autoresearch report --repo <repo> --check    # re-render, exit 0 on identity
```

`init --objective PATH` (plus `--objective-leg NAME` when the active objective prices more
than one leg) derives `--verify`, `--metric-name`, `--direction`, `--repeats`,
`--noise-floor` and `--guard` from the objective's active leg; an explicit flag still wins.
`report --record` writes `record.json` and `record.md` beside the report and refuses a
record that fails its own honest-verdict checks; `report --check` exits 0 only when both
re-render byte for byte.

Every command that reads or writes run state — `init`, `run`, `status`, `report` — takes
`--state-dir PATH`. Without it the engine keeps using `<repo>/.autoresearch` exactly as
before, so an existing run replays unchanged; with it the state (and the `command`
adapter's prompt file) lives somewhere else and the measured tree is never written to.

## Run it — target profile

```bash
autoresearch/engine/bin/autoresearch profile example --repo <checkout>
autoresearch/engine/bin/autoresearch profile example --repo <checkout> --json
```

Validates the declared profile `autoresearch/targets/example.json` and prints the engine
`init` it implies — a plan, never a run. Every path key declares its relativity in the
profile's `$comment`: `engine`/`referee`/`guard_command`/`runs_dir` resolve here, the
rest resolve in the checkout. The plan passes `--state-dir <runs_dir>/state`, so a
round's `run.json`, ledger and report live in the harness and the measured checkout gets
no `.autoresearch` at all; `run`/`status`/`report` take the same `--state-dir` (its
absolute path is recorded in `run.json`). `--json` emits `{name, profile, target, argv}`
instead of one command line. `import_runs.py` copies an external run ledger into the
profile's runs directory (`--dry-run`, clobber refusal); it resolves that directory
through the same validator. The contract and its four lessons are
[PRD 22](../docs/prd/22-target-profile.md); the example profile's `referee` names a path
that must exist at round time, because this repo ships no scoring layer (PRD 20).

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
- [../docs/24-autoresearch-as-a-service.md](../docs/24-autoresearch-as-a-service.md) —
  the empirical record: what was verified on each surface and what still fails.
