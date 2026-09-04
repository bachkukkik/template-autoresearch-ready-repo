# 03 — Funnel & KB Governance

## What

The document funnel + knowledge-base governance layer: every piece of writing has
exactly one home (scratchpads → kb/raw → kb → PRD → gaps → docs/NN → issues), the
`kb/` layout follows the llm-wiki spec, and CI (`doctrine`, `sources-readonly`,
`secret-scan`) enforces the rules structurally.

## Why

The repo is governance-first (bachkukkik/template-agentic-ready-repo doctrine).
Rules survive only if they are enforced, not instructed: a forked `CLAUDE.md`
drifts silently, a `.gitignore` rule that hides `docs/` empties the funnel for
every fresh clone. The three-tier test suite closes the gap between "documented
rule" and "enforced rule" (PRD 03).

## How

- **Funnel stages:** `scratchpads/` (gitignored) → `kb/raw/` (add-only, never
  edited) → `kb/` (llm-wiki-written only) → `PRD.md` + `docs/prd/` → `docs/gaps/`
  → `docs/NN-slug.md` → GitHub issues. A `.md` that fits none of these is a
  defect.
- **CI enforcement:** `ci.yml` job `doctrine` checks harness symlinks resolve and
  funnel paths are tracked/not ignored; `sources-readonly.yml` fails a PR that
  modifies/deletes `kb/raw/**` without the `ingest` label; `ci.yml` job
  `secret-scan` includes a kb content scan (funnel rule 9).
- **pytest enforcement (new):** `test_funnel_structure.py` (AC-FUN-001..003 —
  no stray root `.md` beyond the allowlist, stage dirs exist, harness entry
  points resolve), `test_kb_layout.py` (AC-FUN-011..012 — SCHEMA/index present,
  every layer-2 page indexed, raw files only under the four raw subdirs),
  `test_gaps_lifecycle.py` (AC-FUN-021 — every gap doc has a Resolution; open
  gaps appear in the README table).

## Verification

```bash
python3 -m pytest tests/unit/test_funnel_structure.py tests/unit/test_kb_layout.py \
  tests/unit/test_gaps_lifecycle.py -v   # 6 passed (AC-FUN-001..003, 011..012, 021)
act push -j doctrine                      # Doctrine Integrity ✅
act push -j secret-scan                   # Secret Scan ✅
```

## What Works

- All 6 AC-FUN tests pass against the current tree, and the two CI jobs
  (`doctrine`, `secret-scan`) pass under act.
- Root `.md` allowlist is explicit: `AGENTS.md`, `README.md`, `PRD.md`,
  `program.md` (+ LICENSE if present) — a stray `NOTES.md` at root now fails CI
  at the pytest tier, not just by instruction.
- Harness entry points (`CLAUDE.md`, `.github/copilot-instructions.md`,
  `.claude/skills`, `.claude/plugins`) are asserted symlinks with resolvable
  targets — a plain-copy fork or dangling link is caught.
- `kb/` layer-2 pages are checked for index presence (no orphans) and raw files
  for layout compliance (no strays outside `articles/papers/transcripts/assets`).
- Gap lifecycle enforced: every `docs/gaps/NN-*.md` must carry a `## Resolution`
  and open gaps must be listed in `docs/gaps/README.md`.

## What Fails

- **Raw-layout allowance:** `test_kb_layout` tolerates `README.md`/`SCHEMA.md`
  at `kb/raw/` top level (allowlist) — slightly looser than "no stray raw files"
  literally; no such files exist today, so current state is fully compliant.
- **Gap-openness marker:** `test_gaps_lifecycle` detects "open" via the exact
  bold markup `**Status:** open`; a gap author writing plain `Status: open`
  would slip past the open-gap listing check (the Resolution check still applies
  to every gap file).

## Resolution

- **Raw-layout allowance:** keep the allowlist (matches the llm-wiki raw layout
  convention); tighten only if a stray appears — the AC-FUN-012 test flags it.
- **Gap-openness marker:** documented convention in `docs/gaps/README.md`; if a
  gap author deviates, the Resolution check still blocks the file — tighten the
  regex only if it becomes a real failure mode.

## Verdict

**works** — the governance layer is enforced in three places (documentation, CI
jobs, pytest tier) and all six AC-FUN tests pass against the current tree. Remaining
limits are minor allowlist/marker conventions that do not affect today's state.