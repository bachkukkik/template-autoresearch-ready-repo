---
title: Document Funnel Doctrine
created: 2026-09-04
updated: 2026-10-16
type: concept
tags: [doctrine, agentic]
sources: [raw/articles/autoresearch-template-research-conclusions.md, raw/articles/2026-10-16-autoresearch-oss-landscape.md]
confidence: high
---

# Document Funnel Doctrine

The bachkukkik/template-agentic-ready-repo governance model: every piece of
writing has exactly one home, flows in one direction, and hardens as it moves
downstream.

## Stages

```
0 Prompt → 1 scratchpads/ → 2 kb/raw/ → 3 kb/ (llm-wiki) → 4 PRD.md + docs/prd/
→ 5 docs/gaps/ → 6 docs/NN-slug.md → 7 GitHub issues
```

## Key rules

- No stray documents (stages 1–6 only; everything else is an issue).
- Grounding is downward — a stage may only assert what upstream supports.
- `kb/raw/` is add-only, enforced by CI (`sources-readonly.yml`); secrets never enter it.
- `kb/` layer-2 pages are written only by `llm-wiki`.
- The doctrine itself is tracked: `AGENTS.md`, `PRD.md`, `docs/`, `kb/`,
  `tests/`, `.agents/`, `.github/` — a `.gitignore` hiding any of them empties
  the funnel; the `doctrine` CI job checks harness symlinks and gitignore rules.

## Harness adapter

One canonical `AGENTS.md`; every harness resolves to it — natively, or through a
thin adapter — never a forked copy. The enumerated adapters (each verified
against its vendor's docs, see [[harness-portability]]):

- **AGENTS.md read natively:** opencode, Codex CLI, Cursor, GitHub Copilot
  coding agent (repo-wide `.github/copilot-instructions.md` plus the nearest
  `AGENTS.md`).
- **Claude Code:** `CLAUDE.md` (which also reads a repo's `AGENTS.md` in place).
- **Gemini CLI:** `GEMINI.md`, with a configurable `contextFileName`.
- **Aider:** `CONVENTIONS.md` via `--read CONVENTIONS.md`.
- **generic:** read `AGENTS.md` manually and inline the skill's `SKILL.md`.

Repo-scoped skills live in `.agents/` (canonical), with each harness's directory
**symlinked** into it — a copy drifts. Missing mechanism ≠ waived rule: the
fallback is doing the capability manually, or inlining the skill's `SKILL.md`.

## The pipeline contract (cross-harness)

The canonical cross-harness contract is the **`sub1`–`sub4` phase blocks plus the
phase table** — a harness with no slash commands prompts those phases in order,
and "go through sub1-4" is valid everywhere. **`/goal` is a Hermes-only
convenience**: no harness is required to have a slash command. The phases: sub1
docs/tests gap sync, sub2 local CI via `act`, sub3 PR + CI monitor, sub4 merge +
redeploy, with PM skills for PRD/triage, `karpathy-guidelines` for investigation,
and orchestrator skills for coding.

## Program.md mapping

AGENTS.md ≈ program.md at repo scale; each `.agents/skills/*/SKILL.md` ≈
program.md at task scale; `docs/NN-slug.md` verdicts ≈ `results.tsv` rows.
Autoresearch runs unattended; the doctrine is human-gated at PR/merge — both
modes are explicit in [[autoresearch-contract]]. The funnel is the natural home
for the autoresearch template: see [[template-agentic-ready-repo]].

Related: [[autoresearch-contract]] · [[harness-portability]] · [[skill-self-improvement]] ·
[[template-agentic-ready-repo]]
