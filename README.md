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
`kb/` follows the [`llm-wiki` spec](.agents/skills/llm-wiki/SKILL.md) strictly — the
stage-3 gate travels with the repo, vendored (MIT) from
[`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent/blob/main/skills/research/llm-wiki/SKILL.md);
unused KB material is archived to `kb/_archive/`, never deleted. The add-only
rule for `kb/raw/` is enforced in CI by
[`sources-readonly.yml`](.github/workflows/sources-readonly.yml), not just by instruction.

## Knowledge Base — what is in `kb/` now

Ingested 2026-09-04 from a deep-research run on the autoresearch pattern
(each `kb/raw/` file names its sources in its frontmatter):

| Layer | Content |
|-------|---------|
| `kb/raw/transcripts/` | 11 YouTube transcripts — tutorial, domain adaptations (music, D&D, code), local-LLM bake-off, Claude Code integration, skill self-improvement, playlist series |
| `kb/raw/articles/` | upstream `program.md` (verbatim), the research conclusions, and the output-medium / Karpathy-guidelines sources |
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
bash scripts/local-ci.sh                 # the five pre-PR jobs, one act run per job
bash scripts/local-ci.sh unit doctrine   # a named subset; `e2e` is refused on purpose

# Graph search for coding agents (optional but recommended) — see AGENTS.md §codegraph
npm i -g @colbymchenry/codegraph
codegraph install   # wires your agent's MCP config (hermes/opencode/claude/... auto-detected)
codegraph init      # one-time per clone: builds .codegraph/ (gitignored)

# Regenerate .env from .env.example (comments preserved) — see docs/14-gen-env-script.md
python3 scripts/gen-env.py --fresh      # byte-identical copy for a new deployment
python3 scripts/gen-env.py --update     # .env.new carrying this deployment's values

# STE-style prose audit (the output-medium doctrine's rung-1 gate) — docs/15-ste-audit.md
python3 scripts/audit-ste.py            # default: docs/*.md + README.md, 80% threshold
```

## Repository Structure

```
.
├── AGENTS.md              # Agent instructions (read first) — CANONICAL
├── ADOPTING.md            # How to adopt this template for a new project
├── CLAUDE.md              # symlink → AGENTS.md
├── GEMINI.md              # symlink → AGENTS.md (Gemini CLI's default context file)
├── .gitattributes         # Merge drivers + line-ending policy (graphify; see AGENTS.md)
├── contract/              # Autoresearch contract — program.md / prepare.py / train.py
├── .agents/               # Repo-scoped agent assets — CANONICAL
│   └── skills/            # Skills pinned here: root-cause, llm-wiki, coding-agents-docs-guideline
├── .claude/               # skills, plugins → symlinks into ../.agents/
│   └── agents/            # investigator.md — root-cause gate as a sub-agent
├── PRD.md                 # Master PRD → topic PRDs in docs/prd/
├── README.md              # This file
├── .env.example           # Environment variable template
├── .gitignore             # Standard ignores for agentic repos
├── .credentials/          # Key files the runtime reads from disk — gitignored
│                          #   `.credentials/example.json.example` ships in a fresh clone
├── data/                  # Service runtime state — gitignored except .gitkeep
│                          #   (jobs.db + per-job workspaces/ are created at runtime)
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
├── scripts/               # Repo helpers: verify-clone.sh, gen-env.py, audit-ste.py, local-ci.sh
├── tests/                 # Three-tier test suite — each tier has a runner AND a CI job
├── scratchpads/           # Agent scratch space (gitignored)
└── .github/
    ├── copilot-instructions.md  # symlink → ../AGENTS.md
    └── workflows/         # ci.yml + sources-readonly.yml
```

## Harness Support

`AGENTS.md` is the one instruction file. Every harness reads it — natively, through a
symlinked entry point, or (Aider) through an explicit `--read`; only Gemini CLI insists on
its own filename, which `GEMINI.md` supplies as a symlink. Adding a harness never forks the
content. The pipeline is harness-neutral: every harness runs the `sub1`–`sub4` phase blocks
by prompting them in order (`AGENTS.md` § *The `/goal` Orchestration Workflow*); `/goal` is
a Hermes-only convenience and **"go through sub1-4"** is valid everywhere.

| Harness | Entry point | Skills | Run the `sub1`–`sub4` phases |
|---|---|---|---|
| [Hermes](https://hermes-agent.nousresearch.com/docs) | `AGENTS.md` (native) | `~/.hermes/skills/` or `.agents/skills/` | `/goal <request>`, else prompt the phase blocks |
| Claude Code | `CLAUDE.md` → `AGENTS.md` | `.claude/skills` → `.agents/skills` | prompt the phase blocks in order |
| [opencode](https://opencode.ai/docs/skills/) | `AGENTS.md` (native) | `.agents/skills` honoured natively | prompt the phase blocks in order |
| Copilot | `.github/copilot-instructions.md` → `AGENTS.md` | vendor dir → `.agents/skills` | prompt the phase blocks in order |
| [Codex CLI](https://developers.openai.com/codex/skills) | `AGENTS.md` (native) | `.agents/skills` honoured natively | prompt the phase blocks in order |
| [Cursor](https://cursor.com/docs/skills) | `AGENTS.md` (native); `.cursor/rules` | `.agents/skills` / `.cursor/skills` | prompt the phase blocks in order |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md) | `GEMINI.md` → `AGENTS.md` (its default context file; `contextFileName` configurable) | `.agents/skills` honoured natively; `.gemini/skills` | prompt the phase blocks in order |
| [Aider](https://aider.chat/docs/usage/conventions.html) | `aider --read AGENTS.md` (or `.aider.conf.yml` `read:`) | none — inline the skill's `SKILL.md` | prompt the phase blocks in order |
| DeepSeek / OpenAI-compatible | read `AGENTS.md` manually | vendor into `.agents/skills/`, or inline `SKILL.md` | prompt the phase blocks in order |
| Anything else | read `AGENTS.md` directly | paste `SKILL.md` into the prompt | prompt the phase blocks in order |

No harness needs a vendor entry file or config of its own beyond the entry points above.
`AGENTS.md`'s *Harness Adapter*, including its *Per-harness rows* table, is the
authoritative binding; `ADOPTING.md` step 4 is the short version.

**No-deploy adopters** — a clone that ships no service has no redeploy step, so `sub4` is
*clean `main` + green* `bash tests/run.sh --with-e2e` (never a redeploy cycle).

## Skills

Skills resolve wherever the harness provides them — a host-level skills dir, the
repo-scoped `.agents/skills/`, or, last resort, the skill's `SKILL.md` inlined into the
prompt (a missing tool never waives a gate; `AGENTS.md` §1). Three of the mandated skills
**travel with the repo**; every other one has an install source below. Install from a
neutral cwd (`cd /tmp`), never from inside this repo, so auto-detecting installers do not
pollute the working tree.

| Skill | Source | Install shape |
|-------|--------|---------------|
| `llm-wiki` | **vendored** at [`.agents/skills/llm-wiki/SKILL.md`](.agents/skills/llm-wiki/SKILL.md); upstream [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/blob/main/skills/research/llm-wiki/SKILL.md) (MIT, LICENSE travels with it) | Already present. Funnel stage-3 gate — **the only writer of `kb/` layer-2 pages**; invoke as `llm-wiki ./kb/` so it does not default to `~/wiki` |
| `coding-agents-docs-guideline` | **vendored** at [`.agents/skills/coding-agents-docs-guideline/SKILL.md`](.agents/skills/coding-agents-docs-guideline/SKILL.md); upstream [bachkukkik/coding-agents-docs-guideline](https://github.com/bachkukkik/coding-agents-docs-guideline) | Already present (SKILL.md + `examples/`). Funnel stage-6 gate — required to author or edit any `docs/NN-slug.md` |
| `root-cause` | **vendored** at [`.agents/skills/root-cause/SKILL.md`](.agents/skills/root-cause/SKILL.md) | Already present. Gates every "why does X fail / what does X require" answer; [`.claude/agents/investigator.md`](.claude/agents/investigator.md) is its Claude Code binding (other harnesses run it inline) |
| `opencode-plan-build-orchestrator` | https://github.com/bachkukkik/opencode-plan-build-orchestrator | Plain skill — clone the whole repo (SKILL.md + `agents/` + `references/`) |
| `karpathy-guidelines` | https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md | Plain skill — a single `SKILL.md`. **Not vendored** (the upstream carries no licence file): a copy is captured at [`kb/raw/articles/karpathy-guidelines-skill.md`](kb/raw/articles/karpathy-guidelines-skill.md) |
| `security-best-practices` | https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices | Plain skill — sparse-checkout `skills/.curated/security-best-practices` (SKILL.md + `references/`, `LICENSE.txt`). Python / JS-TS / Go only. Not vendored (large) |
| `webapp-testing` | https://github.com/anthropics/skills/tree/main/skills/webapp-testing | Plain skill — sparse-checkout `skills/webapp-testing` (SKILL.md + `scripts/`, `examples/`, `LICENSE.txt`). Playwright-based. Not vendored |
| `yeet` | https://github.com/openai/skills/tree/main/skills/.curated/yeet | Plain skill — sparse-checkout `skills/.curated/yeet` (SKILL.md + `agents/`, `assets/`, `LICENSE.txt`). Needs `gh` authenticated. Not vendored |
| `simple-english` | https://github.com/AminBlg/SimpleEnglish | §7 rung 1 — STE-style controlled English. Hermes ships it host-level (`creative/simple-english`) |
| `diagrams` | [Karpathy's output-medium post](https://x.com/karpathy/status/2105819303471976479) | §7 rung 2 — DOT/Mermaid → SVG via a deterministic renderer, verified by parsing |
| `render-verify` | [Karpathy's output-medium post](https://x.com/karpathy/status/2105819303471976479) | §7 glue — render → parse verification, never by looking |
| `explainer-video` | [Karpathy's output-medium post](https://x.com/karpathy/status/2105819303471976479) | §7 rung 4 — HTML → MP4 via HyperFrames; needs `/dev/shm` ≥ 256 MB |
| `pm` | https://github.com/phuryn/pm-skills | **Caveat** — a Claude Code plugin bundle (`.claude-plugin/marketplace.json` + `commands/`), not a plain `SKILL.md` skill; install through that mechanism or lift the `commands/*.md` you need (`write-prd`, `test-scenarios`, `triage-requests`, …) by hand |

The `/goal` phase → skill mapping:

| Phase | Skill | Output |
|-------|-------|--------|
| Knowledge synthesis (stage 3) | `llm-wiki` on `./kb/` | `kb/` pages + `index.md` + `log.md` |
| PRD / triage / success criteria / verification policy | `pm` — `create-prd`, `identify-assumptions-*`, `test-scenarios` | `PRD.md` + `docs/prd/NN-*.md` |
| Codebase & resource investigation | `karpathy-guidelines` | Gap report → `docs/gaps/NN-*.md` |
| Root-cause / requirement questions | `root-cause` (Claude Code: `investigator`) | Cited answer, or "not found" |
| Empirical doc authoring (planned vs working) | `coding-agents-docs-guideline` | `docs/NN-slug.md` |
| Task delegation | the harness's delegation mechanism (adapter table) | Scoped sub-agent tasks |
| All coding | `opencode-plan-build-orchestrator` | plan → build → verify |

The output-medium doctrine (`AGENTS.md` §7) adds the consumer-side skills: `simple-english`
(rung 2), `diagrams` (rung 3), `render-verify`, and `explainer-video` (rung 5).

## Status

- [x] Skeleton doctrine (funnel, harness adapter, CI gates)
- [x] `kb/` built: raw sources ingested + layer-2 pages synthesized (2026-09-04)
- [x] PRD topics 01–08, 11, 13–16 (docs/prd/) — scaffold, autoresearch contract, funnel governance, examples corpus, service, codegraph, adoption readiness, worked examples, output medium, gen-env, STE audit, quality controls
- [x] Autoresearch contract implemented (`program.md` / `prepare.py` / `train.py` + `AC-TPL-*` tests)
- [x] Governance + corpus integrity tests (`AC-FUN-*`, `AC-EXC-*`) — unit tier green (count of record: run `bash tests/run.sh`; 187 unit tests at the 2026-10-16 improvement wave)
- [x] One-command onboarding — `ADOPTING.md` + `scripts/verify-clone.sh` (read-only clone health check). Funnel stage 7 is GitHub issues: there is no examples stage
- [x] Output-medium doctrine — `AGENTS.md` §7 (prose → controlled English → diagram → HTML → explainer video) + `kb/` grounding + `AC-OM-*` / `AC-CTX-*` tripwires
- [x] `scripts/gen-env.py` (`--fresh` byte copy / `--update` value-carry, no clobber) + `AC-GEN-001..005`
- [x] `scripts/audit-ste.py` (the "80% to ASD-STE100" prose gate) + `AC-STE-001..003`; repo docs measured at 99.0% within-limit (1544/1559, 2026-10-16)
