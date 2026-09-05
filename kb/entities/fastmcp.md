---
title: FastMCP
created: 2026-09-04
updated: 2026-09-04
type: entity
tags: [integration, agentic]
sources: [raw/articles/mcp-autoresearch-service-conclusions.md]
confidence: high
---

# FastMCP

The actively-developed Python MCP server framework (PrefectHQ/fastmcp, Apache-2.0,
Python ≥3.10, ~27.4K★, ~1.8M PyPI downloads/day at 2026-09-04). Successor to the
FastMCP 1.0 absorbed into the official `mcp` Python SDK — **distinct project, v4**.

## Why this repo uses it

- `@mcp.tool` decorators; streamable HTTP at `/mcp` (default http transport since
  v2.3); `stateless_http=True` for multi-worker round-robin scaling.
- **Dual exposure without duplicated syntax**: `from_fastapi()` converts one
  FastAPI app into an MCP server; per-operation selection (RouteMap, operation
  allowlists/x-mcp markers) decides which endpoints become tools. One async
  handler = REST endpoint + MCP tool.
- Built-in OAuth 2.1 (OAuthProvider, RemoteAuthProvider, OAuthProxy, JWT
  verifier, MultiAuth), dev server, async client with auto transport negotiation.
- Run: `uv add fastmcp` → `uv run fastmcp run server.py:mcp --transport http --port 8000`.
- Caveat (FastMCP's own docs): auto-converted OpenAPI/FastAPI servers underperform
  curated tool sets — bootstrap with `from_fastapi`, then curate the 4-5 research
  tools by hand.

## Production posture

Mount `mcp.http_app()` inside the FastAPI/Starlette app (explicit lifespan),
`@mcp.custom_route("/health")` for probes, bearer/OAuth in front, rate limiting at
gateway/middleware. Fallback option: official `mcp` SDK 2.x (`MCPServer` +
`mcp.run(transport="streamable-http")`).

Related: [[mcp-streamable-http-transport]] · [[research-job-pattern]] ·
[[rest-vs-mcp-dual-exposure]]

^[raw/articles/mcp-autoresearch-service-conclusions.md]