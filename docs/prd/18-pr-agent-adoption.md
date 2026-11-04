# PRD 18 — Optional PR-Agent Adoption (Opt-In AI Code Review)

> Intent: add **PR-Agent** (the open-source AI PR reviewer, `The-PR-Agent/pr-agent`,
> MIT) to this template as an **explicit opt-in** feature: dormant until the adopter
> flips a repo variable and mounts credentials, with the OpenAI-compatible base URL,
> API key and model fully customizable (LiteLLM gateway / any cloud / local vLLM).
> Grounded in: raw source
> [2026-11-04-pr-agent-research](../../kb/raw/articles/2026-11-04-pr-agent-research.md)
> (llm-wiki synthesis page pending — see the gap note in Scope).
> Pattern precedent: [codegraph-adoption PRD 07](07-codegraph-adoption.md) — the
> template's "optional but recommended, opt-in, agent-detectable" slot.

## Context

**Problem.** PRs in repos built from this template get human review only. The
2026-11-03 research (video + 3 subagent briefs, captured in the raw source above)
concluded the strongest purpose-built OSS reviewer is PR-Agent: MIT-licensed,
model-agnostic via LiteLLM (any OpenAI-compatible endpoint), every-forge, actively
maintained (v0.49.0, 2026-10-25). Key benchmark finding adopted here: purpose-built
single-call pipelines beat free-form agentic loops at defect finding, so PR-Agent is
the every-PR reviewer; deep repo-wide questions stay with the agent harnesses of
PRD-17.

**Why optional.** PR-Agent consumes an LLM budget on every PR event and posts bot
comments; a template adopter must explicitly choose that. The mechanism is the
GitHub-native one: the workflow job is gated on a repo **variable**
(`vars.PR_AGENT_ENABLED == 'true'`) — job-level `if` cannot reliably test secrets —
plus repo **secrets** for credentials. Until both exist the workflow never runs.
"Let the agent know it's there when secrets are mounted": `.env.example` carries a
commented `# ─── PR-Agent (optional) ───` block, so `scripts/gen-env.py` surfaces the
variable names to any agent that reads `.env` — keys filled locally = the CLI
(`pip install "pr-agent[github]"`) can review pre-PR; secrets set on GitHub = CI
reviews every PR.

**Users.** (a) A template adopter who wants AI code review but decides *whether*,
*which model* and *which endpoint* themselves; (b) this repo's maintainer, who can
opt in on any clone by setting one variable + two secrets.

**Constraints.** No new runtime deps (the action is Docker-based, invoked from CI
only); every `uses:` SHA-pinned (AC-QC-002); deny-all top-level `permissions:`
(AC-QC-001); no `pull_request_target` (AC-QC-004); fork PRs never receive secrets
(`pull_request` trigger gives none); no secret value in any tracked file — variable
NAMES only; zizmor (`--min-severity low`) must pass on the new workflow.

## Scope

In: `.github/workflows/pr-agent.yml` (opt-in gate, hardened); repo-root
`.pr_agent.toml` (tuning placeholders + comments); `.env.example` optional block;
`tests/unit/test_pr_agent_adoption.py` (`AC-PRA-*`); README § PR-Agent (optional);
`AGENTS.md` § pr-agent (one paragraph, like § codegraph); kb/raw capture + llm-wiki
synthesis page; PRD index + changelog rows.
Out: webhook/GitHub-App deployment modes (single-repo Action is enough); org-wide
`global_settings_repo`; Tier-2 on-demand agent review (opencode `/oc`) — a separate
future PRD if wanted; changing any existing workflow, gate or AC from other domains.

## Success Criteria

- **SC1 — The reviewer exists as an opt-in workflow.**
  `.github/workflows/pr-agent.yml` triggers on `pull_request`
  (types: opened, reopened, ready_for_review, synchronize) and `issue_comment`;
  its single job runs **only** when `vars.PR_AGENT_ENABLED == 'true'` **and**
  `github.event.sender.type != 'Bot'`; top-level `permissions: {}`; the job elevates
  to `contents: read`, `issues: write`, `pull-requests: write` only; the action ref
  is SHA-pinned with a version comment.
  _Verify:_ `tests/unit/test_pr_agent_adoption.py` (AC-PRA-001..004) + existing
  AC-QC-001..004 + the `zizmor` CI job.
