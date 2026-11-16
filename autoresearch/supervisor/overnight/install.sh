#!/usr/bin/env bash
# Thin wrapper: install this recipe's files and its job into a scheduler profile.
# Usage: bash autoresearch/supervisor/overnight/install.sh --profile <p> [--dry-run]
# ${BASH_SOURCE:=…} keeps `sh install.sh` from expanding to a wrong directory.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
exec python3 "${here}/../install.py" "${here}" "$@"
