---
source_url: https://github.com/The-PR-Agent/pr-agent
ingested: 2026-11-04
sha256: d4025b8973721f46e391da8c25a108569ef4331b2f10a8044bb480b7b736bbc2
kind: article
title: "PR-Agent (The-PR-Agent/pr-agent) — OSS AI PR reviewer: licence path, self-host matrix, cost traps"
---

# PR-Agent — OSS AI pull-request reviewer: licence path, self-host matrix, cost traps

Capture of the 2026-11-03 research brief on **PR-Agent**, an open-source AI PR reviewer
originally built at Qodo and now run as a community project. Scope: what the tool is, how
its licence changed three times, what it can be self-hosted on, which configuration
surfaces are now free that used to be paid, and — the part that decides adoption — what
it costs, what it silently skips, and how good its comments actually are according to
independent measurement rather than the project's own claims.

Sources are the repository at `main`, its docs site, the GitHub REST API and two arXiv
papers. Load-bearing values (licence, latest release, default model, token cap, the
action's own pinning guidance, the `/help_docs` retirement issue) were re-checked against
the live API on 2026-11-04 while writing this capture; those re-checks are marked
*re-verified* below. Nothing was executed against a real pull request.

**Bottom line.** PR-Agent is the most complete OSS option in this space and the licence is
now permissive (MIT), which removes the historic reason to avoid it. Two costs remain and
neither is a licence cost: spend is uncapped and scales with PR size, and the default
32k-token window drops files *silently* rather than failing. Independent evaluation puts
best-case comment precision near 15%, so raw output needs severity gating before a human
sees it.

## Evidence table

| # | Claim | Source |
|---|---|---|
| 1 | The repo was donated by Qodo: `github.com/qodo-ai/pr-agent` redirects to `https://github.com/The-PR-Agent/pr-agent` | <https://github.com/qodo-ai/pr-agent> (HTTP 301, repo id 662766482) |
| 2 | Canonical repo is `The-PR-Agent/pr-agent`, described as a community-maintained "legacy project of Qodo"; docs live at `docs.pr-agent.ai` | <https://github.com/The-PR-Agent/pr-agent>, <https://docs.pr-agent.ai> |
| 3 | Licence history: **AGPL-3.0** up to and including v0.35.0 → **Apache-2.0** for v0.36.0–v0.39.0 → **MIT** from v0.40.0 (licence-change commit dated 2026-07-09) | <https://github.com/The-PR-Agent/pr-agent/releases> |
| 4 | Licence today is MIT (*re-verified*: API reports `license.spdx_id = MIT`) | <https://api.github.com/repos/the-pr-agent/pr-agent> |
| 5 | Latest release **v0.49.0**, published **2026-10-25** (re-verified from the releases API) | <https://github.com/The-PR-Agent/pr-agent/releases> |
| 6 | Release cadence ≈ **1–2 weeks** | <https://github.com/The-PR-Agent/pr-agent/releases> |
| 7 | **14.3k stars** at the time of the brief; *re-verified* at 14,498 on 2026-11-04, with `pushed_at` same-day → active daily commits | <https://api.github.com/repos/the-pr-agent/pr-agent> |
| 8 | Commands: `/describe` `/review` `/improve` `/ask` `/add_docs` `/generate_labels` `/similar_issue` `/update_changelog` `/help` | <https://github.com/The-PR-Agent/pr-agent/blob/main/README.md> |
| 9 | Those tools are all OSS now; **self-reflection re-scoring is part of the OSS core**, not a paid tier | <https://docs.pr-agent.ai/core-abilities/self_reflection/> |
| 10 | `/help_docs` disabled since **v0.36.1**; the retirement traces to issue #2445 — untrusted commenters could override the git clone target and exfiltrate `GITHUB_TOKEN` through weak hostname validation (issue closed 2026-06-13) | <https://github.com/The-PR-Agent/pr-agent/issues/2445> |
| 11 | Configuration file is `.pr_agent.toml` **at the repo root**, read from the branch under review | <https://docs.pr-agent.ai/installation/github/> |
| 12 | Env-var configuration exists alongside the TOML, e.g. `CONFIG__MODEL`, `OPENAI_KEY`, `OPENAI_API_BASE` (names only — never values) | <https://github.com/The-PR-Agent/pr-agent/blob/main/README.md> |
| 13 | `extra_instructions`, `custom_labels`, `global_settings_repo` are present in the OSS settings file — formerly Pro features (*re-verified* in `configuration.toml` at `main`) | <https://github.com/The-PR-Agent/pr-agent/blob/main/pr_agent/settings/configuration.toml> |
| 14 | `pr_agent_pro.md` documents the historic free/Pro split that no longer applies | <https://docs.pr-agent.ai/overview/pr_agent_pro.md> |
| 15 | Self-host paths: GitHub Action, GitHub App (webhook), GitLab pipeline + webhook, Bitbucket, Azure DevOps, Gitea, generic Docker, pip CLI | <https://docs.pr-agent.ai/installation/github/>, <https://github.com/The-PR-Agent/pr-agent/blob/main/README.md> |
| 16 | The Action wrapper is `action.yaml` at the repo root; **pin the wrapper by commit SHA**, never `@main`/`@latest`; its runtime image is `docker://pragent/pr-agent` on a **rolling** `github_action` tag, separately digest-pinnable as `docker://pragent/pr-agent@sha256:<digest>` (*re-verified*: both pinning instructions are comments inside `action.yaml`) | <https://github.com/The-PR-Agent/pr-agent/blob/main/action.yaml> |
| 17 | CLI: `pip install "pr-agent[github]"`, then `pr-agent --pr_url <url> review`; `--json-output` emits review metadata including **coverage** and **token usage** | <https://docs.pr-agent.ai/installation/locally/> |
| 18 | **No official docker-compose** — Docker is run as a single container, not a composed stack | <https://docs.pr-agent.ai/installation/locally/> |
| 19 | Model access goes through **LiteLLM**, so OpenAI, Anthropic, DeepSeek, Ollama/vLLM and any OpenAI-compatible endpoint are reachable | <https://docs.pr-agent.ai/usage-guide/changing_a_model/> |
| 20 | OpenAI-compatible endpoints are addressed as `openai/<model-id>` plus `api_base` | <https://docs.pr-agent.ai/usage-guide/changing_a_model/> |
| 21 | Defaults at the time of the brief: `model = gpt-6.1-sol` and `max_model_tokens = 32000` (*re-verified*, with `fallback_models = ["gpt-6-luna"]`) | <https://github.com/The-PR-Agent/pr-agent/blob/main/pr_agent/settings/configuration.toml> |
| 22 | Spend is **uncapped** and scales with PR size: chunking multiplies calls and self-reflection adds a scoring pass per chunk | <https://github.com/The-PR-Agent/pr-agent/discussions/3942>, <https://docs.pr-agent.ai/core-abilities/compression_strategy/> |
| 23 | Coverage loss under the 32k default is **silent**; `files_not_reviewed` from `--json-output` is the only reliable signal | <https://docs.pr-agent.ai/faq/> |
| 24 | GitHub enforces a hard limit of **3000 changed files** per diff — beyond it the PR cannot be reviewed at all | <https://docs.pr-agent.ai/faq/> |
| 25 | Noise reduction is documented as score thresholds plus `extra_instructions`, not as severity classes | <https://docs.pr-agent.ai/faq/> |
| 26 | SWR-Bench: agentic tool-loops do **not** beat well-engineered single-call prompts at defect finding — F1 **12.61 vs 18.73** | <https://arxiv.org/abs/2509.01494> |
| 27 | SWR-Bench: multi-pass aggregation of single-call reviewers raises F1 by **+43.67%** | <https://arxiv.org/abs/2509.01494> |
| 28 | Best-case comment precision is **~15% for every model tested**, so severity gating is mandatory | <https://arxiv.org/abs/2509.01494> |
| 29 | Field study of **178 repositories / ~22k comments**: concise, snippet-bearing, manually triggered comments convert best | <https://arxiv.org/abs/2508.18771> |
| 30 | Action triggers: `pull_request` types `[opened, reopened, ready_for_review, synchronize]` plus `issue_comment` | <https://docs.pr-agent.ai/installation/github/> |
| 31 | Bot loop guard `if: github.event.sender.type != 'Bot'`; permissions `contents: read`, `issues: write`, `pull-requests: write`; **no checkout step needed** | <https://docs.pr-agent.ai/installation/github/> |
| 32 | `pull_request` from a fork gets **no secrets**; only `pull_request_target` would, and that re-opens the exfiltration class fixed in #2445 | <https://docs.pr-agent.ai/installation/github/> |
| 33 | An opt-in gate should be a **repository VARIABLE**, because a job-level `if` cannot reliably test a secret | <https://docs.pr-agent.ai/installation/github/> |
| 34 | A local Ollama endpoint requires a **self-hosted runner** — hosted runners cannot reach it | <https://docs.pr-agent.ai/installation/locally/> |

## 1. What it is and who runs it now

PR-Agent reviews pull requests with an LLM: it summarises a diff, reviews it, proposes
improvements as committable suggestions, answers questions about the change, drafts docs
and changelog entries, and labels issues. Qodo built it and then donated it; the
`qodo-ai/pr-agent` URL still resolves — as a 301 to `The-PR-Agent/pr-agent` — which is the
cleanest possible evidence of the handover. The project describes itself as a
community-maintained **legacy project of Qodo**: still actively developed (same-day pushes,
14.5k stars), but no longer the vendor's commercial focus, with docs hosted separately at
`docs.pr-agent.ai`.

The practical consequence for adopters is that the roadmap is community-shaped and the
commercial pressure that produced the old free/Pro split is gone.

## 2. Licence history — the reason adoption arguments changed

| Version range | Licence | Effect |
|---|---|---|
| ≤ v0.35.0 | AGPL-3.0 | Copyleft over the network; most companies' legal review rejects it for internal tooling |
| v0.36.0 – v0.39.0 | Apache-2.0 | Permissive, patent grant, safe for internal and commercial use |
| v0.40.0 → | MIT | Maximally permissive; the licence-change commit is dated 2026-07-09 |

Three licence changes in one project's history is unusual and worth stating plainly in any
adoption record: a reader who evaluated PR-Agent before mid-2026 was reading a different
legal artifact. Today the API reports MIT. The two permissive steps also track the removal
of the paid tier — the formerly-Pro features are now in the OSS settings file, which is
consistent with a project that stopped monetising the binary.

## 3. Tools and what is now free

`/describe`, `/review`, `/improve`, `/ask`, `/add_docs`, `/generate_labels`,
`/similar_issue`, `/update_changelog`, `/help`. Self-reflection — the second LLM pass that
re-scores each generated comment and drops low-value ones — is part of the OSS core, not a
gate. So are `extra_instructions`, `custom_labels` and `global_settings_repo`.

One tool is gone: `/help_docs` has been disabled since v0.36.1. Issue #2445 explains why,
and it is the most instructive security fact about the whole class of tools: the command
let an untrusted commenter override the git clone target, and weak hostname validation
turned that into `GITHUB_TOKEN` exfiltration. Any bot that reads a comment from an
arbitrary user and then performs a privileged fetch inherits that shape.

## 4. Configuration surface

- **`.pr_agent.toml` at the repo root** — the file is read from the branch under review,
  so a PR can change its own reviewer configuration. That is convenient and it is also a
  reviewable-diff surface worth watching.
- **Environment variables** for deployment-time values, e.g. `CONFIG__MODEL`, `OPENAI_KEY`,
  `OPENAI_API_BASE`. These are the *names*; values belong in `.env` or `.credentials/`,
  never in a tracked file.
- **`extra_instructions`** — the documented noise-reduction lever, alongside comment score
  thresholds.
- **`global_settings_repo`** — a shared settings repo so many repositories inherit one
  policy instead of duplicating TOML.

## 5. Self-hosting matrix

| Target | Mechanism | Notes |
|---|---|---|
| GitHub Action | `action.yaml` at repo root | wrapper pinned by commit SHA; runtime `docker://pragent/pr-agent` on a rolling `github_action` tag, digest-pinnable |
| GitHub App | webhook | no workflow file; the App holds the credential |
| GitLab | pipeline job or webhook | `pr-agent` CLI in a job, or the webhook server |
| Bitbucket / Azure DevOps / Gitea | webhook or pipeline | same CLI/server shapes |
| Generic Docker | single container | **no official docker-compose** |
| pip CLI | `pip install "pr-agent[github]"`; `pr-agent --pr_url <url> review` | `--json-output` carries coverage + token usage |

The Action is the cheapest entry and the one with the most published guidance. Its own
file states the pinning rule twice, because two different things roll: the wrapper
(`uses: …@<sha>`) and the runtime image (`@sha256:<digest>`). Pinning only the wrapper
leaves a moving base image underneath a fixed action.

## 6. Models

LiteLLM sits underneath, so provider choice is a string plus a key: OpenAI, Anthropic,
DeepSeek, local Ollama or vLLM, or any OpenAI-compatible endpoint addressed as
`openai/<model-id>` with `api_base` set. Defaults at capture time are `gpt-6.1-sol` with
`fallback_models = ["gpt-6-luna"]` and `max_model_tokens = 32000`. The 32k ceiling is a
global cap regardless of what the underlying model can accept — that is a cost control,
and it is the direct cause of the silent-coverage behaviour in the next section.

## 7. Cost and the two traps

**Uncapped spend.** Nothing in the OSS build meters cost. Chunking splits a diff into
per-file or per-chunk calls, and self-reflection adds a scoring call per chunk, so the
number of model calls grows faster than the diff. A large PR is not "one review" — it is
dozens, each with its own prompt overhead. Discussion #3942 is the community thread on
this.

**Silent coverage loss.** The 32k default means a big PR is partly unreviewed, and the
tool does not fail or warn in the comment stream. The only dependable signal is
`files_not_reviewed` in `--json-output`. Any CI wiring should treat a non-empty
`files_not_reviewed` as a failed review, not a successful one.

**Hard ceiling.** GitHub itself refuses diffs over 3000 changed files, so very large PRs
have no path through the tool at all — the fix there is splitting the PR, not tuning the
model.

**Noise.** The FAQ's answer is score thresholds plus `extra_instructions`. That works, but
it is a filter on the output rather than a severity model on the input, which matters given
the precision numbers below.

## 8. Does it actually find defects?

Two independent results set the expectation.

SWR-Bench (<https://arxiv.org/abs/2509.01494>) measured agentic tool-loop reviewers against
well-engineered single-call prompts and found the loops **worse** at defect finding: F1
12.61 versus 18.73. The same work found that aggregating several single-call reviewers
raises F1 by **+43.67%** — the gain comes from multi-pass aggregation, not from giving the
model tools. And best-case comment precision is roughly **15% for every model tested**,
meaning about six of seven comments are wrong or unwanted in the best case. Severity
gating is therefore not a nicety; it is the difference between a reviewer people read and
one they mute.

The field study at <https://arxiv.org/abs/2508.18771> (178 repositories, ~22k comments)
supplies the interaction data: concise comments, comments carrying a code snippet, and
comments produced on **manual** trigger are the ones that get acted on. Auto-fire on every
push, verbose prose, and no snippet is the losing configuration.

Read together: PR-Agent's own self-reflection pass is the right instinct (it is a
re-scoring filter), but it does not close a 15%-precision gap on its own, and the
tool-loop-vs-single-call result argues against assuming more agentic behaviour will fix it.

## 9. GitHub Actions deployment pattern for private repos

```yaml
on:
  pull_request:
    types: [opened, reopened, ready_for_review, synchronize]
  issue_comment:
    types: [created]

jobs:
  review:
    if: github.event.sender.type != 'Bot'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: The-PR-Agent/pr-agent@<full-commit-sha>
        env:
          OPENAI_KEY: ${{ secrets.OPENAI_KEY }}   # example variable name only
```

Points that come from the deployment docs rather than from taste:

- **Both triggers are needed** — `pull_request` for the automatic pass, `issue_comment` for
  on-demand `/review`. The field study says the on-demand path is the one that converts,
  so shipping only the automatic pass is choosing the weaker half.
- **`if: github.event.sender.type != 'Bot'`** prevents the bot's own comment from
  re-triggering it. Without it, `issue_comment` plus a bot reply is an infinite loop.
- **No `actions/checkout`.** The tool reads the diff through the API; a checkout only
  widens the blast radius and adds nothing.
- **Least privilege** is `contents: read` plus `issues: write` and `pull-requests: write`.
  Nothing needs `contents: write`.
- **Fork PRs receive no secrets on `pull_request`.** That is the safe default and the
  reason not to reach for `pull_request_target`: doing so would restore exactly the
  untrusted-input-plus-privileged-token shape that #2445 was about.
- **Pin by full commit SHA.** The action's own file says so, and separately recommends a
  digest pin for the rolling runtime image.
- **Gate it behind a repository VARIABLE**, not a secret check in a job `if`. A job-level
  `if` cannot reliably test a secret's presence, so the opt-in has to be a `vars.*` flag.
- **Local models need a self-hosted runner.** A hosted runner cannot reach an Ollama
  instance on your network; this is a runner-placement problem, not a configuration one.

## 10. Limits of this capture

Star count, release and licence were re-checked live on 2026-11-04; the licence-history
boundaries (v0.35.0 / v0.36.0 / v0.40.0) are as recorded in the 2026-11-03 brief and were
not re-derived release by release. The two arXiv results are about AI code review
generally, not PR-Agent specifically — they bound what any reviewer of this shape can
achieve, and quoting them as PR-Agent's own precision would be a misreading. Nothing here
was executed against a live pull request: no spend number, no latency figure and no
measured `files_not_reviewed` rate is claimed.

## Cross-references

- Loop-integrity vocabulary this capture borrows (guard vs objective, coverage as a
  verifier property): layer-2 page `autoresearch-engines-real-world`, and
  `kb/concepts/verify-guard-contract.md`.
- Where a reviewer bot sits in this repo's funnel: `AGENTS.md` § *Document Funnel*.
- Companion raw sources: `kb/raw/articles/2026-10-28-autoresearch-real-world-engines.md`,
  `kb/raw/articles/2026-10-16-autoresearch-oss-landscape.md`.
