---
source_url: https://modelcontextprotocol.io (spec + SDK docs, registries, FastMCP docs; full source list per item in scratchpads/mcp-autoresearch-mcp/results/*.json)
ingested: 2026-09-04
sha256: 72ca641fccce734cdd1e7227d42af8ac5a9d6b13e7ecce2ceba87a33129bab15
title: MCP streamable-HTTP service for the autoresearch loop — deep research conclusions
---

# MCP Streamable-HTTP Service for the Autoresearch Loop — Deep Research Conclusions

> Synthesis of the 2026-09-04 deep-research run on the user enquiry:
> "I have a RESTful service for auto research so we can use it as APIs; I want
> the SAME service exposed as streamable, http-able MCP tools so agents can use
> it to do auto research too."
> Research artifacts (outline, fields.yaml, 10 validated per-item JSON snapshots,
> report.md) live in `scratchpads/mcp-autoresearch-mcp/` (gitignored).

## 1. Executive summary

**Expose dual, not either/or.** The recommended end-state is one research core
(the karpathy-style autoresearch loop: human-edited `program.md`, agent-edited
`train.py`, immutable `prepare.py` + `val_bpb`, fixed 5-minute budget,
keep/discard) with two thin adapters on the same process: a **REST API** for
deterministic programmatic use (job kickoff, status, results, webhooks,
OpenAPI) and an **MCP server over streamable HTTP** (`/mcp`, JSON-RPC + SSE
progress) as the agent-facing tool surface. MCP is an agent adapter that wraps
the REST/service layer — it does not replace it.

**The protocol has moved to a stateless core.** MCP spec 2026-07-28 (final
2026-07-28; breaking changes) removes the `initialize` handshake (SEP-2575) and
the `Mcp-Session-Id` header (SEP-2567): protocol-version, client info and
capabilities travel in per-request `_meta`, a new optional-but-must-implement
`server/discover` RPC advertises server capabilities, `tools/list` is cacheable
with `ttlMs`/`cacheScope`, and routing/quotas happen at the gateway on
`MCP-Protocol-Version` + `Mcp-Method`/`Mcp-Name`/`Mcp-Param-*` headers. Practical
effect: a remote MCP server can run behind a plain round-robin load balancer —
no sticky sessions, no shared session store. This is the "streamable, http-able"
transport the user asked for; the deprecated HTTP+SSE transport (2024-11-05) is
formally out.

## 2. Verified facts (from 10 validated snapshots, 35/35 fields each)

### Transport (mcp_streamable_http_transport_spec.json)
- Spec versions: 2025-03-26 (introduced streamable HTTP), 2025-11-25
  (session-full), 2026-07-28 (stateless core; RC locked 2026-05-21).
- `POST /mcp` with `Content-Type: application/json`; JSON-RPC 2.0.
  `MCP-Protocol-Version` required on every POST (must match body `_meta`,
  mismatch → 400); `Mcp-Method` required on all requests; `Mcp-Name` required
  for `tools/call`/`resources/read`/`prompts/get`; `Mcp-Param-{Name}` carries
  x-mcp-header-annotated tool args. Header–body disagreement → 400 with
  JSON-RPC `-32020` (HeaderMismatch); unknown method → 404 + `-32601`;
  notifications → 202 Accepted.
- Per-request SSE streams carry progress notifications; closing the stream =
  cancellation; `Last-Event-ID` resumability removed.
- Adoption: MCP passed 400M monthly SDK downloads in 2026.

### Server frameworks
- **FastMCP v4 (PrefectHQ/fastmcp)** — recommended primary. Apache-2.0,
  Python ≥3.10, ~27.4K★, ~1.8M PyPI downloads/day. `@mcp.tool` decorators, dev
  server, streamable HTTP at `/mcp` (default http transport since v2.3),
  `stateless_http=True`, OAuth 2.1 (full OAuthProvider, RemoteAuthProvider,
  OAuthProxy, JWT verifier, MultiAuth), built-in client with auto transport
  negotiation, middleware, Docker/systemd/Prefect Horizon targets.
  `uv add fastmcp` → `uv run fastmcp run server.py:mcp --transport http --port 8000`.
  Distinct from the 1.0-era FastMCP bundled in the official SDK.
