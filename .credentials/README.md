# `.credentials/`

A key **file** an operator places on disk. The runtime reads it by path, so it cannot be
supplied as an environment variable. Every real file in here is gitignored; only
`*.example` shapes are tracked (AGENTS.md §Security).

## Which credential home?

| Home | Holds | When to use it |
|---|---|---|
| `.env` | a value injected by the environment at deploy time | the **default** for service credentials — API base URLs, bearer tokens, DB paths, webhook signing secrets |
| `.credentials/` | a key **file** an operator places and the runtime reads from disk | only what cannot travel as an env var — a service-account JSON key, PEM key material |

If the value can arrive as an environment variable — loaded from `.env` locally, injected
by the platform in production — it belongs in `.env`. Reach for `.credentials/` only when
a **file** is genuinely required.

## Rules

- **Every real file here is gitignored** (`.credentials/*`, AGENTS.md §Security). It never
  gets committed and never shows up in `git status`.
- **Only `*.example` shapes are tracked** — `.gitignore` un-ignores `.credentials/*.example`
  and `.credentials/*.example.*`. `secret-scan` in `.github/workflows/ci.yml` asserts it.
- **The tracked example is `example.json.example`.** Copy it to a real filename
  (e.g. `service-account.json`), replace every `REPLACE_ME` placeholder, and place the
  real file here. It documents the *shape* only — it is not a working key.
- **Never paste a live value into `kb/` or `docs/`.** Both are tracked and `kb/raw/` is
  add-only, so a leak there cannot be edited out (AGENTS.md funnel rule 9). Reference the
  filename — `.credentials/service-account.json` — never the value.

This README is tracked so a fresh clone sees the directory exists, what belongs in it, and
what the example shape looks like. `.credentials/` itself is empty in a clone by design.
