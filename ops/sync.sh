#!/usr/bin/env bash
# ops/sync.sh — sync the repo's vendored ops artifacts to the live deploy target.
#
#   ops/sync.sh --check [--repo <dir>] [--live <dir>]   # read-only drift report
#   ops/sync.sh --apply [--repo <dir>] [--live <dir>]   # write the live target (gated)
#
# The repo is canonical; the live side is a copy. See ops/README.md for the
# repo-path <-> deploy-path map and the artifact/runtime-state classification.
#
# Env fallbacks (a flag wins over its env var; an env var wins over the default):
#   OPS_REPO_ROOT      default: the parent directory of this script's directory
#   OPS_LIVE_ROOT      default: $HOME/.local/share/autoresearch-ops
#   OPS_ARTIFACT_DIR   default: $OPS_REPO_ROOT/ops/artifacts
#   OPS_ALLOWLIST      default: $OPS_REPO_ROOT/ops/state-allowlist.txt
#   OPS_APPLY_CONFIRM  must be 1, else --apply refuses to write anything
set -euo pipefail

usage() {
  cat <<'EOF'
usage: ops/sync.sh --check [--repo <dir>] [--live <dir>]
       ops/sync.sh --apply [--repo <dir>] [--live <dir>]

  --check   read-only drift report. Exit 0 when repo and live agree, non-zero on
            drift. Never writes anything, so it is safe to run anywhere (CI included).
  --apply   copy the vendored artifacts into the live root. Refuses unless
            OPS_APPLY_CONFIRM=1.
  --repo    repo root containing ops/            (env OPS_REPO_ROOT)
  --live    live deploy target root             (env OPS_LIVE_ROOT)

Env-only knobs: OPS_ARTIFACT_DIR (default <repo>/ops/artifacts),
OPS_ALLOWLIST (default <repo>/ops/state-allowlist.txt).
EOF
}

MODE=""
REPO_ROOT="${OPS_REPO_ROOT:-}"
LIVE_ROOT="${OPS_LIVE_ROOT:-}"
ARTIFACT_DIR="${OPS_ARTIFACT_DIR:-}"
ALLOWLIST="${OPS_ALLOWLIST:-}"
ARTIFACTS=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --apply) MODE=apply ;;
    --repo)  REPO_ROOT="${2:?--repo needs a directory}"; shift ;;
    --live)  LIVE_ROOT="${2:?--live needs a directory}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ops/sync.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ -z "$MODE" ]; then
  echo "ops/sync.sh: exactly one of --check or --apply is required." >&2
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# Resolution order: an explicit flag (parsed above) > its env var (read at the top) > the
# default here. The default repo root is this script's parent — ops/ lives in the repo.
[ -n "$REPO_ROOT" ] || REPO_ROOT="$(dirname -- "$SCRIPT_DIR")"
[ -n "$ARTIFACT_DIR" ] || ARTIFACT_DIR="$REPO_ROOT/ops/artifacts"
[ -n "$ALLOWLIST" ] || ALLOWLIST="$REPO_ROOT/ops/state-allowlist.txt"
# Placeholder default — a real project sets OPS_LIVE_ROOT to the directory the live
# process actually reads. Documented in the header and in ops/README.md.
[ -n "$LIVE_ROOT" ] || LIVE_ROOT="${HOME}/.local/share/autoresearch-ops"

# A run must be self-describing: print the resolution actually used, in both modes.
print_resolution() {
  echo "mode         : $MODE"
  echo "repo root    : $REPO_ROOT"
  echo "artifact dir : $ARTIFACT_DIR"
  echo "live root    : $LIVE_ROOT"
  if [ -f "$ALLOWLIST" ]; then
    echo "allowlist    : $ALLOWLIST"
  else
    echo "allowlist    : $ALLOWLIST (absent — no runtime-state excuse in force)"
  fi
}

