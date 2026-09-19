# ops/ — repo ↔ deploy contract

ops/ is the tracked, canonical home for configuration artifacts that drive a subject operated OUTSIDE this repo (a scheduler/orchestrator, board or graph definitions, wrapper scripts, cron entries, per-environment manifests). The live location — where those artifacts are actually deployed and read from — is a DEPLOY TARGET, not a source of truth. Rule: the repo is canonical; the live side is a copy.

1. **Repo is canonical.** `ops/README.md` carries the repo-path ↔ deploy-path map.
2. **Two modes, never one.** The sync tool has `--check` (read-only drift report; safe to run anywhere, including CI) and `--apply` (writes the live target; gated behind an explicit confirmation env var). A read-only mode a CI job can run is what makes drift visible at all.
3. **Classify before vendoring: artifact vs runtime state.** A file that another process GENERATES is runtime state. Vendoring it makes `--check` permanently red AND lets `--apply` overwrite live state with a stale snapshot. Runtime state is excluded in BOTH directions — the side that generates a file owns it.
4. **Re-vendor, don't hand-edit.** Vendored copies are byte-copies. When the live side changes first, copy it back into `ops/` and re-run `--check`. Never edit one side alone.
5. **Loud enumeration.** Every deployable root fails loudly when it is absent, unenumerable or empty, and the success line is unreachable over a copy that deployed nothing. A symlinked root deploys THROUGH the link, not around it.
6. **Live-side drift too.** `--check` enumerates the live side as well and reports files that exist live with no vendored counterpart, with generated runtime state excused by an explicit, path-scoped allowlist.

The map below is the only place a deploy path is stated. `ops/sync.sh` reads it as
its defaults; nothing else in the repo hardcodes a live path.

## Repo-path ↔ deploy-path map

| Repo path (canonical) | Deploy path (live) | Mode |
|---|---|---|
| `ops/artifacts/<rel>` | `${OPS_LIVE_ROOT}/<rel>` | byte-copy, `cp -p` (mode travels, so a wrapper stays executable) |
| `ops/artifacts/pipeline.example.json` | `${OPS_LIVE_ROOT}/pipeline.example.json` | example artifact — rename off `.example` in your project |
| `ops/artifacts/wrapper.example.sh` | `${OPS_LIVE_ROOT}/wrapper.example.sh` | example artifact (mode 755) |
| `ops/artifacts/cron.example` | `${OPS_LIVE_ROOT}/cron.example` | example artifact — installed into the live crontab by hand |
| `ops/state-allowlist.txt` | — never deployed | repo-only: it is the exclusion list, not an artifact |
| `ops/README.md`, `ops/sync.sh` | — never deployed | repo-only tooling |

Only `ops/artifacts/**` is deployable. Everything else under `ops/` — this README,
`sync.sh` itself, the allowlist — stays in the repo.

## Classification — artifact or runtime state?

Decide for every file you are tempted to vendor. The question is who *writes* it.

| Path (live side) | Class | Who owns it | How sync treats it |
|---|---|---|---|
| `pipeline.example.json`, `wrapper.example.sh`, `cron.example` | **artifact** — declared by a human, edited in the repo | repo (canonical) | `--check` compares content both ways; `--apply` copies repo → live |
| `*-manifest.json` (per the allowlist) | **runtime state** — written by the scheduler on every run | the live side | excused on the live side, and refused on the repo side: vendoring one is a classification bug |
| `results.tsv`, `*.log` | **runtime state** — output of a run | the live side | keep out of `ops/`; they belong to the run, not the config |

Two failure modes this table prevents:

- **Vendored runtime state.** Copy a generated `run-manifest.json` into `ops/`, and
  `--check` is permanently red (the generator rewrites it), while `--apply`
  overwrites live state with a stale snapshot. Classify first, vendor second.
