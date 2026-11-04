# 12 — Service Runtime State

## What

`service/data/` is the runtime-state root of the autoresearch service: a gitignored tree holding the SQLite job store (`service/data/jobs.db`) and one isolated workspace per job (`service/data/workspaces/<job_id>/`), whose only tracked content is the placeholder `service/data/.gitkeep`.

## Why

- The job store and the per-job workspaces are generated, never authored — nothing in them is a source document, so they belong to the run rather than to the repo.
- Git must still see the directory: the service writes into `service/data/` without creating a tracked parent, so `service/data/.gitkeep` stays tracked while the contents are ignored by rule.
- The purge scan found 453 workspace directories totalling 13 MB accumulated in the then-current root (repo-root `data/`, activity window Sep 5-21) with no bound and no consumer; none carried `results.tsv` or any durable state. The commit message of `7c5613a` is the only surviving record of that scan — the directories were untracked, so the count is not re-derivable from the repo.
- The root moved from repo-root `data/` to `service/data/` on 2026-11-04 to match the upstream template layout (funnel stage 6 record: [18-root-layout-refactor.md](18-root-layout-refactor.md)). `service/` is already a declared tracked root, so `service/data/` adds no new tracked root of its own.

## How

### Layout

| Path | Produced by | Tracked |
|---|---|---|
| `service/data/.gitkeep` | the purge commit `7c5613a`, moved with the 2026-11-04 refactor | yes — the placeholder that keeps the directory in a clone |
| `service/data/jobs.db` (plus `-wal` / `-shm` sidecars) | `service/src/jobs.py` (`JobStore`, WAL mode); path from `RESEARCH_JOBS_DB`; unset default resolves to `<service-root>/data/jobs.db`, and compose passes `data/jobs.db` (relative to WORKDIR `/app`) | no |
| `service/data/workspaces/<job_id>/` | `provision_workspace` (`service/src/workspace.py`); root from `RESEARCH_WORKSPACES_DIR`, default `service/data/workspaces` | no |
| `service/data/workspaces/<job_id>/<prepare.py,train.py,context.json,topic.txt>` (plus `corpus/…` when the job declares texts/files) | the provisioner copying the canonical `autoresearch/contract/` per job | no |

Lifecycle: the store and a job's workspace appear on the first run and are retained after the job reaches a terminal state. No TTL sweeper exists — `docs/05` and `docs/06` record the sweeper over the workspaces root as a documented upgrade path.

### Ignore rules — `.gitignore`

```gitignore
# === Runtime SQLite job store + per-job workspaces ===
# the service writes its jobs DB to service/data/jobs.db (RESEARCH_JOBS_DB
# default resolves under service/; /app/data in the container)
service/data/*
!service/data/.gitkeep
```

Contents are ignored by rule, only the placeholder is un-ignored, so a newly generated name inside the root never reaches `git status`.

### Tracked-root declarations (before and after)

The original purge promoted repo-root `data/` to a derived tracked root, which had to be declared in three places (funnel rule 11). That root no longer exists; its declaration was retired on 2026-11-04, and `service/data/` is covered by the existing `service` root entry in each list.

| Place | Before (to 2026-11-04) | After |
|---|---|---|
| `.github/workflows/ci.yml` | `DOCTRINE_ROOTS: "... contract data docs ..."` | `"... .github autoresearch docs ... service tests"` — no `data` entry |
| `tests/unit/test_funnel_structure.py` | `REQUIRED_DIRS` entry `"data"` | no `data` entry; `"autoresearch"` and `"service"` remain |
| `README.md` | Structure tree entry `├── data/` | `service/` with a `└── data/` child |

`scripts/verify-clone.sh` check 3 runs the same derived-root sweep offline, which is why a missing declaration surfaces before CI.

### The purge

Commit `7c5613a` added the two placeholders (`data/.gitkeep`, `service/data/.gitkeep`) plus the two un-ignore lines — `git show --stat 7c5613a` reports 3 files, +2/-0. The 453 directories / 13 MB / Sep 5-21 activity window is the purge **scan**'s finding, recorded only in the commit message; the directories were untracked, so the count is not re-derivable from the repo. Each scanned directory held only the four provisioned files; none held a results log or durable state, so the next job rebuilds whatever it needs.

## Verification

Run from the repo root, 2026-11-04 (the current `service/data/` layout).

```bash
# 1. only the placeholder is tracked
$ git ls-files service/data/
service/data/.gitkeep

# 2. the root ignores its contents by rule
$ git check-ignore -v service/data/jobs.db service/data/workspaces/x
.gitignore:63:service/data/*	service/data/jobs.db
.gitignore:63:service/data/*	service/data/workspaces/x

# 3. clone health, including the tracked-root coverage check
$ bash scripts/verify-clone.sh 2>&1 | grep RESULT
RESULT: PASSED — 31 check(s) passed

$ bash scripts/verify-clone.sh 2>&1 | grep tracked-root
PASS  tracked-root coverage — 11 tracked top-level directory(ies), all declared

# 4. the guards that own the declaration
$ python3 -m pytest tests/unit/test_funnel_structure.py tests/unit/test_verify_clone.py -q
12 passed in 0.49s

# 5. full unit + integration tier, against the committed doc set
$ python3 -m pytest tests/unit tests/integration -q
356 passed, 1 warning in 141.55s (0:02:21)
```

Historical record of the pre-move layout, 2026-09-26:

