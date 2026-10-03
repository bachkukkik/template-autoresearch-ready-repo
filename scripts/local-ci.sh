#!/usr/bin/env bash
# Local CI — the pre-PR gate (AGENTS.md §6) run with nektos/act.
#
#   bash scripts/local-ci.sh              # unit, integration, secret-scan, doctrine, ops-drift
#   bash scripts/local-ci.sh unit doctrine  # a named subset
#
# ONE INVOCATION PER JOB: `act push -j unit -j integration` runs ONLY the last job —
# act's -j is not a repeatable array. Each job gets its own `act push -j`.
#
# NEVER e2e: the `Docker E2E` job runs `docker compose up -d --build`, which REPLACES
# the running containers. On a host that serves this compose project that is
# destructive. Run E2E in CI, or on a host that serves nothing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "$#" -gt 0 ]; then
  JOBS=("$@")
else
  JOBS=(unit integration secret-scan doctrine ops-drift)
fi

for job in "${JOBS[@]}"; do
  if [ "$job" = "e2e" ]; then
    echo "refusing 'e2e': that job runs 'docker compose up -d --build' and replaces running containers." >&2
    echo "          run it in CI, or from a job list without e2e." >&2
    exit 2
  fi
done

if ! command -v act >/dev/null 2>&1; then
  echo "act not found — install from https://github.com/nektos/act" >&2
  exit 127
fi

LOG_DIR="${TMPDIR:-/tmp}"
fail=0
for job in "${JOBS[@]}"; do
  log="$LOG_DIR/act-$job.log"
  echo "==> act push -j $job"
  rc=0
  act push -j "$job" >"$log" 2>&1 || rc=$?
  status="pass"
  # act's process exit code can be 0 even when a job failed — read the job marker too.
  if [ "$rc" -ne 0 ] || grep -q 'Job failed' "$log"; then
    status="FAIL"
    fail=1
  fi
  printf '  %-14s %s   (log: %s)\n' "$job" "$status" "$log"
  if [ "$status" = "FAIL" ]; then
    grep -E '::error|Job failed' "$log" | head -5 | sed 's/^/      /'
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAILED"
  exit 1
fi
echo "RESULT: PASSED"
