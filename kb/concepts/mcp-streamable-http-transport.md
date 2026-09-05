---
title: MCP Streamable HTTP Transport
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [integration, architecture, agentic]
sources: [raw/articles/mcp-autoresearch-service-conclusions.md]
confidence: high
---

# MCP Streamable HTTP Transport

The Model Context Protocol's remote transport. "Streamable, http-able MCP" in this
repo's service plans means **Streamable HTTP**, not the deprecated HTTP+SSE
transport (2024-11-05, formally out as of 2025-03-26).

## Spec versions

| Spec | Session model | What it means |
|------|---------------|---------------|
| 2025-03-26 | session-full | Introduced streamable HTTP; `initialize` handshake, `Mcp-Session-Id` header |
| 2025-11-25 | session-full | Stable sessionful era; Tasks extension experimental |
| 2026-07-28 | **stateless** | RC locked 2026-05-21, final 2026-07-28. Removes handshake (SEP-2575) and session id (SEP-2567) |

## Stateless core (2026-07-28)

- `initialize`/`initialized` gone — protocol version, client info, capabilities
  travel in per-request `_meta`; `server/discover` RPC fetches capabilities up front.
- `Mcp-Session-Id` gone — any instance can serve any request → **round-robin load
  balancing**, no sticky sessions, no shared session store.
- Routing headers: `MCP-Protocol-Version` (every POST; mismatch with body `_meta` → 400),
  `Mcp-Method` (all requests), `Mcp-Name` (`tools/call`, `resources/read`, `prompts/get`),
  `Mcp-Param-{Name}` for header-annotated tool args. Header–body mismatch → 400 +
  JSON-RPC `-32020`; unknown method → 404 + `-32601`; notifications → 202.
- `tools/list` cacheable via `ttlMs`/`cacheScope` (mirrors HTTP cache-control).
- Per-request SSE streams carry progress notifications; closing stream = cancellation;
  `Last-Event-ID` resumability removed.

## Why this repo targets it

The autoresearch loop ([[autoresearch-contract]]) runs long and must scale behind a
gateway; statelessness + header routing is the operational profile REST users expect.
Dual exposure (also serve REST) is the settled architecture — see
[[rest-vs-mcp-dual-exposure]]. Auth is standard OAuth 2.1 resource-server
(`Authorization: Bearer`, RFC 9728 PRM, RFC 8707 audience binding): no
`Mcp-Authorization` header exists in any current spec.

Related: [[fastmcp]] · [[research-job-pattern]] · [[template-agentic-ready-repo]]

^[raw/articles/mcp-autoresearch-service-conclusions.md]