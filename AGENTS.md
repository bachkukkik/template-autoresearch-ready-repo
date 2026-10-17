# Agent Instructions — template-autoresearch-ready-repo

> **This file is the single source of agent instructions for every harness.**
> `CLAUDE.md` and `.github/copilot-instructions.md` are **symlinks** to this file —
> edit `AGENTS.md` only. Repo-scoped skills and plugins live in `.agents/`, with each
> harness's own directory symlinked to it. See *Harness Adapter* below.

## What This Is

A template repo for **autonomous research** (karpathy/autoresearch style) built on the
**template-agentic-ready-repo doctrine**: the same document funnel, harness adapter and
PRD→SC→test→CI gates applied to the research loop (`program.md`/`train.py`/`prepare.py`,
fixed-time budget, keep/discard).

## Read First

1. *Document Funnel* below — where any piece of writing may live.
2. `PRD.md` — intent index → `docs/prd/` (wins on intent).
3. `docs/README.md` — reality index → `docs/NN-slug.md` (wins on behaviour).
4. `kb/index.md` — knowledge index. Three indexes, no overlap.
5. `README.md` — quick start, services, commands, structure.

## Document Funnel (MANDATORY — every harness, every agent)

Writing flows **one direction only**: each stage narrows what the stage above
produced. Know your output's stage *before* writing; never skip one.

```
user prompt (desire + imagination, any harness)
   │
   ▼
scratchpads/            playground, quick notes, memos, dumps   [gitignored, deletable]
   │  what survives scrutiny and is a source document
   ▼
kb/raw/                 immutable source material               [add-only, never edit]
   │  /llm-wiki ./kb/   (synthesis step — never hand-write kb/ layer-2 pages)
   ▼
kb/                     confirmed knowledge, fitted to repo purpose
   │  grounds
   ▼
PRD.md + docs/prd/      intent — what we plan to build
   │  compared against kb/ and against the codebase
   ▼
docs/gaps/              gap observations (kb ↔ prd, prd ↔ code)
   │  drives change; change gets verified
   ▼
docs/<NN-topic>.md      empirical observation — what actually works / fails
   │
   ▼
anything else           GitHub issue, or a comment on an existing issue
```


| # | Stage | Path | Contains | Mutability | Written with |
|---|-------|------|----------|------------|--------------|
| 0 | Prompt | — | Desire + imagination, any harness | ephemeral | — |
| 1 | Scratch | `scratchpads/` | Playgrounds, notes | **gitignored, deletable** | any tool |
| 2 | Raw knowledge | `kb/raw/` | Immutable sources, any format | **add or archive; never edit** | capture / ingest |
| 3 | Knowledge | `kb/` (`kb/SCHEMA.md`) | Confirmed knowledge, fitted to purpose | regenerated from `kb/raw/` | **`llm-wiki` on `./kb/` only** |
| 4 | Intent | `PRD.md`, `docs/prd/NN-*.md` | Requirements, SCs, test mapping, CI gate | edit freely; grounded in `kb/` | PRD skills |
| 5 | Gaps | `docs/gaps/NN-*.md` | Divergence: kb ↔ prd, prd ↔ codebase | short-lived; closed when resolved | `karpathy-guidelines` |
| 6 | Reality | `docs/NN-slug.md`, `docs/README.md` | Empirical observation (eight sections) | append per run | **`coding-agents-docs-guideline` only** |
| 7 | Everything else | GitHub issues | Anything fitting no stage above | issue thread | `gh` CLI |
| — | Amendment | a tracked doctrine file | a branch + PR; never `scratchpads/` | tracked edit | any editor + `gh` |
| — | Ops | `ops/` | Vendored config for a subject outside this repo | live = a **deploy target** | the sync tool — § 6 |

### Funnel rules