- **Official Python SDK (`mcp` package v2.1.1, MIT)** — the SDK renamed FastMCP →
  `MCPServer`; `mcp.run(transport="streamable-http")` (Starlette+uvicorn at
  `:8000/mcp`) or mount `mcp.streamable_http_app()` in FastAPI, `stateless_http=True`,
  OAuth 2.1. Native 2026-07-28 with legacy 2025-11-25/06-18/03-26 serving.
  Good fallback; smaller feature surface than standalone FastMCP.
- **TypeScript SDK (@modelcontextprotocol/server v2)** — alternative: build the
  Python research loop and expose a thin Node `/mcp` gateway, or port tools to
  TS only if the loop itself is Node. v2 is stateless-per-request by design
  (factory per request), `requireBearerAuth` + DNS-rebinding guards built in.
  Chosen when the stack is Node/edge (Cloudflare/Workers).

### Long-running jobs (long_running_job_patterns.json)
- Autoresearch runs are long (multi-hour loops, 5-min experiments). Two
  patterns: **(1) durable job-id/poll pair** — `start_research → job_id`,
  `get_job_status(job_id)` — works with every current client; **(2) MCP Tasks
  extension** (2026-07-28, SEP-2663) — server-directed durable tasks:
  `CreateTaskResult` with `resultType:"task"`, client polls `tasks/get`,
  `tasks/update`, `tasks/cancel`; statuses working → input_required/completed/
  failed/cancelled. Tasks requires client opt-in and support is uneven → ship
  job-id/poll first, augment with Tasks.
- Back the job store with Postgres (pg-boss) or Redis (BullMQ); idempotency
  keys on dispatch; `notifications/progress` + `progressToken` in `_meta` for
  stage progress; bind task IDs to the auth context; cap TTL/concurrency per
  requestor. True partial-result streaming is still draft (SEP-2998).

### Auth (mcp_auth_remote.json)
- Remote MCP servers act as **OAuth 2.1 resource servers**: 401 +
  `WWW-Authenticate: Bearer resource_metadata=` pointing to the RFC 9728
  Protected Resource Metadata doc; clients discover the authorization server,
  register (RFC 7591 DCR fallback), run authorization-code + PKCE. Tokens go in
  the standard `Authorization: Bearer` header. **There is no `Mcp-Authorization`
  header in any current spec.** RFC 8707 resource/audience binding mandatory;
  token passthrough forbidden.
- Pragmatic path for single-agent/team: static bearer API key via FastMCP
  MultiAuth (clearly marked non-spec). Full OAuth delegated to a hosted IdP
  (Keycloak, WorkOS, Cloudflare Access).

### Security (mcp_server_security.json)
- Expose over remote streamable HTTP, **not stdio** (stdio carries the
  command-execution CVE class). Narrow tool allowlist
  (`research_kickoff`/`research_status`/`research_results`/`cancel`) with
  per-tool scopes and a sha256-pinned manifest; treat every tool result and
  tool description as untrusted data (datamark, extract-then-act, classifier).
- Sandbox all code/training runs in Docker (read-only fs, egress allowlist,
  dropped capabilities, seccomp) or WASM/WASI; per-user-per-tool rate limits,
  cost ceilings (429 + Retry-After), vault-hosted secrets, source-side
  redaction, human-approval gate for training-run tools.
- Never expose an omnibus free-form code-exec tool over MCP; keep raw code
  submission on REST.

### Ecosystem & clients (mcp_ecosystem_registries_clients.json)
- Discovery: official MCP Registry (registry.modelcontextprotocol.io, preview,
  metadata-only, `mcp-publisher` CLI, reverse-DNS namespaces) feeding
  aggregators — Glama (superset, 38K–82K servers), Smithery (~6K, one-click
  hosting), PulseMCP (~1.2K curated), mcp.so (~10K unvetted crawl).
