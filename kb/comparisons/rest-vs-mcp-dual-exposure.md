---
title: REST vs MCP Dual Exposure
created: 2026-09-04
updated: 2026-09-04
type: comparison
tags: [integration, architecture, decision]
sources: [raw/articles/mcp-autoresearch-service-conclusions.md]
confidence: high
---

# REST vs MCP Dual Exposure

For an autoresearch service used by agents **and** humans, the settled answer is
**dual exposure**: one research core, two adapters. Not replacement; complementary.

## Dimensions

| Dimension | REST | MCP (streamable HTTP) |
|-----------|------|-----------------------|
| Consumer | programs, CI, browsers, any HTTP client | agent harnesses (Hermes, Claude Code, Cursor, Codex, opencode, LiteLLM) |
| Resource model | endpoints + OpenAPI spec | tools/resources/prompts + JSON-RPC |
| Jobs | POST kickoff, GET status/results, webhooks | `research_start` / `research_status`, Tasks extension opt-in |
| Auth | standard (bearer/OAuth) | same — OAuth 2.1 resource server, `Authorization: Bearer` |
| Streaming | SSE/websocket | per-request SSE progress |
| Raw code submission | ✅ safe, strong schema validation | ❌ never expose omnibus code-exec tool (prompt-injection surface) |

## Architecture

- One core (the [[autoresearch-contract]] loop) behind one FastAPI/Starlette app.
- OpenAPI spec = single source of truth; MCP = curated projection (x-mcp markers,
  operation allowlists) — see [[fastmcp]] `from_fastapi` + curation.
- Same process: `/api/...` (REST) + `/mcp` (streamable HTTP), one auth layer, one
  rate limiter, one job store ([[research-job-pattern]]).
- 2026-07-28 stateless MCP makes the wire models converge: header-routable,
  cacheable, round-robin scalable — mirroring REST's operational profile.

## Prior art

Perplexity (hosted remote MCP + Agent API REST — canonical dual exposure), Exa,
Tavily; MLflow official MCP server + AI Gateway (heavier platform for
tracking/runs, cited not adopted). Conversion tooling: openapi-to-mcp (uvx),
liteLLM MCP-from-OpenAPI.

Related: [[mcp-streamable-http-transport]] · [[autoresearch-contract]] ·
[[document-funnel-doctrine]]

^[raw/articles/mcp-autoresearch-service-conclusions.md]