1. **No stray documents** — a new `.md` outside stages 1–6 is a defect; if it fits no stage, file an **issue**. Root entry docs and component READMEs are exempt; amendments are a branch + PR, never `scratchpads/` (rule 6). → `ADOPTING.md`
2. **Grounding is downward** — a PRD claim with no `kb/` backing is `[ASSUMPTION]`-marked or dropped; a `docs/NN-slug.md` claim with no verification command is not a claim.
3. **`kb/raw/` is append-or-archive** — supersede into `kb/_archive/` preserving the path; CI: `.github/workflows/sources-readonly.yml`. → `kb/SCHEMA.md`
4. **`kb/` layer-2 pages are never hand-written** — update `kb/raw/`, then run `llm-wiki` on `./kb/`; a vendored `.agents/skills/llm-wiki/SKILL.md` is canonical once it travels with the repo.
5. **Unused knowledge is archived, not deleted** — out of `index.md`, wikilinks → plain text + "(archived)", logged in `kb/log.md`. → `kb/SCHEMA.md`
6. **`scratchpads/` is never cited** as evidence by a tracked document.
7. **Gaps are transient** — a `docs/gaps/` file closes with a `kb/raw/` ingest, a PRD edit, a code change with tests, or an issue, then archives; never deleted, its `NN` never reused (a tombstone remains). → `docs/gaps/README.md`
8. **Skill gates are absolute** — stage 3 requires `llm-wiki`, stage 6 requires `coding-agents-docs-guideline`; no harness mechanism = paste the skill's `SKILL.md` into the prompt and follow it manually (a missing tool never waives the gate).
9. **Never write a secret into `kb/` or `docs/`** — both tracked, `kb/raw/` add-only, so a leak costs a rotation. Record *that* a secret exists, *which* home, and the variable/file NAME (`.env` = injected at deploy time; `.credentials/` = an operator-placed key file), never the value; CI: `secret-scan`. → *Security*
10. **The doctrine itself is tracked** (`AGENTS.md`, `PRD.md`, `docs/`, `kb/`, `tests/`, `.agents/`, `.github/`, symlinks) — a `.gitignore` entry hiding any of them empties the funnel for a fresh clone; CI: the `doctrine` job.
11. **A tracked root is a multi-file edit** — move together: (1) the stage table, (2) *Where does this text go?*, (3) `README.md` § *Repository Structure*, (4) the `doctrine` job's tracked-path list, (5) `AC-FUN-002`'s dirs when it is a stage; CI names the root. → `ADOPTING.md` step 6

### Where does this text go?

| If the writing is… | It goes to |
|---|---|
| A hunch, a scratch calculation, a paste buffer | `scratchpads/` |
| An external doc / spec / transcript about the project | `kb/raw/` |
| A stable fact about how this project works | `kb/raw/` → `llm-wiki ./kb/` |
| A component runbook (run/use/update a service) | that component's `README.md` |
| A config artifact for a subject outside this repo | `ops/` + a README beside it (canonical; live = a **deploy target**) |
| A doctrine amendment | a branch + PR — **never** `scratchpads/`; discuss → an issue |
| A thing we want to build | `docs/prd/` |
| "The PRD says X but the code does Y" | `docs/gaps/` |
| "I ran it; here is what worked and failed" | `docs/NN-slug.md` |
| A bug or a question to revisit | GitHub issue |

## Harness Adapter

Harness-neutral: written against **capabilities**, not one agent product — a harness supplies its own mechanism or does the capability manually.

| Capability | Hermes | Claude Code | Copilot / other | Generic fallback |
|---|---|---|---|---|
| Entry instruction file | `AGENTS.md` (native) | `CLAUDE.md` (symlink) | `.github/copilot-instructions.md` (symlink) | read `AGENTS.md` manually |
| Repo-scoped skills / plugins | `.agents/skills`, `.agents/plugins` | same, via symlinks | symlink the vendor dir to `.agents/` | inline the skill's `SKILL.md` |
| Host-level skills | `~/.hermes/skills/` | `~/.claude/skills/` | vendor-specific | — |
| Sub-agent delegation | `delegate_task` / `kanban` | `Task` tool sub-agents | vendor-specific | do the work inline, in the documented phase order |
| Plan scratch space | `~/.hermes/plans/*.md` | `scratchpads/` | `scratchpads/` | `scratchpads/` |
| Code graph (structural search) | `codegraph install` → `$HERMES_HOME/config.yaml` | `codegraph install` → `./.mcp.json` | `codegraph install` | MCP client: `codegraph serve --mcp`; none: the CLI twins |
| Pipeline invocation | `/goal <request>` **(Hermes-only)** | prompt the phases below in order | prompt the phases below in order | prompt the phases below in order |
| KB synthesis (funnel stage 3) | `/llm-wiki ./kb/` (native) | invoke `llm-wiki` on `./kb/` | invoke `llm-wiki` on `./kb/` | inline `.agents/skills/llm-wiki/SKILL.md` by hand |
| Issue tracking (funnel stage 7) | `gh issue create` / `comment` | same | same | same |

