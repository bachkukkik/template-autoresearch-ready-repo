#!/usr/bin/env bash
# ex5 — turn this example into a disposable autoresearch target.
#
#   bash setup.sh [DEST]          # DEST defaults to ${TMPDIR:-/tmp}/ex5
#
# Copies the example into DEST, makes it a fresh git repo on `main` with one
# baseline commit, then records the engine's run config there. Nothing outside
# DEST is written; the example directory in this repo is left untouched.
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${1:-${TMPDIR:-/tmp}/ex5}"

# The engine lives in the template repo three levels up; AUTORESEARCH_ENGINE
# overrides it for a copy of this example that was moved somewhere else.
engine="${AUTORESEARCH_ENGINE:-}"
if [[ -z "$engine" ]]; then
  probe="$here"
  while [[ "$probe" != "/" && ! -d "$probe/engine/autoresearch" ]]; do
    probe="$(dirname -- "$probe")"
  done
  if [[ ! -d "$probe/engine/autoresearch" ]]; then
    echo "error: no engine/ found above $here; set AUTORESEARCH_ENGINE to the repo's engine directory" >&2
    exit 2
  fi
  engine="$probe/engine"
fi

command -v git >/dev/null || { echo "error: git is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "error: python3 is required" >&2; exit 2; }

if [[ -d "$dest" && "$dest" -ef "$here" ]]; then
  echo "error: DEST is the example directory itself; pass a scratch path" >&2
  exit 2
fi
if [[ -e "$dest" && -n "$(ls -A "$dest" 2>/dev/null)" ]]; then
  echo "error: $dest exists and is not empty" >&2
  exit 2
fi

mkdir -p "$dest"
cp -R "$here"/. "$dest"/
rm -rf "$dest/.autoresearch"
find "$dest" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

git -C "$dest" init -q -b main
git -C "$dest" add -A
git -C "$dest" \
  -c user.name='autoresearch setup' \
  -c user.email='autoresearch@localhost' \
  commit -qm "ex5: pristine NLTK 3.9.1 distance.py as the baseline"

# bench.py and guard.py are protected by name; every file under oracle/ is
# protected individually because `init --protect` takes files, not directories.
# (Scope `target` already makes any edit outside it a scope violation — this is
# the second lock on the same door.)
protect_args=(--protect bench.py --protect guard.py)
while IFS= read -r rel; do
  protect_args+=(--protect "$rel")
done < <(cd "$dest" && find oracle -type f | LC_ALL=C sort)

PYTHONPATH="$engine" python3 -m autoresearch init \
  --repo "$dest" \
  --verify "python3 bench.py" \
  --guard "python3 guard.py" \
  --metric-name seconds \
  --direction lower \
  --scope target \
  "${protect_args[@]}" \
  --repeats 3 \
  --noise-floor 0.02 \
  --program program.md \
  --goal "cut the median seconds of the vendored NLTK distance workloads without changing a single output"

cat <<EOF

ready: $dest
engine: $engine

  cd $dest
  PYTHONPATH=$engine python3 -m autoresearch run --repo . --agent claude --dry-run
  PYTHONPATH=$engine python3 -m autoresearch run --repo . --agent claude --max-iterations 8 --plateau 3
EOF
