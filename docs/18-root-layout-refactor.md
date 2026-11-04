# 18 — Root Layout Refactor

## What

The repo root now matches the upstream foundation template's shape: the contract and the
engine live under one tracked root, `autoresearch/` (`autoresearch/contract/`,
`autoresearch/engine/`); the repo-root `data/` is gone in favour of `service/data/`; and
`ops/` no longer exists. Tracked top-level directories fell from 14 to 11 (10 to 7
excluding dot-directories), and `git ls-files | cut -d/ -f1 | sort -u` names none of
`contract/`, `engine/`, `data/` or `ops/`.

## Why

- **The root was wider than the template it claims to be.** `bachkukkik/template-agentic-ready-repo`
  carries 8+ top-level directories; this repo carried 14 (10 non-dot) because each
  capability had been granted its own root. An adopter diffing the two trees reads a
  different taxonomy before reading a single doc.
- **The contract and the engine are one capability, not two.** `contract/` defines the
  loop's roles and the frozen evaluator; `engine/` runs it. Grouping them under
  `autoresearch/` states that relationship and removes an ambiguity where `contract/`
  read like a legal or API document.
- **`ops/` was this repo's own extension, never baseline adoption.** The PRD 1.6.0
  provenance note records it as an extension; upstream has no `ops/`, and its only
  subject (a deploy-target sync tool) had no live consumer in this template.
- **`data/` at the root was the wrong owner.** Runtime state is produced by the service
  (docs/12); the root had already been narrowed once to `service/data/`, and the
  remaining root copy was a duplicate declaration waiting to drift.

## How

### Before and after

```bash
$ git ls-tree -r --name-only HEAD | cut -d/ -f1 | sort -u    # before, at b7b153d (wrapped)
.agents .claude .credentials .env.example .gitattributes .github .gitignore
.pr_agent.toml ADOPTING.md AGENTS.md CLAUDE.md GEMINI.md LICENSE PRD.md README.md
SECURITY.md contract data docker-compose.yml docs engine kb ops scratchpads scripts
service tests

$ git ls-files | cut -d/ -f1 | sort -u                      # after (wrapped for width)
.agents .claude .credentials .env.example .gitattributes .github .gitignore
.pr_agent.toml ADOPTING.md AGENTS.md CLAUDE.md GEMINI.md LICENSE PRD.md README.md
SECURITY.md autoresearch docker-compose.yml docs kb scratchpads scripts service tests
```

Top-level directories: 14 → 11 (`git ls-tree -d --name-only HEAD | wc -l` = 14;
`tracked-root coverage — 11 tracked top-level directory(ies), all declared`).

### Move map

| Before | After | Notes |
|---|---|---|
| `contract/` (`program.md`, `prepare.py`, `train.py`, `examples/`) | `autoresearch/contract/` | `git mv`; the frozen `prepare.py` bytes did not change, so the `AC-TPL-014` sha256 pin still matches |
| `engine/` (`autoresearch/` package, `bin/autoresearch`, README) | `autoresearch/engine/` | `git mv`; the wrapper derives `ENGINE_DIR` from its own path, so it still sets `PYTHONPATH` correctly |
| `data/` (`.gitkeep` plus runtime state) | `service/data/` | one placeholder remains tracked; `JobStore`'s unset default is `<service-root>/data/jobs.db`, the workspaces default is `<service-root>/data/workspaces`, and compose passes `data/jobs.db` / `data/workspaces` relative to `WORKDIR /app` |
| `ops/` (`README.md`, `sync.sh`, `artifacts/`, `state-allowlist.txt`) | deleted | `AC-OPS-001..010`, `tests/unit/test_ops_sync.py`, the `ops-drift` CI job and its `qc-gate` wiring retired; PRD-08 SC1 and docs/08 carry a retirement note rather than a silent drop |

### Follow-through

A tracked root is a multi-file edit (funnel rule 11), and a *moved* root reaches further
than its declaration list:

- Declarations: `DOCTRINE_ROOTS` in `.github/workflows/ci.yml`, `REQUIRED_DIRS` +
  `AC-FUN-002` in `tests/unit/test_funnel_structure.py`, the `README.md` structure tree,
  and `scripts/verify-clone.sh`'s tracked-root sweep all name `autoresearch` and none of
  the retired roots.
- Consumers: `service/src/runner.py`'s contract search, the compose read-only mount
  (`./autoresearch/contract:/app/contract:ro`), `.github/CODEOWNERS`, and every
  `sys.path` insert in `tests/unit/test_engine_*.py`.
- Documentation: current-state path claims in `README.md`, `docs/README.md`,
  `docs/03`, `docs/06`, `docs/07`, `docs/10`, `docs/11`, `docs/12`, the PRD bodies and
  `PRD.md`'s 2.3.0 changelog row were rewritten. Historical evidence (verbatim command
  output, commit quotes such as `80b78b2 contract/examples: …`, the gap evidence table
  at `afcab6c`, dated changelog rows) was left byte-identical.

## Verification

Run in the refactor worktree (branch `refactor/root-layout`, all changes staged), 2026-11-04.