**Per-harness rows.** Harnesses not columned above:

| Harness | Entry instruction file | Repo-scoped skills | Host-level skills | Sub-agents | Code graph | Plan scratch space | KB synthesis (stage 3) | Pipeline invocation |
|---|---|---|---|---|---|---|---|---|
| **opencode** | `AGENTS.md` (native) | `.agents/skills` honoured natively | `~/.config/opencode/skills/` or vendor in | — | MCP via `codegraph install`, or the CLI twins | `scratchpads/` | `llm-wiki` on `./kb/` | prompt the phases (no slash command) |
| **DeepSeek / OpenAI-compatible** | read `AGENTS.md` manually | vendor into `.agents/skills/`, or inline `SKILL.md` | — | run the phase order inline | no MCP client — the codegraph CLI twins `codegraph explore\|…` | `scratchpads/` | `llm-wiki` by hand | prompt the phases |
| **Codex CLI / Cursor / Gemini CLI / Aider** | `AGENTS.md` native (Gemini CLI: `GEMINI.md`) | `.agents/skills`, else README § *Skills* | — | — | — | `scratchpads/` | `llm-wiki` by hand | prompt the phases |

**Two symlink families, both pointing at one canonical source.** Entry points — every one resolves to `AGENTS.md`:

```
CLAUDE.md                        -> AGENTS.md
GEMINI.md                        -> AGENTS.md
.github/copilot-instructions.md  -> ../AGENTS.md
```

Skill/plugin roots — `.agents/` is canonical, harness dirs point into it:

```
.agents/skills/                  # canonical, tracked
.agents/plugins/                 # canonical, tracked
.claude/skills                   -> ../.agents/skills
.claude/plugins                  -> ../.agents/plugins
```

