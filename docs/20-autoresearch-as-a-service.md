# 20 — Autoresearch as a Service

## What

One autoresearch implementation — the engine in `autoresearch/engine/`, the contract in
`autoresearch/contract/` and the REST + MCP service in `autoresearch/service/` — ships from
one `autoresearch/pyproject.toml` and is driven from four surfaces: a slash command, the
engine CLI, REST and MCP.

## Why

- Before PRD-20 the repo carried three loops under one name (gap
  [20](../gaps/_archive/20-three-loops-one-name.md)): `service/` ran the toy `val_bpb`
  contract through its own `runner.py`, the engine was reachable only from a CLI, and the
  vendored skill was a prompt loop with neither.
- A service is only "the same loop" if every surface reaches the engine's keep/discard,
  metric parser and report; two copies of that logic disagree silently.
- A network surface needs a bounded blast radius by default: over REST/MCP the only agent
  allowed without configuration is `replay`, and `command` (arbitrary shell) is refused
  even when listed.

## How

### One package

```text
autoresearch/
├── pyproject.toml        # ONE distribution: autoresearch (engine) + autoresearch_service [service]
├── uv.lock               # one lock for both
├── engine/
│   ├── bin/autoresearch  # wrapper: imports the package, no PYTHONPATH needed
│   └── autoresearch/     # stdlib-only engine: cli, config, loop, measure, ledger, adapters
├── contract/             # program.md / prepare.py / train.py + examples/ (the bundled workload)
└── service/
    ├── Dockerfile        # build context is autoresearch/
    ├── README.md         # the service runbook
    └── autoresearch_service/   # auth, policy, jobs, workloads, workspace, main (ASGI app)
```

`autoresearch==0.1.0` is one distribution with two top-level packages:
`[tool.setuptools.package-dir]` maps `autoresearch` → `engine/autoresearch` and
`autoresearch_service` → `service/autoresearch_service`. The engine's dependencies are
empty; FastAPI, uvicorn, FastMCP, APScheduler and pydantic live behind the `service` extra.
`docker-compose.yml` builds `./autoresearch` with `service/Dockerfile` and mounts
`./autoresearch/contract` read-only at `/app/contract`.

### Four surfaces, one loop

| Surface | Entry point | Transport | Reaches |
|---|---|---|---|
| Agent mode | `.agents/commands/ar-{init,run,status,report}.md`, symlinked from `.claude/commands/` and `.opencode/commands/`; `.agents/skills/autoresearch-engine/SKILL.md` | the harness's prompt → `engine/bin/autoresearch` | engine CLI |
| CLI | `autoresearch/engine/bin/autoresearch`, or `PYTHONPATH=autoresearch/engine python3 -P -m autoresearch` | stdout, exit codes (`0` ok, `2` precondition, `3` invalid ledger) | engine package |
| REST | `autoresearch_service.main:app` (uvicorn, container port 8000) | HTTP under `/api/v1` | `autoresearch.loop` / `autoresearch.measure` |
| MCP | the same ASGI app | streamable HTTP at `/mcp`, 9 tools | the same handlers registered as REST routes |

### Two operation families

| Family | Operations | Execution |
|---|---|---|
| `research_*` (PRD-05/06 contract kept) | `research_start`, `research_status`, `research_results`, `research_cancel` | **one** engine measurement of the bundled `contract` workload |
| `run_*` / `doctor` (PRD-20) | `run_start`, `run_status`, `run_report`, `run_cancel`, `doctor` | a full engine keep/discard loop over a bundled workload |

Each operation is one Python handler, registered both as a REST route and as an MCP tool of
the same name. A job returns an id immediately and is polled to a terminal status; its
`engine` summary is the engine's own ledger view
(`metric_name`, `direction`, `baseline_metric`, `incumbent_metric`, `trials`, `outcomes`,
`stop_reason`).

### Bounds a request cannot cross

| Rule | Where | Failure mode |
|---|---|---|
| `workload` names a **bundled** tree, never a path | `autoresearch_service/workloads.py` registry | unknown name → `400` |
| every run executes in a per-job copy under `RESEARCH_WORKSPACES_DIR` | `workspace.py` | no request field accepts a host directory |
| `replay` is the only agent allowed by default | `RESEARCH_ALLOWED_AGENTS` | unlisted harness → `400` |
| `command` is refused over the API even when listed | `policy.py` | `400`, "use the CLI for it" |
| one verify run and one guard run are bounded by `RESEARCH_RUN_TIMEOUT` (30 s) | `workloads.run_timeout()` | job fails bounded, not hangs |

