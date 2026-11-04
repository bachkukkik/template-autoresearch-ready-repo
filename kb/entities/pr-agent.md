---
title: PR-Agent
created: 2026-11-04
updated: 2026-11-04
type: entity
tags: [integration]
sources: [raw/articles/2026-11-04-pr-agent-research.md]
confidence: high
---

# PR-Agent

[The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) — the open-source
AI pull-request reviewer this repo adopts (PRD 18) as an **optional, dormant**
feature. Donated by Qodo: `qodo-ai/pr-agent` 301-redirects here; the README calls it
a "community-maintained legacy project of Qodo" (docs: https://docs.pr-agent.ai).

## Key facts (as of 2026-11-04)

- **License:** MIT since v0.40.0 (2026-07-09); path AGPL-3.0 (≤ v0.35.0) →
  Apache-2.0 (v0.36.0–v0.39.0) → MIT. The old free-vs-Pro split no longer gates the
  OSS tree — self-reflection, custom labels, committable suggestions and
  `global_settings_repo` are OSS.
- **Health:** latest release v0.49.0 (2026-10-25), ~1–2-week cadence, daily commits,
  14.5k stars. Not archived; active.
- **Tools (OSS):** `/describe`, `/review`, `/improve`, `/ask`, `/add_docs`,
  `/generate_labels`, `/similar_issue`, `/update_changelog`; self-reflection
  re-scoring (0–10, drops low scorers) is core OSS. `/help_docs` retired (v0.36.1+)
  after a `GITHUB_TOKEN`-exfiltration bug (issue #2445, closed 2026-06-13).
- **Config:** repo-root `.pr_agent.toml`, env vars (`CONFIG__MODEL`,
  `OPENAI_KEY`, `OPENAI_API_BASE`), `extra_instructions`, `custom_labels`.
- **Models:** LiteLLM underneath — any OpenAI-compatible endpoint (cloud, LiteLLM
  gateway, local vLLM/Ollama). Defaults (2026-11-03): `model = "gpt-6.1-sol"`,
  `max_model_tokens = 32000`, fallback `gpt-6-luna`.
- **Self-host:** GitHub Action (`action.yaml`; wrapper pinned by commit SHA, runtime
  image `docker://pragent/pr-agent` digest-pinnable), GitHub App webhook, GitLab,
  Bitbucket, Azure DevOps, Gitea, generic Docker, pip CLI
  (`pip install "pr-agent[github]"`; `--json-output` reports coverage +
  token usage). No official docker-compose.

## In this repo

- `.github/workflows/pr-agent.yml` — dormant until `vars.PR_AGENT_ENABLED == 'true'`
  plus the `OPENAI_API_KEY` secret; conventional names
  `OPENAI_BASE_URL` / `OPENAI_DEFAULT_MODEL` at the surface, mapped to PR-Agent
  internals in the workflow. SHA-pinned to v0.49.0
  (`efdde4afe14aa401a3889012c7f3e9ef3081a430`).
- Tuning: repo-root `.pr_agent.toml`. Intent: `docs/prd/18-pr-agent-adoption.md`
  (`AC-PRA-001..009`). Cross-refs: [[codegraph]] (the other optional-but-recommended
  slot), [[verify-guard-contract]]-style gating philosophy (opt-in = the human owns
  the gate), [[document-funnel-doctrine]] (kb/raw capture first).
- **Evidence caveat:** single-LLM-pass comment precision is ~15% for every model
  (SWR-Bench, arXiv 2509.01494) — gate on score thresholds; multi-pass aggregation
  adds up to +43.67% F1. Field study (arXiv 2508.18771): concise, snippet-bearing,
  manually triggered comments convert best.
