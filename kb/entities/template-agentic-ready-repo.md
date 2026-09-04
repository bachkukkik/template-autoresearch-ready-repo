---
title: Template Agentic Ready Repo
created: 2026-09-04
updated: 2026-09-04
type: entity
tags: [doctrine, agentic]
sources: [raw/articles/autoresearch-template-research-conclusions.md]
confidence: high
---

# Template Agentic Ready Repo

bachkukkik/template-agentic-ready-repo — the starter doctrine this repo clones:
an agent-driven development skeleton with a document funnel, harness adapter,
three-tier tests, and CI enforcement.

## Key facts

- URL: https://github.com/bachkukkik/template-agentic-ready-repo · created 2026-07-28 · Apache-2.0
- Structure: `AGENTS.md` (canonical instruction file + symlinked harness entry points),
  `PRD.md` + `docs/prd/`, `kb/` (llm-wiki layout), `docs/` (gaps + NN status docs),
  `tests/` (unit/e2e/integration), `.agents/` (repo-scoped skills), `.github/` workflows
- CI gates: `ci.yml` (unit → integration → e2e + secret-scan + doctrine), `sources-readonly.yml` (kb/raw add-only)

## Role in this repo

This repository adapts the doctrine to the autoresearch pattern. The funnel
rules and harness adapter apply verbatim (see [[document-funnel-doctrine]]); the
research-loop contract maps onto the same stages — program.md-style skills,
metrics-first evaluation, verdicts that work for both humans and agents. The
KB here captures the synthesis needed to build out those stages.

Related: [[document-funnel-doctrine]] · [[autoresearch-contract]] · [[skill-self-improvement]]