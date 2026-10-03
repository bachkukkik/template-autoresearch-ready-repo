# 14 — gen-env Script

## What

`scripts/gen-env.py` regenerates `.env` from `.env.example` line by line, with the exact
comment blocks preserved. `--fresh` writes a byte-identical copy for a new deployment.
`--update` writes `.env.new`, carrying the existing deployment's values key by key into
the verbatim template.

## Why

- `.env.example` evolves with the codebase. A deployed `.env` drifts behind it. Reconciling
  by hand loses the operator-guidance comments.
- The usage contract is: generate for a fresh deployment, and update the new file while
  keeping the existing one for the running deployment. So the tool never touches a live
  `.env`.

## How

Stdlib-only Python 3 (`argparse`, `pathlib`), no subprocess, about 130 lines. Modes per
`docs/prd/14-gen-env-script.md`:

| Mode | Target | Refuses without `--force` when |
|------|--------|-------------------------------|
| `--fresh` | `.env` | `.env` exists |
| `--update` | `.env.new` | `.env.new` exists |

`--update` reads the existing `.env`, maps `KEY` to value (exact key match, everything
after the first `=`, `export ` prefixes ignored), rewrites `.env.example`'s lines with the
carried values, and prints dropped keys **by name only** — values are never echoed. Exit
`0` on success, `1` on usage or environment errors.

## Verification

Run from the repo root, 2026-10-03.

```bash
python3 -m pytest tests/unit/test_gen_env.py -q
# -> 5 passed
python3 -m pytest tests/unit -q
# -> 135 passed

# CLI smoke, in a scratch directory
T=$(mktemp -d); cp .env.example "$T/.env.example"; cd "$T"
python3 /workspace/Archives/template-autoresearch-ready-repo/scripts/gen-env.py --fresh
# -> wrote .env
cmp .env .env.example && echo BYTE-IDENTICAL
# -> BYTE-IDENTICAL
printf '\nLEGACY_VAR=old\nAPP_NAME=prod-frontend\n' >> .env
python3 /workspace/Archives/template-autoresearch-ready-repo/scripts/gen-env.py --update
# -> wrote .env.new
# -> dropped keys (not in .env.example): LEGACY_VAR
grep -c LEGACY_VAR .env.new
# -> 0
```

Expected: `5 passed`; every `--fresh` output byte-identical to `.env.example`; `--update`
carries drifted values, drops `LEGACY_VAR` by name, and leaves the existing `.env` intact.

## What Works

- `--fresh` output is byte-identical to `.env.example` (`cmp` clean) — every comment block
  verbatim.
- `--update` preserves the template's comment lines, carries drifted values
  (`APP_NAME=prod-frontend` in the smoke), and drops `LEGACY_VAR` with a name-only stdout
  report. The dropped key never appears in `.env.new` (`grep -c` returns 0).
- The existing `.env` is untouched by `--update`.
- `--fresh` over an existing `.env` refuses with exit 1 until `--force` is given.
- 5/5 unit tests green. The module imports with no side effects (`if __name__ ==
  "__main__"` guard).

## What Fails

- **No diff preview.** `--update` writes `.env.new` whole. An operator who wants a key-by-key
  diff runs `diff .env .env.new` themselves.
- **Comment-only drift is silent for values.** If a template line's default changed but the
  key exists in `.env`, the carried value hides the new default.
- **Flat key space.** Sections are comments, not parsed structure. Two `KEY=` lines with the
  same name in one file would be last-wins. This is not a real `.env` pattern, so it is
  unguarded.

## Resolution

- **No diff preview:** documented behavior — `diff .env .env.new` is the review step before
  the swap.
- **Comment-only drift:** the operator reads `.env.new` before `mv .env.new .env`. The swap
  is manual by design.
- **Flat key space:** acceptable for `.env` semantics, where duplicate keys are undefined
  behavior anyway. No guard was added.

## Verdict

**works** — Both modes verify end to end against the real `.env.example`: a byte-identical
fresh output, and a value-carrying update with name-only drop reports and an untouched
source `.env`. Five hermetic unit tests guard it in the CI `unit` job.
