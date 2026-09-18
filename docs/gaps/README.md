# docs/gaps — Gap Observations

Funnel stage 5 (see *Document Funnel* in `AGENTS.md`). A gap doc records **one
observed divergence** between two adjacent funnel stages. It is transient: it exists
to be closed.

Two kinds, and only two:

| Kind | Divergence | Typical cause |
|------|-----------|---------------|
| `kb ↔ prd` | The PRD asserts something the KB does not support, or the KB holds knowledge no PRD acts on | PRD written ahead of the knowledge, or stale intent |
| `prd ↔ code` | The codebase does not do what the PRD says, or does something no PRD asked for | drift, undocumented work, abandoned intent |

Divergence between *PRD* and *observed runtime behaviour* is not a gap doc — that is
stage 6, `docs/NN-slug.md`, authored via `coding-agents-docs-guideline`.

## Naming

```
docs/gaps/NN-slug.md      # NN = zero-padded sequence, matching docs/ and docs/prd/
```

## Required sections

```markdown
# NN — <short gap title>

**Layers:** kb ↔ prd | prd ↔ code
**Status:** open | resolved
**Opened:** YYYY-MM-DD

## Observation

What each side says, with paths and line refs for both. No interpretation.

| Side | Source | Claim |
|------|--------|-------|
| A | `kb/concepts/x.md` | ... |
| B | `docs/prd/01-topic.md:42` | ... |

## Evidence

The commands run and their output. A gap with no evidence is a hunch — it belongs in
`scratchpads/`.

## Impact

Who or what breaks if this stays open. If nothing does, close it as `wontfix`.

## Resolution

Exactly one of:

- `kb/raw/` ingest + `llm-wiki ./kb/` — the knowledge was missing
- PRD edit — the intent was wrong or stale
- Code change + test — the code was wrong (route through the coding pipeline)
- GitHub issue #N — real, but not now

State which, link it, then flip **Status** to `resolved`.
```

## Lifecycle

```
sub1 gap sync  ──►  docs/gaps/NN-slug.md (open)
                          │
                          ▼
              resolution applied upstream
                          │
                          ▼
              Status: resolved  ──►  moved to docs/gaps/_archive/ once merged
```

Rules:

1. **One gap per file.** Two divergences = two files.
2. **No open gap survives a merge to `main` without a Resolution section.** An
   unresolvable gap becomes a GitHub issue and the file is closed pointing at it.
3. **Gaps never carry fixes.** They observe; upstream stages change.
4. **Every open gap has a row below.** `docs/README.md` points here for the gap
   listing — a gap file with no row is invisible to the next agent.

## Open gaps

| # | Gap | Layers | Status | Opened |
|---|-----|--------|--------|--------|
| 03 | [kb/raw articles cite scratchpad paths as their evidence](03-kb-raw-scratchpad-citations.md) | kb ↔ prd | open | 2026-09-18 |
| 07 | [The CodeGraph knowledge base has no stage-4 PRD](07-codegraph-no-prd.md) | kb ↔ prd | open | 2026-09-18 |

Resolved gaps leave this directory but stay in the repo, their path structure preserved
under `docs/gaps/_archive/`:

- **Archived 2026-09-18** — resolutions landed in PR #9, files moved to
  [`_archive/`](_archive/): `04-corpus-counts-stale.md`,
  `05-sc7-start-command-drift.md`, `05-sc8-upgrade-paths-undocumented.md`,
  `05-unit-auth-id-collision.md`, `06-runbook-unverified.md`,
  `06-test-mapping-ac-034-stale.md`.
- **Removed 2026-09-18**, before this directory existed, their resolutions having landed in
  PRs #3–#5: `02-contract-files-missing.md`, `03-governance-tests-missing.md`,
  `04-corpus-tests-missing.md`, `05-dual-exposure-not-implemented.md` and
  `06-single-topic-no-isolation.md`. Those five names resolve to nothing by design; two of
  the numbers were reused (`03`, `04`), so a stale link must be read against this note.
