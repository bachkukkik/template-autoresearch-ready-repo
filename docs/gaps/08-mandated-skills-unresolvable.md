# 08 — Seven of eight mandated skills cannot be resolved outside a Hermes host

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-10-16

## Observation

| Side | Source | Claim |
|------|--------|-------|
| A | `AGENTS.md` § Standing Orders 1 | eight skills are mandated; "a missing tool never waives the gate" |
| A | `AGENTS.md` funnel rule 4 + Harness Adapter generic-fallback cell | inline `.agents/skills/llm-wiki/SKILL.md` |
| A | `docs/prd/08-adoption-readiness.md` SC7 | all harnesses are first-class |
| B | `git ls-files .agents/skills` | only `root-cause/` and `autoresearch-methodology/` |
| B | `README.md` + `kb/SCHEMA.md` | stage 3 is defined by an external Hermes-repo URL |
| B | `tests/unit/test_agents_md_budget.py` | the Hermes context-file cap is stated as a rule of every harness |
| B | `tests/unit/test_harness_neutrality.py` | checks string presence for an exact four-harness set; never checks that a mandated skill resolves |

## Evidence

Reproduced 2026-10-16; full record in [`kb/raw/articles/2026-10-16-template-self-audit.md`](../../kb/raw/articles/2026-10-16-template-self-audit.md).

```bash
git ls-files .agents/skills
test -f .agents/skills/llm-wiki/SKILL.md || echo "fallback path missing"
```

## Impact

A Claude Code, opencode, Codex, Cursor, Gemini CLI or Aider adopter without a Hermes skills home cannot satisfy the stage-3 and stage-6 gates, and the documented fallback points at a file that does not exist.

## Resolution

Code change + test — PRD 08 gains SCs for AC-HRN-015..017; skills vendored or given install sources; `GEMINI.md` entry point; repo-budget restatement of AC-CTX.