```bash
# 1. only the placeholders were tracked
$ git ls-files data/ service/data/
data/.gitkeep
service/data/.gitkeep

# 2. both roots ignored their contents by rule
$ git check-ignore -v data/jobs.db data/workspaces/x service/data/jobs.db
.gitignore:63:/data/*	data/jobs.db
.gitignore:63:/data/*	data/workspaces/x
.gitignore:65:service/data/*	service/data/jobs.db

# 3. clone health
$ bash scripts/verify-clone.sh 2>&1 | grep RESULT
RESULT: PASSED — 34 check(s) passed
```

`#5` counts the committed doc set. While an uncommitted `docs/NN-*.md` exists, `test_docs_readme_status_rows` (`AC-DOC-003`) fails until that doc has its row in `docs/README.md` — a docs-catalog state unrelated to `service/data/`.

Regression reproduction — the purge commit, before its rule-11 declarations:

```bash
SCR=$(mktemp -d) && git clone -q . "$SCR" && cd "$SCR" && git checkout -q 7c5613a

$ bash scripts/verify-clone.sh 2>&1 | grep -E "^( *data is|FAIL|RESULT)"
      data is a tracked top-level directory missing from the list in .github/workflows/ci.yml — add it there AND to AC-FUN-002 (funnel rule 11)
FAIL  tracked-root coverage (14 derived, list incomplete)
RESULT: FAILED — 1 check(s) failed

$ python3 -m pytest tests/unit -q
FAILED tests/unit/test_corpus_integrity.py::test_articles_frontmatter_and_sha
FAILED tests/unit/test_verify_clone.py::test_real_repo_passes_and_reports_a_nonzero_check_count
FAILED tests/unit/test_verify_clone.py::test_real_repo_run_is_read_only
3 failed, 119 passed, 1 warning in 4.11s
```

## What Works

- The root ships a tracked placeholder: `git ls-files service/data/` returns exactly `service/data/.gitkeep`.
- Contents are ignored by rule with only the placeholder un-ignored, so no path under `service/data/` ever appears in `git status`, however much the service or the tests generate.
- `bash scripts/verify-clone.sh` reports `RESULT: PASSED — 31 check(s) passed`, including `tracked-root coverage — 11 tracked top-level directory(ies), all declared`; `service/` is named in the `doctrine` job's list and the check is not passing vacuously.
- `AC-FUN-002` and `AC-FUN-003` pass: the `service` entry exists in the tree and matches the `ci.yml` line, so the two lists cannot drift.
- The job-store fallback is service-root-relative, not cwd-relative: `JobStore()` with `RESEARCH_JOBS_DB` unset resolves to `<service-root>/data/jobs.db` (test: `test_db_path_fallback_is_service_data`).
- The purge scan found 453 workspaces / 13 MB with nothing durable in any of them — the store and every workspace are regenerated by the next run, and no directory held a results log; the commit itself records only the two placeholders and the two un-ignore lines (3 files, +2/-0).
- An idle service is visible as an absent `service/data/jobs.db`: the store is created by `JobStore` on first use, never committed.

## What Fails

- **The purge is a one-time cleanup, not a bound.** The repo's own test tiers refill the root against the default path: `python3 -m pytest tests/unit/test_routes.py` added one workspace and the integration tier added seven in one pass (measured workspace counts 6 → 7 and 7 → 14, when the root was repo-root `data/`). Nothing deletes a workspace after a terminal job, so growth resumes with use.
- **The purge landed before its rule-11 declarations.** At `7c5613a` the tracked root existed while the list that must name it did not: `bash scripts/verify-clone.sh` reported `RESULT: FAILED — 1 check(s) failed` (`FAIL  tracked-root coverage (14 derived, list incomplete)`, naming `data`), and the unit tier was `3 failed, 119 passed` — the two real-repo `test_verify_clone` tests plus an unrelated `test_corpus_integrity` sha256 drift. CI is red on that commit.
- **A test that exercises a run without overriding `RESEARCH_JOBS_DB` / `RESEARCH_WORKSPACES_DIR` writes into `service/data/`.** A freshness check cannot distinguish runtime state from tracked content, so the guards assert the placeholder and the ignore rule instead, and any such test leaves real artifacts behind in the tracked tree.

## Resolution

- **The purge is a one-time cleanup, not a bound.** Add the TTL sweeper over `service/data/workspaces` that `docs/05` and `docs/06` record as the upgrade path, or delete the directories between runs; the root holds no durable state, so removing it is always safe.
- **The purge landed before its rule-11 declarations.** Fixed in `80b78b2` — `data` was added to `DOCTRINE_ROOTS`, to `REQUIRED_DIRS`, and to the `README.md` structure tree. Land a tracked root and all three declarations in one commit: the `doctrine` job and `AC-FUN-003` both fail in either direction. The root was retired from all three lists in one edit on 2026-11-04.
- **A test that exercises a run without overriding `RESEARCH_JOBS_DB` / `RESEARCH_WORKSPACES_DIR` writes into `service/data/`.** Point any such test at a temp `RESEARCH_JOBS_DB` and `RESEARCH_WORKSPACES_DIR`; assert on the placeholder and the ignore rule (`git ls-files service/data/`, `git check-ignore -v`), never on the generated files.

## Verdict

**works** — the root tracks only its placeholder, ignores all contents by rule, and every tracked-root guard (`verify-clone` check 3, the `doctrine` job, `AC-FUN-002`/`003`) confirms `service/` is declared; the root's contents remain unbounded runtime state that the documented TTL sweeper, not the purge, has to control.