## Verification

### Run 2026-11-10 — live, this worktree (`feat/autoresearch-as-a-service` @ `33e5171`)

Tiers and clone health:

```console
$ python3 -m pytest tests/unit -q
353 passed, 1 warning in 45.63s

$ python3 -m pytest tests/integration -q
26 passed in 102.02s (0:01:42)

$ bash scripts/verify-clone.sh
PASS  7 harness entry point(s) are resolving symlinks
PASS  doctrine paths tracked and not gitignored (10 paths)
PASS  tracked-root coverage — 11 tracked top-level directory(ies), all declared
PASS  credential homes — .credentials/ example tracked, live files ignored
PASS  graphify artifacts ignored by rule (graphify-out/*)
PASS  python3 and tests/run.sh are present
RESULT: PASSED — 33 check(s) passed

$ docker compose build
Successfully tagged template-autoresearch-ready-repo-service:latest
```

The service was exercised from a temp container (`ar-w4`, host port 18099) that mounts
`kb/raw:/kb-raw:ro` and `autoresearch/contract:/app/contract:ro` — the compose mounts,
without replacing any running stack:

```console
$ docker run -d --name ar-w4 -p 18099:8000 -e AUTH_DISABLED=1 \
    -v "$PWD/kb/raw":/kb-raw:ro -v "$PWD/autoresearch/contract":/app/contract:ro \
    template-autoresearch-ready-repo-service:latest
$ curl -s -o /dev/null -w '%{http_code}\n' localhost:18099/health
200
```

**CLI.** A scratch repo built from the bundled contract (`prepare.py`, `train.py`,
`program.md`, one baseline commit) plus a two-record replay file generated the same way the
integration tier generates one (`git diff` of `STEP_WINDOW = 256` → `64`):

```console
$ PYTHONPATH=autoresearch/engine python3 -P -m autoresearch init --repo "$S" \
    --verify "python3 -m train" --guard "python3 prepare.py" \
    --metric-name val_bpb --direction lower --scope train.py \
    --noise-floor 0.001 --protect prepare.py --program program.md --goal "PRD-20 W4 CLI demo"
initialised run in .../ar-cli-demo
  verify : python3 -m train
  guard  : python3 prepare.py
  metric : val_bpb (lower is better)
  scope  : train.py
  protect: prepare.py

$ PYTHONPATH=autoresearch/engine python3 -P -m autoresearch run --repo "$S" \
    --agent replay --replay "$S/../ar-cli-records.jsonl" --max-iterations 2 --plateau 2
baseline: 3.795531 (commit d0c6686)
iter 1: discard metric=3.79553 commit=195dc46 — window 1
iter 2: discard metric=3.79553 commit=4e4afb8 — window 2
stop: plateau after 2 iteration(s) (incumbent 3.795531 at d0c6686)

$ autoresearch/engine/bin/autoresearch status --repo "$S"
run val_bpb (lower is better): baseline 3.79553 -> best 3.79553 (+0.00%), 2 iteration(s), stop plateau
ledger: valid

$ autoresearch/engine/bin/autoresearch report --repo "$S"
.../ar-cli-demo/.autoresearch/report.md

$ PYTHONPATH=autoresearch/engine python3 -P -m autoresearch doctor
claude    /usr/bin/claude  2.1.319 (Claude Code)
opencode  .../bin/opencode  opencode v2.2.5
hermes    /usr/local/bin/hermes  Hermes Agent vunknown (2026.9.24) · stable
dsh       /usr/bin/dsh  0.2.2-rc.1
dsh       OPENAI_API_KEY is unset
```

`results.tsv` after the run, with the ledger's own commits:

```text
iter	commit	metric	outcome	description
0	d0c66862c193...	3.79553	baseline	baseline
1	195dc467ba12...	3.79553	discard	window 1
2	4e4afb8e6f7a...	3.79553	discard	window 2
```

**REST.** `research_*` still serves its PRD-05/06 contract (job id, poll, numeric
`val_bpb`) — now by one engine baseline measurement of the same contract workload:

```console
$ curl -s -X POST localhost:18099/api/v1/research -H 'Content-Type: application/json' \
    -d '{"topic":"PRD-20 W4 live demo"}'
202 {"id": "5745fb38...", "status": "queued", ...}

$ curl -s localhost:18099/api/v1/research/5745fb38...
200 completed  result.val_bpb = 3.795531
   output: "val_bpb:          3.795531\n... stop_reason: converged  num_steps: 29"
```

