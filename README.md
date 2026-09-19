# template-autoresearch-ready-repo

> Template for **autonomous research** (Karpathy-style autoresearch: one
> human-edited `program.md`, one agent-edited artifact, one immutable evaluator,
> fixed time budget, keep/discard loop) built on the
> [bachkukkik/template-agentic-ready-repo](https://github.com/bachkukkik/template-agentic-ready-repo)
> doctrine — document funnel, harness adapter, PRD→SC→test→CI.

> **Adopting this for your own project?** [`ADOPTING.md`](ADOPTING.md) is the onboarding
> guide — clone → verify → keep/replace/delete → wire your harness. `AGENTS.md` stays the
> canonical rule set it points back at.

## Document Funnel

Every piece of writing in this repo has exactly one home. Writing flows one direction
only — full rules in [AGENTS.md](AGENTS.md#document-funnel-mandatory--every-harness-every-agent).

```
user prompt (any harness)
   ▼
scratchpads/          playground, notes, memos          gitignored, deletable
   ▼
kb/raw/               immutable sources, any format     add-only, never edited
   ▼  llm-wiki ./kb/
kb/                   confirmed knowledge               written ONLY by llm-wiki
   ▼
PRD.md + docs/prd/    intent, grounded in kb/           pm skills
   ▼
docs/gaps/            kb ↔ prd, prd ↔ code divergence   transient, must resolve
   ▼
docs/NN-slug.md       what actually works / fails       coding-agents-docs-guideline ONLY
   ▼
GitHub issues         everything else
```

A new `.md` that fits none of these stages is a defect — file an issue instead.
`kb/` follows the [llm-wiki spec](https://github.com/NousResearch/hermes-agent/blob/main/skills/research/llm-wiki/SKILL.md)
strictly; unused KB material is archived to `kb/_archive/`, never deleted. The add-only
rule for `kb/raw/` is enforced in CI by
[`sources-readonly.yml`](.github/workflows/sources-readonly.yml), not just by instruction.

## Knowledge Base — what is in `kb/` now

Ingested 2026-09-04 from a deep-research run on the autoresearch pattern
(research artifacts snapshot in `scratchpads/autoresearch-research/`, gitignored):

| Layer | Content |
|-------|---------|
| `kb/raw/transcripts/` | 11 YouTube transcripts — tutorial, domain adaptations (music, D&D, code), local-LLM bake-off, Claude Code integration, skill self-improvement, playlist series |
| `kb/raw/articles/` | upstream `program.md` (verbatim) + the research conclusions article |
| `kb/concepts/`, `kb/entities/`, `kb/comparisons/` | synthesized pages — [[autoresearch-contract]], [[val-bpb-metric]], [[fixed-time-budget]], [[evaluator-legitimacy]], [[document-funnel-doctrine]], [[domain-adaptation]], [[problem-selection]], [[skill-self-improvement]], [[karpathy-autoresearch]], [[template-agentic-ready-repo]], plus the ecosystem/platform/agent comparisons |

Query the KB via `kb/index.md`; run `llm-wiki ./kb/` after any `kb/raw/` change.

## Quick Start

```bash
# Clone and set up (the harness entry points are symlinks — see ADOPTING.md step 1)
git clone <repo-url>
cd template-autoresearch-ready-repo
git config core.symlinks true

# Prove the clone is healthy — read-only, one PASS/FAIL line per check
bash scripts/verify-clone.sh

# Start the example service
docker compose up -d

# Run tests (unit + integration; --with-e2e adds the container tier)
bash tests/run.sh
bash tests/run.sh --with-e2e

# Local CI (pre-PR) — the command and its safety rules have ONE home: AGENTS.md §6.
# Never `act push` unqualified on a host running this compose project live.

# Graph search for coding agents (optional but recommended) — see AGENTS.md §codegraph
npm i -g @colbymchenry/codegraph
codegraph install   # wires your agent's MCP config (hermes/opencode/claude/... auto-detected)
codegraph init      # one-time per clone: builds .codegraph/ (gitignored)
```

## Repository Structure

```
.
├── AGENTS.md              # Agent instructions (read first) — CANONICAL
├── ADOPTING.md            # How to adopt this template for a new project
├── CLAUDE.md              # symlink → AGENTS.md
├── .gitattributes         # Merge drivers + line-ending policy (graphify; see AGENTS.md)
├── contract/              # Autoresearch contract — program.md / prepare.py / train.py
├── .agents/               # Repo-scoped agent assets — CANONICAL
│   └── skills/            # Skills pinned to this repo (root-cause ships here)
├── .claude/               # skills, plugins → symlinks into ../.agents/
│   └── agents/            # investigator.md — root-cause gate as a sub-agent
├── PRD.md                 # Master PRD → topic PRDs in docs/prd/
├── README.md              # This file
├── .env.example           # Environment variable template
├── .gitignore             # Standard ignores for agentic repos
├── .credentials/          # Key files the runtime reads from disk — gitignored
│                          #   `.credentials/example.json.example` ships in a fresh clone
├── docker-compose.yml     # Service orchestration
├── service/               # Python microservice (example harness)
├── kb/                    # Knowledge base — llm-wiki layout, populated
│   ├── SCHEMA.md          # KB domain + conventions + tag taxonomy
│   ├── index.md           # Page catalog (llm-wiki-maintained)
│   ├── log.md             # Append-only action record
│   ├── raw/               # Immutable sources: articles/ transcripts/ assets/
│   ├── concepts/          # Autoresearch contract, metrics, budgets, doctrine…
│   ├── entities/          # karpathy-autoresearch, template-agentic-ready-repo
│   ├── comparisons/       # Systems landscape, platform forks, LLM controllers
│   ├── queries/           # Filed query results
│   └── _archive/          # Superseded material (never deleted)
├── docs/                  # Three doc layers — intent, gaps, verified reality
├── ops/                   # Vendored config for a subject operated outside this repo — CANONICAL
├── scripts/               # Repo-level helper scripts (verify-clone.sh)
├── tests/                 # Three-tier test suite — each tier has a runner AND a CI job
├── scratchpads/           # Agent scratch space (gitignored)
└── .github/
    ├── copilot-instructions.md  # symlink → ../AGENTS.md
    └── workflows/         # ci.yml + sources-readonly.yml
```

## Harness Support

`AGENTS.md` is the one instruction file. Harness entry points are symlinks to it, so
adding a harness never forks the content:

| Harness | Entry point | Skills dir |
|---|---|---|
| Hermes | `AGENTS.md` (native) | `~/.hermes/skills/` or `.agents/skills/` |
| Claude Code | `CLAUDE.md` → `AGENTS.md` | `.claude/skills` → `.agents/skills` |
| opencode | `AGENTS.md` (native) | `.agents/skills` honoured natively |
| Copilot | `.github/copilot-instructions.md` → `AGENTS.md` | vendor dir → `.agents/skills` |
| DeepSeek / OpenAI-compatible | read `AGENTS.md` manually | vendor into `.agents/skills/`, or inline `SKILL.md` |
| Anything else | read `AGENTS.md` directly | paste `SKILL.md` into the prompt |

No harness needs a vendor entry file or config of its own — the entry points above are
symlinks that already exist. `AGENTS.md`'s *Harness Adapter*, including its *Per-harness
rows* table, is the authoritative binding; `ADOPTING.md` step 4 is the short version.

## Status

- [x] Skeleton doctrine (funnel, harness adapter, CI gates)
- [x] `kb/` built: raw sources ingested + layer-2 pages synthesized (2026-09-04)
- [x] PRD topics 01–04 (docs/prd/) — scaffold, autoresearch contract, funnel governance, examples corpus
- [x] Autoresearch contract implemented (`program.md` / `prepare.py` / `train.py` + `AC-TPL-*` tests)
- [x] Governance + corpus integrity tests (`AC-FUN-*`, `AC-EXC-*`) — 34/34 unit tests green
- [x] One-command onboarding — `ADOPTING.md` + `scripts/verify-clone.sh` (read-only clone health check). Funnel stage 7 is GitHub issues: there is no examples stage
