#!/usr/bin/env bash
# EXAMPLE ONLY. A wrapper the live scheduler invokes once per run (see ops/README.md).
# Rename it off .example, point SUBJECT_DIR at your subject, and let `--apply` deploy it.
set -euo pipefail

SUBJECT_DIR="${SUBJECT_DIR:-/srv/research/subject}"
LOG_FILE="${LOG_FILE:-${SUBJECT_DIR}/run.log}"
MAX_RUNS="${MAX_RUNS:-3}"

cd -- "$SUBJECT_DIR"

for run in $(seq 1 "$MAX_RUNS"); do
  echo "== run ${run}/${MAX_RUNS} $(date -u +%FT%TZ) =="
  python3 prepare.py >/dev/null
  python3 train.py --results results.tsv | tee -a "$LOG_FILE"
done