`run_*` drives the full loop with the same two records:

```console
$ curl -s -X POST localhost:18099/api/v1/runs -H 'Content-Type: application/json' \
    -d '{"workload":"contract","agent":"replay","max_iterations":2,"records":[...]}'
202 {"id": "08de2bba...", "status": "queued", ...}

$ curl -s localhost:18099/api/v1/runs/08de2bba...
200 completed
engine: {"metric_name":"val_bpb","direction":"lower","baseline_metric":3.795531,
         "incumbent_metric":3.795531,"trials":2,"outcomes":{"discard":2},
         "stop_reason":"max_iterations"}

$ curl -s localhost:18099/api/v1/runs/08de2bba.../report
200 keys=['job_id','report','results','status']  rows=3  (first line "# autoresearch report")

$ curl -s -X POST localhost:18099/api/v1/runs -H 'Content-Type: application/json' \
    -d '{"agent":"command","command":"echo pwned","records":[...]}'
400 {"detail":"agent 'command' is never available over the API — it runs an arbitrary command; use the CLI for it"}
```

**MCP.** `tools/list` over the streamable-HTTP endpoint returns the nine dual-registered
tools, and `doctor` executes through the same handler as the REST route:

```console
$ curl -s -X POST localhost:18099/mcp \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}
# 9 tools: research_start, research_status, research_results, research_cancel,
#          run_start, run_status, run_report, run_cancel, doctor

$ curl -s -X POST localhost:18099/mcp ... \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"doctor","arguments":{}}}'
isError=False
{"allowed_agents":["replay"],"refused_agents":["command"],"harnesses":[...],
 "workloads":["contract"]}
```

**Agent mode.** The four commands live once in `.agents/commands/` and resolve from both
harness dirs:

```console
$ for h in .claude/commands .opencode/commands; do for f in ar-init ar-run ar-status ar-report; do
    printf '%s/%s.md -> %s\n' "$h" "$f" "$(readlink -f "$h/$f.md")"; done; done
.claude/commands/ar-init.md   -> .../.agents/commands/ar-init.md
.claude/commands/ar-run.md    -> .../.agents/commands/ar-run.md
.claude/commands/ar-status.md -> .../.agents/commands/ar-status.md
.claude/commands/ar-report.md -> .../.agents/commands/ar-report.md
.opencode/commands/ar-*.md    -> .../.agents/commands/ar-*.md   (same four)
```

### How to reproduce

```bash
# one-time: image + a scratch repo for the CLI surface
docker compose build
S="$TMPDIR/ar-cli-demo"; rm -rf "$S"; mkdir -p "$S"
cp autoresearch/contract/{prepare.py,train.py,program.md} "$S"/
cd "$S" && git init -q -b main && git add -A \
  && git -c user.name=demo -c user.email=demo@localhost commit -qm baseline
sed -i 's/STEP_WINDOW = 256/STEP_WINDOW = 64/' train.py && git diff > ../ar-cli.patch \
  && git checkout -- train.py
python3 -c 'import json;p=open("../ar-cli.patch").read();[print(json.dumps({"iteration":i,"description":f"window {i}","patch":p})) for i in (1,2)]' \
  > ../ar-cli-records.jsonl    # outside the repo: the engine needs a clean tree
```

```bash
# CLI surface
autoresearch/engine/bin/autoresearch init --repo "$S" --verify "python3 -m train" \
  --guard "python3 prepare.py" --metric-name val_bpb --direction lower \
  --scope train.py --noise-floor 0.001 --protect prepare.py
autoresearch/engine/bin/autoresearch run --repo "$S" --agent replay \
  --replay "$S/../ar-cli-records.jsonl" --max-iterations 2 --plateau 2
autoresearch/engine/bin/autoresearch status --repo "$S"
autoresearch/engine/bin/autoresearch report --repo "$S"
autoresearch/engine/bin/autoresearch doctor
```

