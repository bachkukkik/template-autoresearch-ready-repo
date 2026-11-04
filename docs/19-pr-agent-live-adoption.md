# 19 — PR-Agent Live Adoption

## What

The optional PR-Agent reviewer (PRD 18) enabled and verified live: the workflow
fires on real PRs, calls the gateway model, and posts review comments; three
configuration layers had to be fixed in sequence before the first green run.

## Why

PRD 18 shipped the feature dormant-by-default; its success criteria are
structural (workflow shape, test guards). A live enablement proves the design
works against real infrastructure and surfaces the configuration traps a
template adopter will hit, which structural tests cannot.

## How

Enablement is two GitHub-side switches plus one tuning file — no code change:

1. Repository variables (Settings → Secrets and variables → Actions):
   `PR_AGENT_ENABLED=true`, `OPENAI_BASE_URL` (the gateway base URL including
   `/v1`), `OPENAI_DEFAULT_MODEL=openai/<model-id>`.
2. Repository secret `OPENAI_API_KEY` (the gateway key).
3. `.pr_agent.toml` on **`main`** declaring `custom_model_max_tokens` — see
   *What Fails* below.

The model id needs the `openai/` prefix because PR-Agent calls models through
LiteLLM: an unprefixed `<vendor>/<model>` is parsed as a LiteLLM provider route
(`<vendor>` public API) and never reaches `OPENAI_API_BASE`; the `openai/`
prefix keeps the call on the OpenAI-compatible path pointing at the gateway.

Tuning in `.pr_agent.toml` (committed, credential-free — AC-PRA-008):

```toml
[config]
custom_model_max_tokens = 32000   # not in PR-Agent's built-in MAX_TOKENS table
fallback_models = ""              # built-in fallbacks don't exist on a custom gateway
```

## Verification

```bash
# The job runs and posts to the PR thread (name: PR Agent):
gh pr checks <PR>   # → PR Agent  pass
# The reviewer output is visible as bot comments:
gh api repos/<org>/<repo>/issues/<PR>/comments --jq '.[].user.login'
```

Observed live (2026-11-04, PR #40): job green in 49 s; two bot comments posted
("PR Reviewer Guide" with effort estimate, "PR Code Suggestions" — correctly
empty for a comment-only diff).

## What Works

- Dormant-by-default gate: with `PR_AGENT_ENABLED` unset the job skips
  (verified on PR #39 before enablement) and no tokens are spent.
- End-to-end review on a real PR through a custom OpenAI-compatible gateway.
- Structured output: reviewer guide (effort, test/security observations) +
  scored code suggestions, self-reflection applied.
- Repo-root tuning file is read by the action **without a checkout step**
  (fetched from the default branch via the API).

## What Fails

- **Bot-management challenge:** datacenter IPs (GitHub-hosted runners) receive
  a "Just a moment…" interstitial from the edge proxy in front of the gateway;
  all model calls fail with HTML instead of JSON. Residential/VPS clients are
  unaffected, so host-side curls succeed while CI fails.
- **Provider routing:** model id `zai/glm-5.3-flash` (no `openai/` prefix) is
  routed to the vendor's public API — errors reference the vendor exception
  class and "not available for this API key", even though the same id works
  through the gateway from a local client.
- **Unknown-model token budget:** `Model … is not defined in MAX_TOKENS … and
  no custom_model_max_tokens is set` — the action fails fast (≈40 s) on any
  model outside its built-in table.
- **Built-in fallbacks:** PR-Agent's default fallback models do not exist on a
  custom gateway; each fallback adds a wasted round trip per failed call.

## Resolution

- **Bot-management challenge:** disable the zone's automatic bot-challenge
  mode (free plan: no per-rule exemption exists). The gateway is already
  key-authenticated, so the challenge adds nothing for an API endpoint.
- **Provider routing:** set `OPENAI_DEFAULT_MODEL=openai/<model-id>` — the
  prefix selects LiteLLM's OpenAI-compatible path, which honors the custom
  base URL.
- **Unknown-model token budget:** declare `custom_model_max_tokens` in
  `.pr_agent.toml` **on the default branch before the first enabled run** —
  the action reads it from the base branch of the PR, not the PR head, so a
  tuning PR cannot fix its own review run.
- **Built-in fallbacks:** set `fallback_models = ""` in the same toml.

## Verdict

Works: the reviewer is live and produces useful structured review output on
every PR, with the adopter owning endpoint, key, model and tuning. The three
traps above are all first-enablement configuration issues, fixed in-repo or in
repo settings — nothing remains outstanding in PRD 18's scope. The repo is
**opted out again** (`PR_AGENT_ENABLED=false` since 2026-11-04 21:09 UTC): the
reviewer is dormant, and re-enablement is one variable flip — endpoint, key,
model and tuning all stay in place.