Adding a harness = two symlinks (`ln -s AGENTS.md <entry-file>`, `ln -s ../.agents/skills <vendor-dir>/skills`) plus a row above. `.agents/` pins `root-cause` (the gate's procedure); `.claude/agents/investigator.md` binds it for Claude Code (a read-only sub-agent returning cited evidence or "not found"); other harnesses run it inline.

## Lifecycle — Zero to Deployment (coding-agent entry point)

Every substantive request runs two stages in order; the coding agent MUST follow this sequence.

### Development stage — idea → implemented

| # | Step | Do | Done when |
|---|------|----|-----------|
| D0 | Entry | **Zero:** fill the `[Project Name]` / *(adapt)* placeholders. **Existing:** capture current code + docs into `kb/raw/`, `codegraph sync` | No placeholder left / project in `kb/raw/` |
| D1 | Prompt → intent | `/goal` kickoff: triage, then funnel stages 0–4 (`scratchpads/` → `kb/raw/` → `llm-wiki ./kb/` → PRD + SC + verification policy) | SC list with `_Verify:` annotations, each traceable to a `kb/` page |
| D2 | Gaps | Diff `kb/` ↔ PRD ↔ codebase into `docs/gaps/` (stage 5) | Every gap names its Resolution |
| D3 | Implement | `opencode-plan-build-orchestrator`: plan → build → verify via subagents (tests per §5) | SC tests green locally |
| D4 | Empirical docs | `docs/NN-slug.md` + verdict row via `coding-agents-docs-guideline` (stage 6) | Verdict recorded with its verification commands |

**Kickoff prompt:** `/goal <whatever user request>` + the shared footer.

**Shared footer** — append to the kickoff and every sub block (sub2/sub3: prefix `if problems surface, `):

```
use pm skills for PRD, problem triage, success criteria definition and verification policy.
use karpathy skill for codebase investigation and all resource analysis.
prioritize task delegation over direct execution.
use opencode-plan-build-orchestrator skill for all coding tasks.
```

### Delivery stage — ship to UAT or production

**Subsequent prompts (run in order):**

```
## sub1 — docs/tests gap sync
check gaps in docs/ and tests/ against codebase. update + drop obsolescences accordingly.

## sub2 — local CI
run github action locally using https://github.com/nektos/act

## sub3 — PR + CI monitor
PR using yeet. thoroughly provide context in the PR using coding agent docs skill. lastly monitor CI/CD in PR.

## sub4 — merge + redeploy
squash and merge to main all test-passed PRs.
then git checkout main and pull here.
lastly do full redeployment cycle from pull to serve.
```

**UAT variant (opt-in)** — a repo with a `uat` branch + UAT stack replaces `sub4` with these; the contract becomes `sub1`–`sub5`:

```
## sub4 — merge to uat + redeploy
squash and merge to uat all test-passed PRs (create uat from main if it is missing).
then git checkout uat and pull here.
lastly do full redeployment cycle from pull to serve — the UAT stack.

## sub5 — promote uat → main
open ONE PR from uat into main and monitor its CI to terminal, then squash and merge it.
then git checkout main and pull here.
lastly do full redeployment cycle from pull to serve — the production stack.
```

### Running the pipeline without `/goal`

`/goal` is a **Hermes-only** slash command; a harness without it prompts the same steps in order — the canonical cross-harness contract is the `D0`–`D4` and `sub1`–`sub4` (UAT: `sub1`–`sub5`) labels plus the phase table below, so **"go through sub1-4"** is valid everywhere. Or use this table:

| # | Phase | Do | Done when |
|---|-------|----|-----------|
| `sub1` | Docs/tests gap sync | Diff `kb/` ↔ `docs/prd/` ↔ codebase ↔ `tests/`; record divergences in `docs/gaps/`, update, and drop obsolescences | No SC without a test; no doc claiming behaviour the code lacks; every `docs/gaps/` file has a Resolution |
| `sub2` | Local CI | Run the workflows locally with [`nektos/act`](https://github.com/nektos/act) — `-j unit`, `-j integration`, `-j secret-scan`, `-j doctrine`, `-j ops-drift`; E2E runs directly, not under act (see §6) | those five jobs green + `bash tests/run.sh --with-e2e` green |
| `sub3` | PR + CI monitor | Open the PR with full context in the body; watch remote CI to completion | Remote CI green |
| `sub4` | Merge + redeploy | Squash-merge green PRs, `git checkout main && git pull`, run the full redeploy cycle | Service healthy from a clean pull |
| `sub4`/`sub5` (UAT) | UAT variant | As the UAT blocks above | UAT, then production, healthy from a clean pull |

Report each step's *Done when* before the next; a surfacing problem re-enters D1 triage first.

**Skill-to-phase mapping** (full table: `README.md` § *Skills*): stage-3 knowledge `llm-wiki` on `./kb/`; PRD / triage / SCs / verification policy `pm`; codebase & resource investigation `karpathy-guidelines`; root-cause questions `root-cause`; empirical docs `coding-agents-docs-guideline`; delegation the harness's adapter mechanism; all coding `opencode-plan-build-orchestrator`.

---

## Standing Orders (ALWAYS apply)

### 1. Mandated Skills

Load on EVERY task: `karpathy-guidelines`, `security-best-practices`, `webapp-testing`, `coding-agents-docs-guideline` (docs — stage 6), `llm-wiki` (stage 3, its only writer), `root-cause`, `yeet` (git), `opencode-plan-build-orchestrator` (coding). A mandated skill resolves wherever the harness provides it (host-level `~/.hermes/skills/`, `~/.claude/skills/`, `~/.config/opencode/skills/`; repo-scoped `.agents/skills/`; or its `SKILL.md` inlined — rule 8): a missing tool never waives the gate.

### 2–3. Delegation & Code Quality

- **Every delegated coding task MUST include** `opencode-plan-build-orchestrator` + `karpathy-guidelines` in the subagent's goal context; the parent never writes repo-tracked files (docs excepted); without a delegation mechanism it still reports plan → build → verify separately.
- **No `shell=True`**; **no hardcoded secrets**; **no `requests` without `timeout=N`**; **never log or commit a credential**; **webhook signatures are verified before the payload is read**; `set -euo pipefail` and `$()` in bash; **Docker images pin tags**. → `docs/02-autoresearch-contract.md`

### 4. Verification

After any change: `docker compose build && docker compose up -d`; `docker compose ps`; `bash tests/run.sh --with-e2e`; `git diff --cached | grep -iE '(api_key|secret|token|password)' || echo Clean`. → `README.md`

### 5. PRD → Test → CI Pattern

Every `docs/prd/` PRD: SC bullets with inline `_Verify:` annotations (test file + ID), a **Test Mapping** table, a `## CI/CD Gate` section, `AC-<DOMAIN>-NNN` IDs whose hundreds digit is the tier, one runner + one CI job per tier (host-dependent tests use the `tests/conftest.py` preflight; shared-infrastructure ones are opt-in). → `PRD.md` § *Verification Policy*

### 6. CI/CD Pipeline — Local-First, Then Remote

**No PR opens on a known-red local CI run.** The pre-PR command is `act push -j` each of `unit`, `integration`, `secret-scan`, `doctrine`, `ops-drift` — one `-j` per invocation; multi-`-j` silently drops all but the last (act 0.2.89, verified 2026-10-16). **Never run `act push` unqualified, or `-j e2e`, on a host that also serves this compose project**: the E2E job's `docker compose up -d --build` **replaces the running containers**; run E2E off the deployment.

### 7. Output-Medium Escalation

For explanatory output, climb to the richest useful rung: prose → controlled English (ASD-STE100-style) → diagram → HTML page → explainer video — all code/text, verified by render → parse, never by looking (works for a non-visual engine). Large custom artifacts are **discardable**: build them in `scratchpads/` and never cite them (funnel rule 6). Skills: `simple-english`, `diagrams`, `render-verify`, `explainer-video`. → `docs/prd/13-output-medium-doctrine.md`; `kb/concepts/output-medium-escalation.md`

### Ops artifacts — repo canonical, live location a deploy target

`--check` reports drift read-only, `--apply` writes live behind a confirmation env var, generated state excluded both ways, vendored copies are byte-copies. → `ops/README.md`

## Repository Structure

Canonical tree in `README.md` § *Repository Structure*. `.agents/` is canonical (`.claude -> .agents`); the entry files symlink here; a new tracked root is a five-file edit (rule 11).

## Development Commands

```bash
git config core.symlinks true   # once per clone — entry points are symlinks
bash scripts/verify-clone.sh    # read-only clone health check
bash tests/run.sh --with-e2e    # unit + integration + container tiers
act push -j unit                # one -j per invocation (see § 6)
```

Pre-PR local CI has ONE home: § 6. → `README.md`

## Security

- **Never commit `.env`, API keys or JWT secrets** — only `.example` shapes are tracked → `.credentials/README.md`.
- **Credential homes:** `.env` = injected at deploy time (the default); `.credentials/` = an operator-placed key file — record the home and the variable/file NAME, never the value (rule 9).
- **Never paste a live value into `kb/` or `docs/`** — `kb/raw/` is add-only, so a leak is unfixable by edit.
- **Every inbound webhook is signature-verified before its payload is read** — unsigned or unknown senders are rejected; CI's `secret-scan` enforces it.

## codegraph

[CodeGraph](https://github.com/colbymchenry/codegraph) is the **primary graph search for coding agents** here — a local-first tree-sitter → SQLite symbol/edge graph over MCP (MIT).

One MCP tool by design, `codegraph_explore`. **Without an MCP client, use the CLI twins** `codegraph explore|node|callers|callees|impact|query|affected`. Install `npm i -g @colbymchenry/codegraph` → `codegraph install` → `codegraph init`. Scripted runs set `DO_NOT_TRACK=1`. → `docs/prd/07-codegraph-adoption.md`

### graphify (optional)

Non-code knowledge graph (docs, SQL, configs, PDFs): `graphify query|path|explain`. → `kb/comparisons/codegraph-vs-graphify.md`