# Runtime state is excluded in BOTH directions (README contract rule 3). Patterns are
# matched against the path relative to the deploy root; '#' starts a comment.
# shellcheck disable=SC2254  # the pattern is deliberately a glob, not a literal
allowlisted() {
  local rel="$1" line pat
  [ -f "$ALLOWLIST" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    pat="${line%%#*}"
    pat="${pat#"${pat%%[![:space:]]*}"}"   # strip leading whitespace
    pat="${pat%"${pat##*[![:space:]]}"}"   # strip trailing whitespace
    [ -n "$pat" ] || continue
    case "$rel" in $pat) return 0 ;; esac
  done < "$ALLOWLIST"
  return 1
}

# LOUD ENUMERATION. An absent, unenumerable or empty artifact root is an error, never a
# quiet "nothing to do". Failure class we are guarding: a green success line printed
# over a copy that deployed nothing — the run looks clean and the deploy target stays
# empty. Keep this guard in front of both modes.
enumerate_artifacts() {
  if [ ! -d "$ARTIFACT_DIR" ]; then
    echo "ERROR: artifact root '$ARTIFACT_DIR' is absent or not a directory." >&2
    echo "       Nothing is vendored, so there is nothing to report or deploy." >&2
    exit 1
  fi
  if ! ARTIFACTS="$(cd -- "$ARTIFACT_DIR" && find . -type f -print | sed 's|^\./||' | LC_ALL=C sort)"; then
    echo "ERROR: artifact root '$ARTIFACT_DIR' could not be enumerated." >&2
    exit 1
  fi
  if [ -z "$ARTIFACTS" ]; then
    echo "ERROR: artifact root '$ARTIFACT_DIR' resolves to zero files." >&2
    echo "       An empty artifact root is a broken vendoring, not a clean sync." >&2
    exit 1
  fi
}

cmd_check() {
  local drift=0 rel live live_files=""
  enumerate_artifacts   # absent/unenumerable/empty artifact root is an error, not "no drift"
  declare -A vendored=()
  while IFS= read -r rel; do vendored["$rel"]=1; done <<< "$ARTIFACTS"

  if [ ! -d "$LIVE_ROOT" ]; then
    echo "DRIFT live root '$LIVE_ROOT' is absent — nothing has been deployed."
    drift=1
  fi

  # Direction (a): vendored artifacts absent from live, or differing in content.
  while IFS= read -r rel; do
    if allowlisted "$rel"; then
      echo "DRIFT $rel — vendored copy matches the runtime-state allowlist."
      echo "      It is generated state owned by the live side; unvendor it (README rule 3)."
      drift=1
      continue
    fi
    live="$LIVE_ROOT/$rel"
    if [ ! -e "$live" ]; then
      echo "DRIFT $rel — vendored but absent live ($live)"
      drift=1
    elif ! cmp -s -- "$ARTIFACT_DIR/$rel" "$live"; then
      echo "DRIFT $rel — vendored and live differ in content"
      drift=1
    fi
  done <<< "$ARTIFACTS"

  # Direction (b): files that exist live with no vendored counterpart. Generated runtime
  # state is excused by the path-scoped allowlist; anything else is unattributed config.
  if [ -d "$LIVE_ROOT" ]; then
    # Trailing slash: follow a SYMLINKED deploy root instead of reporting the link itself.
    if ! live_files="$(cd -- "$LIVE_ROOT/" && find . -type f -print | sed 's|^\./||' | LC_ALL=C sort)"; then
      echo "ERROR: live root '$LIVE_ROOT' could not be enumerated." >&2
      exit 1
    fi
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      [ -z "${vendored[$rel]:-}" ] || continue
      if allowlisted "$rel"; then
        continue   # generated runtime state — the live side owns it (README rule 3)
      fi
      echo "DRIFT $rel — exists live with no vendored counterpart"
      drift=1
    done <<< "$live_files"
  fi

  if [ "$drift" -ne 0 ]; then
    echo "== drift detected =="
    echo "Re-vendor the live side into ops/artifacts/ (README rule 4) and re-run --check."
    exit 1
  fi
  echo "== in sync, no drift =="
  exit 0
}

cmd_apply() {
  local rel count=0 dest

  if [ "${OPS_APPLY_CONFIRM:-0}" != "1" ]; then
    echo "ERROR: --apply writes to the live deploy target '$LIVE_ROOT' and is gated." >&2
    echo "       Re-run with OPS_APPLY_CONFIRM=1 once you have reviewed '--check'." >&2
    exit 1
  fi

  if [ ! -d "$LIVE_ROOT" ]; then
    echo "ERROR: live root '$LIVE_ROOT' is absent — the deploy target must exist." >&2
    echo "       Refusing to create it: a mistyped --live path would deploy into the void." >&2
    exit 1
  fi

  enumerate_artifacts   # nothing to deploy is an error, never a quiet success

  # Pre-flight: refuse a vendored copy that is really generated runtime state. Copying it
  # would overwrite live state (which the live side owns) with a stale snapshot — the
  # exact clobber that --check flags. Nothing is written until every file passes.
  while IFS= read -r rel; do
    if allowlisted "$rel"; then
      echo "ERROR: vendored artifact '$rel' matches the runtime-state allowlist in" >&2
      echo "       '$ALLOWLIST'. It is generated state; --apply would clobber live" >&2
      echo "       state with a stale copy. Refusing to write anything." >&2
      exit 1
    fi
  done <<< "$ARTIFACTS"

  # Copies go THROUGH a symlinked deploy root: the path is used as given, never
  # resolved to its target, so the link is the deploy path, not an obstacle.
  while IFS= read -r rel; do
    dest="$LIVE_ROOT/$rel"
    mkdir -p -- "$(dirname -- "$dest")"
    cp -p -- "$ARTIFACT_DIR/$rel" "$dest"   # byte-copy; -p keeps a wrapper executable
    count=$((count + 1))
  done <<< "$ARTIFACTS"

  # The success line is unreachable over a no-op copy. enumerate_artifacts already
  # refuses an empty root; this count is the second belt on the same failure class
  # (a green "sync complete" over a deploy that shipped zero files). Never print
  # success over an error.
  if [ "$count" -eq 0 ]; then
    echo "ERROR: zero artifacts deployed — refusing to print success." >&2
    exit 1
  fi
  echo "deployed $count artifact(s) to $LIVE_ROOT"
  echo "== sync complete =="
}

print_resolution
case "$MODE" in
  check) cmd_check ;;
  apply) cmd_apply ;;
esac
