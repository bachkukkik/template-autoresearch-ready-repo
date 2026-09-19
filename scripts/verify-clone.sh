#!/usr/bin/env bash
#
# verify-clone.sh — prove a fresh clone of this template is healthy. READ-ONLY.
#
#   bash scripts/verify-clone.sh
#
# Exit 0 = every check passed. Exit 1 = at least one check failed, and each failure is
# named with the fix. The script writes NOTHING — no files, no git index, no git config
# — so it is safe on a fresh clone, on a deploy host, and in CI. Checks 1-3 mirror the
# 'doctrine' job in .github/workflows/ci.yml, so a clone that passes here is a clone
# that job accepts.
#
# Reading the output: one PASS/FAIL line per check, indented lines are detail, the last
# line is the verdict. Read it top to bottom; the first FAIL is the one to fix first.
#
# LOUD BY CONSTRUCTION (the same principle as ops/sync.sh, AGENTS.md §6 *Ops artifacts*):
# $checks_run counts the checks this script actually performed, and the success line is
# reachable ONLY when that count is greater than zero AND nothing failed. A run that
# performed no checks — a bad parse, a loop that got skipped, someone's early 'exit 0' —
# must never print success. Do not simplify that guard away: a health check that
# reports health it never verified is worse than no health check at all.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CI=".github/workflows/ci.yml"
DOCTRINE_PATHS="AGENTS.md PRD.md README.md ADOPTING.md .agents .github docs kb tests ops scripts"
HARNESS_LINKS="CLAUDE.md .github/copilot-instructions.md .claude/skills .claude/plugins"

checks_run=0
failures=0

say() { printf '      %s\n' "$1"; }
pass() { printf 'PASS  %s\n' "$1"; }
fail() {
  printf 'FAIL  %s\n' "$1"
  failures=$((failures + 1))
}

# The tracked-root list in ci.yml, parsed TOLERANTLY — a sibling change to that file
# must not make this check unfalsifiable, and a list this script cannot find must fail
# loudly rather than silently pass. Three shapes are accepted; empty output = not found.
# A candidate containing '$' or '(' is a variable reference or a command substitution,
# not a literal list, and is rejected.
declared_roots() {
  local raw
  # Shape 1 — shell array:  VAR=(a b c)
  raw="$(grep -oE '^[[:space:]]*[A-Za-z_]*(ROOTS|PATHS)[[:space:]]*=[[:space:]]*\([^)]*\)' "$CI" 2>/dev/null | head -n1 || true)"
  if [ -n "$raw" ]; then
    printf '%s' "$raw" | sed -E 's/^[[:space:]]*[A-Za-z_]*(ROOTS|PATHS)[[:space:]]*=[[:space:]]*\(//; s/\)[[:space:]]*$//'
    return 0
  fi
  # Shape 2 — assignment or YAML env key holding a quoted literal list:  VAR="a b c" / VAR: "a b c"
  raw="$(grep -oE '^[[:space:]]*[A-Za-z_]*(ROOTS|PATHS)[[:space:]]*[=:][[:space:]]*"[^"]*"' "$CI" 2>/dev/null | head -n1 || true)"
  if [ -n "$raw" ]; then
    printf '%s' "$raw" | sed -E 's/^[[:space:]]*[A-Za-z_]*(ROOTS|PATHS)[[:space:]]*[=:][[:space:]]*"//; s/"$//'
    return 0
  fi
  # Shape 3 — a literal loop:  for path in a b c; do
  raw="$(grep -oE 'for path in [^$;]*;?[[:space:]]*do' "$CI" 2>/dev/null | head -n1 || true)"
  if [ -n "$raw" ]; then
    printf '%s' "$raw" | sed -E 's/^for path in //; s/;?[[:space:]]*do$//'
    return 0
  fi
  return 0
}

echo "verify-clone.sh v1 — read-only health check for a fresh clone"
echo "  repo root : $ROOT"
echo "  read it   : one PASS/FAIL line per check; indented lines are detail"
echo "  writes    : nothing (no files, no index, no git config)"
echo

# ── 1. every harness entry point is a RESOLVING symlink (doctrine job, step 1) ───────
# A plain copy forks AGENTS.md silently; a dangling link breaks the harness on a fresh
# clone while still looking committed. Both are invisible until an agent reads a stale
# instruction file, which is why this is check 1.
bad=0
links_ok=0
for link in $HARNESS_LINKS; do
  checks_run=$((checks_run + 1))
  if [ ! -L "$link" ]; then
    say "$link is not a symlink — it is a plain copy and will fork from AGENTS.md"
    say "  fix: git config core.symlinks true && git checkout -- $link"
    bad=1
  elif [ ! -e "$link" ]; then
    say "$link is a dangling symlink -> $(readlink "$link") (target missing or gitignored)"
    say "  fix: git config core.symlinks true && git checkout -- $link"
    bad=1
  else
    links_ok=$((links_ok + 1))
  fi
done
if [ "$bad" -eq 0 ]; then
  pass "$links_ok harness entry point(s) are resolving symlinks"
else
  fail "harness entry points are not all resolving symlinks (hint: git config core.symlinks true)"
fi

# ── 2. the doctrine paths are tracked and not gitignored (funnel rule 10) ────────────
bad=0
tracked=0
pending=""
for path in $DOCTRINE_PATHS; do
  checks_run=$((checks_run + 1))
  if git check-ignore -q "$path"; then
    say "$path is matched by a .gitignore rule — remove the ignore (funnel rule 10)"
    bad=1
  elif git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
    tracked=$((tracked + 1))
  elif [ -e "$path" ]; then
    pending="$pending $path"
  else
    say "$path is missing from the worktree and is not tracked"
    bad=1
  fi
done
if [ "$bad" -ne 0 ]; then
  fail "doctrine paths are tracked and not gitignored"
elif [ -n "$pending" ]; then
  # A fresh clone has every one of these tracked. A path present but uncommitted is a
  # file this working tree has not committed YET: named rather than failed, because
  # this script has to be runnable mid-change. The 'doctrine' job is the strict version
  # of this check — commit these before opening a PR.
  pass "doctrine paths tracked and not gitignored ($tracked committed; not yet committed:$pending)"
else
  pass "doctrine paths tracked and not gitignored ($tracked paths)"
fi

# ── 3. every tracked top-level directory is declared in the doctrine job's list ──────
# The list only knows the roots someone typed into it, so it fails silently WIDE: a new
# tracked root nobody declared passes CI green because the guard never reports a root it
# does not know about. Derive the real set from the index instead (funnel rule 11).
declared="$(declared_roots)"
if [ -z "$declared" ]; then
  say "no tracked-root list found in $CI — looked for:"
  say "  VAR=(a b c)  |  VAR=\"a b c\" or VAR: \"a b c\" (VAR ends in ROOTS or PATHS)  |  for path in a b c; do"
  fail "tracked-root coverage — the list could not be located"
else
  derived="$(git ls-files | awk -F/ 'NF>1 {print $1}' | sort -u)"
  bad=0
  roots=0
  missing=""
  for dir in $derived; do
    roots=$((roots + 1))
    checks_run=$((checks_run + 1))
    case " $declared " in
      *" $dir "*) ;;
      *)
        missing="$missing $dir"
        bad=1
        ;;
    esac
  done
  if [ "$roots" -eq 0 ]; then
    # Never pass vacuously: zero derived roots means the enumeration failed, not that
    # the repo is clean.
    say "git ls-files enumerated no tracked top-level directory — refusing to pass vacuously"
    fail "tracked-root coverage (nothing enumerated)"
  elif [ "$bad" -ne 0 ]; then
    for m in $missing; do
      say "$m is a tracked top-level directory missing from the list in $CI — add it there AND to AC-FUN-002 (funnel rule 11)"
    done
    fail "tracked-root coverage ($roots derived, list incomplete)"
  else
    pass "tracked-root coverage — $roots tracked top-level directory(ies), all declared"
  fi
