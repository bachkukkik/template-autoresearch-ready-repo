---
title: Harness Portability
created: 2026-10-16
updated: 2026-10-28
type: concept
tags: [agentic, architecture]
sources: [raw/articles/2026-10-16-autoresearch-oss-landscape.md, raw/articles/2026-09-26-autoresearch-methodology-registration.md, raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: high
---

# Harness Portability

How one canonical source serves many coding-agent harnesses. The doctrine (see
[[document-funnel-doctrine]]) is **capabilities, not products**: write for what a
harness *can* do, and give each harness a binding for that capability — never a
fork of the content.

## The entry-instruction file

One canonical `AGENTS.md`; every harness resolves to it, natively or via a thin
adapter. Verified against each vendor's own documentation:

| Harness | Entry file | How |
|---------|-----------|-----|
| opencode | `AGENTS.md` | native (`opencode.ai/docs/rules`) |
| Codex CLI | `AGENTS.md` | native |
| Cursor | `AGENTS.md` | native — "Simple alternative to `.cursor/rules`" (`cursor.com/docs/rules`) |
| GitHub Copilot coding agent | `.github/copilot-instructions.md` + `AGENTS.md` | repo-wide file, plus the nearest `AGENTS.md` in the directory tree (`docs.github.com`) |
| Claude Code | `CLAUDE.md` | also reads a repository's `AGENTS.md` in place of it (`docs.claude.com`) |
| Gemini CLI | `GEMINI.md` | default name; configurable via `contextFileName` (can be set to `AGENTS.md`) |
| Aider | `CONVENTIONS.md` | `aider --read CONVENTIONS.md` (or `/read`); `read:` in `.aider.conf.yml` |
| generic | read `AGENTS.md` manually | inline the capability's `SKILL.md` |

Symlink, never copy: `CLAUDE.md -> AGENTS.md` and
`.github/copilot-instructions.md -> ../AGENTS.md` are literally the same bytes as
the canonical file, so the doctrine cannot fork. `git config core.symlinks true`
is the one per-clone prerequisite.

## Skill and plugin roots

`.agents/skills` and `.agents/plugins` are canonical; `.claude/skills` and
`.claude/plugins` symlink into them. A harness with no skill mechanism inlines
the skill's `SKILL.md` — a missing mechanism never waives a gate.

## What the OSS study adds

- **CORAL** *generates* its instruction file with the active runtime's shared dir
  substituted (a runtime registry), instead of shipping N copies.
- **Arbor** ships the same loop logic as 11 plain-Markdown skill directories that
  transfer to any harness, with the package itself optional.
- **uditgoenka** is the counter-example: it generates harness ports with `sed`
  into `.opencode/`, `.agents/skills/` and `claude-plugin/`, so the copies **drift**
  — the exact failure mode the symlink rule avoids.

^[raw/articles/2026-10-16-autoresearch-oss-landscape.md]

## Related

- [[document-funnel-doctrine]] — the harness adapter and the `/goal`-vs-phase-table rule.
- [[autoresearch-contract]] — the loop the harness runs.
- [[autoresearch-oss-landscape]] — the portability evidence.
- [[headless-harness-invocation]] — the other half of the seam: the exact argv per harness
  (`claude -p`, `opencode run`, `codex exec`, `dsh --profile headless`), including the two
  prompt-transport families and the session-resume flags.
- [[autoresearch-engines-real-world]] — the 2026-10-28 study; its portability finding is that
  a single-harness loop with vendor flags in its spine (evo, GEPA, pi) is a rewrite to port,
  while CORAL's `agent/builtin/` four-adapter shape is the reference seam.
