---
title: Headless Harness Invocation
created: 2026-10-28
updated: 2026-10-28
type: concept
tags: [agentic, integration]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: high
---

# Headless Harness Invocation

How a loop drives a coding agent with no human in the session. This is the adapter seam of
[[harness-portability]] made concrete: the exact argv each studied engine builds, so an
adapter can be written from evidence instead of guesswork.
^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## argv by harness

Five harnesses appear in the corpus; `dsh` appears in exactly one repo.

| Harness | Exact argv from source | Repo |
|---------|------------------------|------|
| Claude Code | `claude -p <prompt> --model <m> [--permission-mode auto\|--dangerously-skip-permissions] [--max-turns N] --output-format stream-json --verbose [--add-dir <dir>] [--resume <sid>]` | CORAL |
| Claude Code | `claude -p <prompt> --output-format stream-json --verbose --model <m> --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --add-dir <ws> --max-budget-usd 10.0 --dangerously-skip-permissions [--resume <sid>]` | FAROS |
| Claude Code | `claude -p --resume <SID> --fork-session --output-format json --permission-mode bypassPermissions` | evo |
| Claude Code | `bwrap … claude --print --output-format json --model <m> --session-id <uuid> --resume <uuid> --disallowedTools=WebFetch,WebSearch --permission-mode bypassPermissions --max-budget-usd <remaining> "<prompt>"` | GEPA |
| Claude Code | `claude -p --dangerously-skip-permissions … < PROMPT_FILE` — prompt on **stdin** | steer |
| Claude Code | `claude -p --permission-mode plan\|dontAsk --tools … --output-format stream-json <prompt>` | Thoth |
| opencode | `opencode run --model <m> --format json [--continue --session <id>] <prompt>` | CORAL |
| Codex | `codex exec [resume <id>] <prompt> --dangerously-bypass-approvals-and-sandbox --model <m> --json` | CORAL |
| Codex | `codex exec -C <repo> --ephemeral --json --output-last-message <file> [--model <m>] (--sandbox workspace-write \| --dangerously-bypass-approvals-and-sandbox) -` — prompt on **stdin** | leo-lilinxiao |
| Codex | `codex exec -m gpt-5.4 --json -C <root> --dangerously-bypass-approvals-and-sandbox <prompt>` | Thoth |
| DeepSeek Harness (`dsh`) | `dsh --profile headless [--patch <p>]… --patch .dsh/coral-model.patch.yml <prompt>` | CORAL |
| Cursor `agent` | `agent -p --trust --yolo --workspace … < PROMPT_FILE` | steer |
| Hermes | **no argv in the corpus** — evo drives it through a background terminal and polls; the harness's own one-shot form is `hermes chat -q <prompt>` **[unverified in this study]** | evo |

## Four adapter rules

1. **Prompt as argv or stdin — support both.** argv is more common and simpler to log; stdin
   avoids argv length limits (leo-lilinxiao's `-`, steer's `< PROMPT_FILE`). An adapter that
   only supports one will fail on the other family.
2. **The edit is collected out of band.** Every repo takes the change from the working tree, a
   commit, or a designated file (`candidate.txt` in GEPA) — never from stdout. stdout is the
   *result envelope* (`--output-format json` / `stream-json` / `--json`), parsed for cost,
   usage and session id; GEPA uses it to update the remaining budget and to detect a zero-cost
   iteration.
3. **Session continuity is per-harness.** `--resume <id>` (claude), `--continue --session <id>`
   (opencode), `resume <id>` (codex), `--session-id` + `--resume` (GEPA), `--fork-session` to
   branch per attempt (evo). `--ephemeral` (leo-lilinxiao) is the opposite, defensible choice:
   bounded per-iteration context with all cross-iteration memory in the repo and the event log.
4. **Credentials by name, never by argv.** No studied repo passes a key on the command line.
   The variables that appear are `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`,
   `GEMINI_API_KEY` (aideml's provider set) and the indirection `ACTIVE_PROVIDER_NAME` /
   `OPENAI_BASE_URL` / `ACTIVE_MODEL_NAME` (FAROS). research-loop's profile schema accepts only
   `required_env` **names** and recursively rejects secret-like fields; aideml is the
   counter-example — provider keys stay in the environment of the child process that runs
   generated code, stripped only inside its own end-to-end test. Record the variable name and
   its home (`.env` injected at deploy, `.credentials/` operator-placed), never a value.

## Why the flags belong in an adapter

evo's loop is welded to `claude -p --resume --fork-session --permission-mode`, so portability
would be a rewrite rather than a config change; FAROS's only file-editing path is Claude Code
and its "generic" OpenAI-compatible fallback cannot edit files at all, so a provider change
silently degrades the loop to a chat bot. The fix is a small class per CLI — build argv, parse
the result envelope, capture the session id, collect the edit — with the loop calling
`run_adapter(prompt) -> {exit, envelope, session_id}`. CORAL's `coral/agent/builtin/` is the
reference shape (four adapters, one per CLI), and `dsh` support exists in exactly one place,
which is why it is worth copying rather than re-deriving.

The sandbox question is orthogonal and belongs in the same seam: only GEPA pairs approval
bypass with an OS sandbox (`bwrap`), and it also strips web tools to close the "look up the
benchmark answer" hack.

## Related

- [[harness-portability]] — the entry-file and skill-root half of the same seam.
- [[script-owned-keep-revert]] — the loop that calls the adapter.
- [[verify-guard-contract]] — what the adapter's edit is measured by.
- [[autoresearch-engines-real-world]] — the 15-system comparison.