- **SC2 — Endpoint, key and model are customizable, never hardcoded.**
  The configuration surface uses the conventional OpenAI names so any adopter (or
  agent) recognizes them without PR-Agent-specific knowledge: repo **secret**
  `OPENAI_API_KEY` (the key), repo **variables** `OPENAI_BASE_URL` (any
  OpenAI-compatible endpoint — LiteLLM gateway, cloud, local vLLM) and
  `OPENAI_DEFAULT_MODEL` (unset → the workflow falls back to a sane default). The
  workflow maps these onto PR-Agent's own env (`OPENAI_KEY`, config overrides) —
  the mapping lives only inside the workflow file. No literal URL, model id or
  credential appears in any tracked file.
  _Verify:_ `tests/unit/test_pr_agent_adoption.py` (AC-PRA-005, 006).
- **SC3 — Agents detect the feature when secrets are mounted.**
  `.env.example` gains a commented `# ─── PR-Agent (optional) ───` block listing
  exactly the conventional names the workflow consumes — `OPENAI_API_KEY`,
  `OPENAI_BASE_URL`, `OPENAI_DEFAULT_MODEL` (plus a local `PR_AGENT_ENABLED`
  switch), values placeholder-only (`changeme` / empty) — consistent with
  `scripts/gen-env.py` (PRD 14), which copies comments verbatim into `.env`.
  _Verify:_ `tests/unit/test_pr_agent_adoption.py` (AC-PRA-007).
- **SC4 — Tuning lives in one committable file.**
  Repo-root `.pr_agent.toml` exists, holds commented tuning knobs
  (`extra_instructions`, suggestion score threshold) and no credential-looking
  values; a comment names the docs.
  _Verify:_ `tests/unit/test_pr_agent_adoption.py` (AC-PRA-008).
- **SC5 — The instructions surface knows the feature.**
  README carries a "PR-Agent (optional)" how-to-enable block (variable + secrets +
  `.env` mapping); `AGENTS.md` carries a `## pr-agent` section in the § codegraph
  style ("optional, dormant until enabled"); both mention PRD 18.
  _Verify:_ `tests/unit/test_pr_agent_adoption.py` (AC-PRA-009).
- **SC6 — Knowledge is grounded.**
  The raw research capture exists under `kb/raw/articles/` (add-only) and the
  `llm-wiki` synthesis pass over `./kb/` regenerates `kb/index.md` with a PR-Agent
  page; PRD.md gains the PRD-18 index row and changelog entry.
  _Verify:_ existing `tests/unit/test_kb_layout.py` + `test_kb_synthesis.py`
  (green after synthesis), plus the `doctrine` CI job.
- **SC7 — Local tiers stay green.**
  `bash tests/run.sh` (unit + integration) passes with the new test file; the new
  workflow passes the `secret-scan` and `doctrine` gates' assumptions (tracked-path
  list unchanged — no new tracked root).
  _Verify:_ `bash tests/run.sh`; local `act push -j unit` equivalents in CI.

## Test Mapping

| Tier | File | IDs | Covers |
|---|---|---|---|
| Unit | `tests/unit/test_pr_agent_adoption.py` | `AC-PRA-001..009` | SC1–SC5 structural guards |
| Unit (existing) | `tests/unit/test_quality_controls.py` | AC-QC-001..004 | Hardening of the new workflow (pinning, permissions, trigger) |
| Unit (existing) | `tests/unit/test_kb_layout.py`, `test_kb_synthesis.py` | — | SC6 kb integrity |
| CI | `zizmor`, `secret-scan`, `qc-gate` | — | SC1, SC7 |

## CI/CD Gate

No new CI job: the new workflow is dormant-by-default (its job gate evaluates false
until the adopter opts in), so the `qc-gate` aggregate and required checks are
unchanged. PRD-16's AC-QC-001..004 and the zizmor job apply to the new file
automatically because the QC tests glob `.github/workflows/*.yml`.

## Gaps

- `kb/` layer-2 synthesis page for PR-Agent is produced by `llm-wiki ./kb/` in the
  same change-set (SC6); until then this PRD's grounding rests on the raw capture.
  Resolution: run synthesis before merge.