fi

# ── 4. credential homes: the example ships, a real file cannot be committed ──────────
bad=0
checks_run=$((checks_run + 1))
if [ ! -f .credentials/example.json.example ]; then
  say ".credentials/example.json.example is missing — a fresh clone must ship the example shape"
  bad=1
elif git check-ignore -q .credentials/example.json.example; then
  say ".credentials/example.json.example is gitignored — un-ignore the *.example shape (funnel rule 9)"
  bad=1
fi
checks_run=$((checks_run + 1))
if ! git check-ignore -q .credentials/live-service-account.json; then
  say ".credentials/live-service-account.json is NOT gitignored — a real key file could be committed"
  bad=1
fi
if [ "$bad" -eq 0 ]; then
  pass "credential homes — .credentials/ example tracked, live files ignored"
else
  fail "credential homes"
fi

# ── 5. the graphify ignore holds BY RULE, not by an enumerated list ──────────────────
# One run writes a root marker, detect/chunk files and caches; a version bump adds more,
# so the ignore is graphify-out/*. These three representative artifacts stand for the
# class — if the rule is intact they are all covered.
bad=0
checks_run=$((checks_run + 1))
for artifact in graphify-out/.graphify_root graphify-out/.graphify_detect.json graphify-out/.graphify_chunk_01.json; do
  if ! git check-ignore -q "$artifact"; then
    say "$artifact is NOT gitignored — restore the graphify-out/* rule (AGENTS.md *graphify*)"
    bad=1
  fi
done
if [ "$bad" -eq 0 ]; then
  pass "graphify artifacts ignored by rule (graphify-out/*)"
else
  fail "graphify ignore-by-rule"
fi

# ── 6. python3 and the test runner are present; hand over the next command ───────────
bad=0
checks_run=$((checks_run + 1))
if ! command -v python3 >/dev/null 2>&1; then
  say "python3 is not on PATH — tests/run.sh, contract/ and service/ all need it"
  bad=1
fi
checks_run=$((checks_run + 1))
if [ ! -f tests/run.sh ]; then
  say "tests/run.sh is missing — the three-tier runner is part of the doctrine"
  bad=1
fi
if [ "$bad" -eq 0 ]; then
  pass "python3 and tests/run.sh are present"
  say "next: bash tests/run.sh --with-e2e"
else
  fail "toolchain / test runner"
fi

echo
if [ "$failures" -ne 0 ]; then
  echo "RESULT: FAILED — $failures check(s) failed"
  exit 1
fi
if [ "$checks_run" -eq 0 ]; then
  # Unreachable while the checks above run, and that is the point: the success line
  # must be unreachable over a run that verified nothing.
  echo "RESULT: FAILED — no checks were performed; refusing to report success"
  exit 1
fi
echo "RESULT: PASSED — $checks_run check(s) passed"