```bash
# REST + MCP surface (temp container; never replaces a running compose stack)
docker run -d --name ar-w4 -p 18099:8000 -e AUTH_DISABLED=1 \
  -v "$PWD/kb/raw":/kb-raw:ro -v "$PWD/autoresearch/contract":/app/contract:ro \
  template-autoresearch-ready-repo-service:latest
curl -s localhost:18099/health
curl -s localhost:18099/api/v1/doctor
curl -s -X POST localhost:18099/api/v1/research -H 'Content-Type: application/json' \
  -d '{"topic":"demo"}'                       # poll /api/v1/research/<id>
curl -s -X POST localhost:18099/api/v1/runs -H 'Content-Type: application/json' \
  -d '{"workload":"contract","agent":"replay","max_iterations":2,"records":[...]}'  # poll /api/v1/runs/<id>
curl -s localhost:18099/api/v1/runs/<id>/report
curl -s -X POST localhost:18099/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
docker rm -f ar-w4
```

```bash
# agent mode: in a harness session, from a repo with a clean tree
/ar-init  --verify "python3 -m train" --guard "python3 prepare.py" \
          --metric-name val_bpb --direction lower --scope train.py
/ar-run   --agent replay --replay ../ar-cli-records.jsonl --max-iterations 2
/ar-status
/ar-report
```

## What Works

- One distribution ships the engine, the contract and the service: `docker compose build`
  succeeds from `./autoresearch`, and the image exposes the loop at `/api/v1` and `/mcp`
  without a second copy of the keep/discard logic.
- All four surfaces reach the same engine: the CLI's replay run, the REST `run_*` job and
  the MCP `doctor` tool report the same ledger numbers (`baseline 3.795531`, 2 discards)
  and the same allowlist (`allowed=[replay]`, `refused=[command]`).
- The `research_*` contract survived the re-founding: `POST /api/v1/research` → `202`,
  poll → `completed`, `result.val_bpb` numeric (`3.795531`).
- Safety is enforced at the edge, not documented hopefully: `agent=command` is a `400` with
  the reason, and `doctor` lists `command` under `refused_agents` even with an empty
  allowlist.
- The slash commands are one canonical set: all four resolve from `.claude/commands/` and
  `.opencode/commands/` to `.agents/commands/`, so no harness carries a divergent copy.
- Clone health holds after the move: `verify-clone.sh` → `33 check(s) passed`, 11 tracked
  roots, all declared.

## What Fails

- **The image carries no harness binary.** `doctor` inside the container reports
  `available: false` for `claude`, `opencode`, `hermes` and `dsh`, so the live API demo can
  only use `replay`; a real-harness API run needs binaries and credentials baked into (or
  mounted into) the image and a matching `RESEARCH_ALLOWED_AGENTS`.
- **The replay demo proves the pipeline, not a win.** Both recorded candidates land inside
  the 0.001 noise floor, so the run stops on `plateau`/`max_iterations` with
  `incumbent == baseline` (`3.795531`); it exercises commit → guard → verify → discard and
  the report, but shows no improvement.
- **`research_*` no longer researches the corpus.** The operation measures the bundled
  contract once and returns `val_bpb` with the topic as a label; `params.corpus` is
  recorded as stats, and corpus content does not move the metric (PRD-20 records this as an
  `[ASSUMPTION]`).
- **A slash-command invocation is not in this record.** Only command *resolution* was
  re-verified (symlinks above); no harness was driven through `/ar-run` in this session, so
  SC6's slash-command leg rests on the files plus the CLI run they call.
- **Timeout semantics are per measurement, not per job.** `RESEARCH_RUN_TIMEOUT` bounds one
  verify and one guard run; a `run_*` job with many iterations can outlive that budget.

## Resolution

- Build a harness into the image (or run the CLI on the host) and set
  `RESEARCH_ALLOWED_AGENTS=claude,opencode`; `GET /api/v1/doctor` is the check that the
  image can actually do it.
- For a win-shaped API demo, record a live `--record` run whose candidate clears the noise
  floor and replay that; PRD-17's ex5 (NLTK, 3.7×) stays the real-improvement evidence, not
  this workload.
- Treat `research_*` as a compatibility surface (job id, poll, numeric metric); corpus-driven
  research is the vendored skill's job, and a corpus-aware metric needs its own PRD.
- Run `/ar-run` once in a harness session on a clean repo and append the transcript to this
  doc's *Verification*; until then, treat that leg as unverified, not as broken.
- Size `max_iterations` against `RESEARCH_RUN_TIMEOUT` (or raise the timeout) rather than
  expecting the job budget to cut a long loop short.

## Verdict

**works** — one package serves the loop from CLI, REST, MCP and agent-mode commands with
the engine's own semantics and a safe-by-default allowlist; the live API demo is
`replay`-only and shows no metric win, and the slash-command leg is verified by resolution
only.