```bash
# 1. no retired root is tracked any more
$ git ls-files | cut -d/ -f1 | sort -u | tr '\n' ' '
.agents .claude .credentials .env.example .gitattributes .github .gitignore .pr_agent.toml ADOPTING.md AGENTS.md CLAUDE.md GEMINI.md LICENSE PRD.md README.md SECURITY.md autoresearch docker-compose.yml docs kb scratchpads scripts service tests

# 2. the full hermetic tier
$ python3 -m pytest tests/unit tests/integration -q -p no:cacheprovider 2>&1 | tail -3
356 passed, 1 warning in 141.24s (0:02:21)

# 3. clone health, including the tracked-root sweep
$ bash scripts/verify-clone.sh 2>&1 | tail -3
PASS  python3 and tests/run.sh are present
      next: bash tests/run.sh --with-e2e

RESULT: PASSED — 31 check(s) passed

$ bash scripts/verify-clone.sh 2>&1 | grep tracked-root
PASS  tracked-root coverage — 11 tracked top-level directory(ies), all declared

# 4. the compose file still parses (no containers started on this host)
$ docker compose config -q; echo $?
0

# 5. the CI workflow is valid YAML
$ python3 -c "import yaml;yaml.safe_load(open('.github/workflows/ci.yml'))" && echo yaml-ok
yaml-ok

# 6. both entrypoints still run from their new paths
$ bash autoresearch/engine/bin/autoresearch --help | head -5
usage: autoresearch [-h] [--version] {init,run,status,report,doctor} ...

Script-owned keep/discard research loop: verify prints the metric, guard
decides if a candidate may win, the ledger records both.

$ cd autoresearch/contract && timeout 120 python3 prepare.py --help 2>&1 | head -3
usage: prepare.py [-h] [--check-ledger PATH]

Frozen autoresearch evaluator — dataset summary, or a results.tsv ledger

# 7. service runtime state: one placeholder, contents by rule
$ git ls-files service/data/
service/data/.gitkeep

$ git check-ignore -v service/data/jobs.db
.gitignore:63:service/data/*	service/data/jobs.db
```

## What Works

- The root now carries the upstream taxonomy: 11 tracked top-level directories, with the
  contract and the engine under `autoresearch/` exactly as upstream groups its loop.
- The full hermetic tier is green (`356 passed`) after the move — including
  `AC-TPL-014`, the byte pin on the frozen `prepare.py`, which proves the file moved
  without changing content.
- Both entrypoints resolve from the repo root: `autoresearch/engine/bin/autoresearch --help`
  prints its usage, and `cd autoresearch/contract && python3 prepare.py --help` does too.
- The service's runtime defaults are service-root-relative (`<service-root>/data/jobs.db`,
  `<service-root>/data/workspaces`), so the repo-root `data/` removal changed no runtime
  behaviour; `test_db_path_fallback_is_service_data` still passes.
- `bash scripts/verify-clone.sh` is `RESULT: PASSED — 31 check(s) passed` with
  `tracked-root coverage — 11 tracked top-level directory(ies), all declared` — the
  declaration lists and the tree agree in both directions.
- The ops retirement is documented rather than erased: PRD-08 SC1, `AC-OPS-001..010` and
  the `ops-drift` job carry explicit retirement notes, so the audit trail survives the
  deletion.
- `docker compose config -q` exits 0 and the CI workflow parses as YAML, so the mount
  rewrite and the job removal left both descriptors valid.

## What Fails

- **Three `kb/` layer-2 pages still name the old root.** `kb/concepts/script-owned-keep-revert.md:60`,
  `kb/concepts/methodology-registration.md:38` and `kb/comparisons/autoresearch-oss-landscape.md:23`
  say `contract/`; layer-2 pages are llm-wiki-owned and must not be hand-edited, so the
  refactor could only list them.
- **Old roots remain in historical evidence by design.** Dated changelog rows, the docs/12
  pre-move `git ls-files` block, the docs/10 commit quote `80b78b2 contract/examples: …`,
  the docs/07 codegraph output line and the `at afcab6c` gap evidence table still print
  the old paths; a repo-wide grep reports them and a reader can mistake them for live
  claims.
- **A changelog link is read as a catalog row.** Writing the 2.3.0 PRD row as
  `[docs/18](docs/18-root-layout-refactor.md)` made `AC-DOC-005`
  (`test_prd_quick_reference_rows`) treat the changelog line as a Quick Reference row
  and fail: `row points at 'docs/18-root-layout-refactor.md', which is not a catalogued
  file`.
- **A rename is not a pure `git mv`.** Path strings also live in test assertions and
  messages, script output, `sys.path` inserts and doctrine line pins: `AC-HRN-011` pins
  every `/goal` line in `AGENTS.md` and failed at `[106, 129, 134, 179, 181]` versus the
  recorded `[108, 131, 136, 181, 183]` after two doctrine lines were removed above the
  cluster.

## Resolution

- **Three `kb/` layer-2 pages still name the old root.** Run `llm-wiki` on `./kb/` with
  `kb/raw/` unchanged so the three pages are regenerated from confirmed sources; until
  then the refs are listed here as the follow-up index.
- **Old roots remain in historical evidence by design.** Keep them; scope any sweep with
  `git grep … ':!kb/raw' ':!kb/_archive' ':!docs/gaps/_archive'` and classify each hit as
  current (fix), historical (keep) or layer-2 (llm-wiki).
- **A changelog link is read as a catalog row.** Reference the record as plain code text
  (`` `docs/18` ``) in `PRD.md`; the catalog row in `docs/README.md` is the only
  link-bearing line for a stage-6 doc.
- **A rename is not a pure `git mv`.** Sweep the path strings after the move and re-run
  the pinned-line guard; when doctrine text above a pin changes, recompute the pin in the
  same edit (done here for `AC-HRN-011`).

## Verdict

**works** — the root now matches the upstream grouping (11 tracked top-level directories,
`autoresearch/{contract,engine}` together, `service/data` owning runtime state, no `ops/`),
the full unit + integration tier is green at `356 passed`, `verify-clone` reports
`RESULT: PASSED — 31 check(s) passed`, and both the engine wrapper and the frozen contract
run from their new paths; the only live old-root references left are three `kb/` layer-2
pages queued for the next `llm-wiki` synthesis.