- Streamable HTTP is native in: Claude Code (`.mcp.json` type http +
  OAuth), Cursor (`mcp.json` url+headers+static OAuth), OpenAI Codex
  (`config.toml` `streamable_http` + `bearer_token_env_var`), opencode
  (`opencode.json` mcp type remote, PKCE+DCR), Hermes (`config.yaml`
  `mcp_servers` url+headers, 2026-07-28 negotiation), LiteLLM gateway.

### REST ↔ MCP (rest_vs_mcp_dual_exposure.json)
- Complementary, not replacement: REST = deterministic service layer; MCP =
  agent adapter wrapping it ("MCP servers wrap REST APIs"). 2026-07-28 makes the
  wire models converge (stateless, cacheable, header-routable).
- Prior art validates both halves: karpathy/autoresearch (the loop),
  Perplexity (hosted remote MCP + Agent API REST — canonical dual exposure),
  Tavily, Exa (~4.9K★), plus 4+ independent deep-research MCP servers
  (pminervini, menesekinci async-jobs+SQLite, Hajime-Y, achuthprince004).
- Conversion tooling: openapi-to-mcp (PyPI, uvx, FastAPI+SSRF whitelist),
  liteLLM MCP-from-OpenAPI, 0mcp hosted. Recommended: OpenAPI spec as single
  source of truth, MCP as a curated projection via `x-mcp` markers/allowlists.

### Deployment (uv_deployment_streamable_http.json)
- Canonical uv container pattern: copy `uv` from pinned
  `ghcr.io/astral-sh/uv` into `python:3.12-slim-trixie`, `ENV UV_NO_DEV=1`,
  layered `uv sync --locked --no-install-project --no-editable` with
  cache/bind mounts, `CMD uv run --no-dev --locked uvicorn ...` on port 8000,
  endpoint `/mcp`. Context = `service/` so uv.lock, pyproject.toml, Dockerfile
  and code all live in one directory (the "no spill outside service/" rule).
- Reverse-proxy pitfalls: SSE requires `proxy_buffering off`,
  `proxy_http_version 1.1`, `Connection ''`, `proxy_read_timeout 300s+`
  (defaults at nginx/Cloudflare silently hang streams).
- Health: FastMCP `@mcp.custom_route("/health")` (custom routes bypass auth).
- Stateless scaling: FastMCP `stateless_http=True` → `--workers 4` and
  round-robin LB replicas; stateful sessions break multi-instance.

## 3. Decisions this research locks for the build

1. **Dual exposure on one process**: REST core (`/api/...`) + MCP at `/mcp`,
   both mounted in one ASGI app (uvicorn), one auth layer, one rate limiter.
2. **FastMCP v4 as the MCP layer** (Python, uv-managed, stateless_http=True,
   2026-07-28 protocol), falling back to official `mcp` SDK 2.x if OAuth/Tasks
   needs shift. Protocol: 2026-07-28 primary, 2025-11-25 compatibility fallback.
3. **Job-id/poll tool pair first** (`research_start`, `research_status`,
   `research_results`, `research_cancel`) over a durable job store
   (Postgres/Redis), with Tasks-extension augmentation as opt-in.
4. **Auth**: static bearer (MultiAuth) for launch; OAuth 2.1 + PKCE via hosted
   IdP when multi-tenant — standard `Authorization: Bearer`, RFC 8707 audience
   binding, no token passthrough.
5. **Security posture**: remote streamable HTTP (not stdio), Docker/WASM
   sandbox for loop execution, per-tool scopes, rate limits, injection
   containment, human-approval gate for runs.
6. **Deployment**: uv container under `service/`, nginx/Traefik/Caddy with SSE
   buffering off, `/health` custom route, round-robin LB replicas.

## 4. Open items / uncertainties

- Per-client Tasks-extension support matrix (Claude Code/Cursor/Codex/opencode/
  Hermes) not officially published as of 2026-09-04 → ship job-id/poll first.
- Exact FastMCP built-in rate limiting unconfirmed → implement at gateway/middleware.
- `uv run --no-dev` flag spelling varies by uv version (UV_NO_DEV env documented).
- Official MCP Registry GA date unknown (preview) → list also on Glama/PulseMCP/Smithery.