- **Ignored live-only state.** A generated file the repo has never seen is not drift.
  Name it in `ops/state-allowlist.txt` (one glob per line, `#` comments, path-scoped);
  a live-only file that matches is excused by name, not by accident.

## How to adopt this

If your project has no externally-operated subject — nothing deployed outside the repo
for another process to read — **delete `ops/`** (README, tool, artifacts, allowlist) and
the pointers to it. The doctrine row stays: it is what tells the next adopter that this
slot exists. Deleting the worked example is cheap; discovering three months in that the
only copy of your wrapper script is on one host is not.

If you do have one:

1. Rename the examples off `.example` (or drop them) and add your own artifacts under
   `ops/artifacts/`. Keep them small — this is config, not output.
2. Set `OPS_LIVE_ROOT` to the directory the live process actually reads.
3. Run `--check` first. Every drift line is either a missing deploy or a live-side
   edit you have not re-vendored yet (contract rule 4).
4. Add your generated runtime state to `ops/state-allowlist.txt`.
5. Wire `--check` into CI (it writes nothing, so it is safe on any runner).

## `--check` in CI — the `ops-drift` job

`.github/workflows/ci.yml` runs `ops/sync.sh --check` in the `ops-drift` job. This
template ships no live deploy target, so by default the job **self-fixtures**: it
deploys the vendored artifacts into a temp root with `--apply`, checks that root, then
mutates one deployed file and requires `--check` to fail naming it. That is what proves
drift is detectable without a real target.

**To gate your own target, set the `OPS_LIVE_ROOT` repository variable** (Settings →
Secrets and variables → Actions → **Variables**) to the directory the live process
reads. The job then skips both fixture steps and runs `--check` against that target
instead — red on drift, exactly as it is locally.

`--apply` is never run against a configured target from CI: the two steps that write are
gated on the self-contained mode, so a misconfigured variable cannot make a CI run
mutate your deploy target.

The local equivalent is the same command:

```bash
OPS_LIVE_ROOT=/path/to/live ops/sync.sh --check
```

## Worked example

```bash
# Inspect. Read-only: safe in CI, safe on the deploy host, exit non-zero on drift.
OPS_REPO_ROOT="$PWD" OPS_LIVE_ROOT="$HOME/ops-live" ops/sync.sh --check
#   mode         : check
#   repo root    : /srv/repo
#   artifact dir : /srv/repo/ops/artifacts
#   live root    : /home/me/ops-live
#   allowlist    : /srv/repo/ops/state-allowlist.txt
#   DRIFT wrapper.example.sh — vendored and live differ in content
#   exit 1

# Deploy. Gated: without OPS_APPLY_CONFIRM=1 it prints why and exits non-zero.
OPS_REPO_ROOT="$PWD" OPS_LIVE_ROOT="$HOME/ops-live" OPS_APPLY_CONFIRM=1 ops/sync.sh --apply
#   deployed 3 artifact(s) to /home/me/ops-live
#   == sync complete ==
```

`--live` overrides `OPS_LIVE_ROOT` for a one-off run: `ops/sync.sh --check --live /tmp/scratch`.
A `--live` path that is a symlink to a directory works — the copy goes *through* the
link, and `--check` enumerates through it too.

## Where the map and the allowlist live

- **The map**: the table above, in this file. To add a deployable, add its file under
  `ops/artifacts/` and a row here.
- **The allowlist**: `ops/state-allowlist.txt` — one glob per line, `#` starts a
  comment, blank lines ignored. Patterns are matched against the path *relative to the
  deploy root* (`*-manifest.json` matches `board/run-manifest.json`). It is repo-only
  and never deployed. Override the path for a one-off run with `OPS_ALLOWLIST`.
- **The tool**: `ops/sync.sh`. Its `--help` restates the interface; the env fallbacks
  are in the header comment.

Unit tests for the tool (loud enumeration, both-direction drift, the apply gate, the
symlinked root) live in `tests/unit/test_ops_sync.py`.
