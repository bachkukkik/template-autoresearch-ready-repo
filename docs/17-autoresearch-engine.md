# 17 — Autoresearch Engine

## What

`engine/autoresearch/` is a generic autoresearch loop: a stdlib-only Python
package (run as `python3 -P -m autoresearch` or the `engine/bin/autoresearch`
wrapper) that can be pointed at **any** git repository. You register a run with
`init` (a verify command that prints the metric, a guard command that must keep
passing, the scope the agent may edit, protected files, a noise floor, repeats),
and `run` then loops: an agent harness proposes an edit, the engine commits it,
runs guard and verify itself, keeps the commit only if the guard passed and the
metric improved beyond the noise floor, and otherwise hard-reverts. `status`
replay-validates the ledger; `report` writes an evidence-linked markdown
summary; `doctor` checks the four harness installations.

The agent is pluggable: `--agent {hermes,claude,opencode,dsh,command,replay}`.
The four harness adapters shell out to the headless invocations each harness
documents; `command` runs any shell command as the proposer; `replay` re-applies
a recorded run offline (`--record` makes a live run replayable). `--dry-run`
validates everything and measures the baseline without calling the agent or
writing an event; a real run is bounded by `--max-iterations` (default 10),
`--plateau`, `--max-wall` and consecutive-crash limits, and stops early on
`--target`.

`contract/examples/ex5-real-oss-speedup/` is the real-world proof: NLTK 3.9.1's
`nltk/metrics/distance.py` vendored verbatim (Apache-2.0, pinned commit
`aca78cb`) as the only editable scope, with `bench.py` (the verify: cold
child-process timing of a fixed seeded workload) and `guard.py` (the guard:
four stages — policy, upstream test cases, a differential oracle against the
pristine module over thousands of randomized inputs, and a public-surface
check — with the candidate isolated in a child process so it can neither exit
the guard early nor patch the comparison functions).

The design is grounded in the 15-system study in
[kb/comparisons/autoresearch-engines-real-world.md](../kb/comparisons/autoresearch-engines-real-world.md)
(script-owned keep/revert, verify + guard, scope + protected files, noise
floor, bounded stops, replay-validated ledger — the mechanics shared by the
systems that report real-code wins) and serves
[docs/prd/17-autoresearch-engine.md](prd/17-autoresearch-engine.md)
(AC-ENG-000..079 unit, AC-ENG-201..203 integration; ex5 AC-EXA-040..050).
Gap [17](gaps/17-loop-cannot-target-real-code.md) is the "why".

## Why

- The template's loop could not be pointed at real code: one hard-wired toy
  metric, keep/discard copy-pasted per example, and the only live example
  pasting whole files over raw HTTP (gap 17).
- The harnesses this host runs — Hermes, Claude Code, opencode, DeepSeek
  Harness — had no channel into the loop at all.
- The KB had never ingested the systems that report real wins (Shopify Liquid
  #2056: 53 % faster with a 974-test guard over ~120 experiments; CORAL; the
  OSS engines), so the template's design predated the evidence.

## How

```bash
# doctor: is every harness installed?
PYTHONPATH=engine python3 -P -m autoresearch doctor

# register a run on any git repo (requires a clean tree on a named branch)
PYTHONPATH=engine python3 -P -m autoresearch init --repo <repo> \
  --verify "<cmd printing METRIC name=value>" --guard "<cmd; exit 0 = pass>" \
  --metric-name <name> --direction {lower,higher} --scope <prefix> \
  [--target X] [--noise-floor REL] [--repeats N] [--protect PATH ...] \
  [--program FILE] [--goal TEXT]

# prove everything without calling the agent (no commits, no events)
PYTHONPATH=engine python3 -P -m autoresearch run --repo <repo> --agent claude --dry-run

# a real, bounded run; stop on target or plateau
PYTHONPATH=engine python3 -P -m autoresearch run --repo <repo> --agent claude \
  --max-iterations 8 --plateau 3 [--record FILE]

# inspect and export
PYTHONPATH=engine python3 -P -m autoresearch status --repo <repo>
PYTHONPATH=engine python3 -P -m autoresearch report --repo <repo>

# the worked example, end to end
bash contract/examples/ex5-real-oss-speedup/setup.sh "$TMPDIR/ex5"
cd "$TMPDIR/ex5"
PYTHONPATH=<repo>/engine python3 -P -m autoresearch run --repo . --agent claude \
  --max-iterations 8 --plateau 3
```

State lives in `<repo>/.autoresearch/` (`run.json`, `events.jsonl`,
`report.md`, `results.tsv`), gitignored wholesale. Exit codes: `0` normal,
`2` config/precondition (including a missing agent binary, which is checked
before the baseline is written), `3` an invalid ledger, `130` Ctrl-C.

## Verification

### Run 2026-10-28 (pre-hardening live evidence, superseded below)

The first end-to-end proof ran on the pre-hardening engine/guard. An
independent post-hoc check (pristine oracle first, candidate in a fresh `python
-I` child, 3 unseen seeds × 24,000 comparisons, cold-process timing including
import) confirmed the Claude Code result was genuine: **0 mismatches, no
missing public functions, 4.07× cold speedup** (1.083 s → 0.266 s). The
review's bypasses (early `SystemExit(0)`, oracle monkeypatching, free
import-time precompute) were real but *not used* by the winning runs. This run
is superseded by the hardened re-run below and is kept only as the triage
evidence that the bypasses existed.

### Run 2026-10-28 (hardened engine + hardened ex5 — the record)

- `python3 -m pytest tests/unit -q` → **334 passed**
- `python3 -m pytest tests/unit/test_engine_*.py tests/integration/test_engine_loop.py -q`
  → 113 passed (engine subset)
- `bash tests/run.sh` → `RESULT: PASSED`; `bash scripts/local-ci.sh` → all five
  gates pass; PR #36 remote CI → 9/9 green (incl. Docker E2E).
- **Hardened-guard live run (claude)**: baseline 0.617 s → 3 keeps to 0.304 s
  (+50.8 %), ledger valid, final guard ok — then Claude Code hit its weekly
  usage limit; the engine recorded each refusal as `agent_error` (the ledger's
  `log_tail` carries the provider message verbatim) and stopped cleanly on
  `max_crashes`. The hardened isolation does not slow real optimization down,
  and a harness outage is a bounded, evidenced stop — not a corrupted run.
- **Pre-hardening live runs** (superseded run below — kept as the
  improvement evidence; each independently confirmed post-hoc): claude
  0.621→0.166 s (3.7×; 4.07× post-hoc), opencode 0.612→0.136 s (4.5×; 4.47×),
  hermes 0.613→0.188 s (3.3×; 2.63×), dsh 0.611→0.135 s (4.5×; 4.06×) —
  every final artifact output-identical on unseen seeds (24,000 comparisons
  each), full public surface intact.

## What Works

- The engine drives all four harnesses on this host, end to end, with valid
  ledgers (each smoke and live run reports `ledger: valid`).
- Real improvement on real code: NLTK's distance metrics made **3.7× faster by
  the engine's own measurement and 4.07× on an independent unseen-seed check**,
  with byte-identical outputs (24,000 comparisons × 3 seeds) and the full
  public surface intact.
- Dry-run proves a configuration (config, git state, protected hashes, adapter
  binary, baseline metric) with zero side effects.
- The guard held against every attack the security review threw at it after
  hardening (AC-EXA-046..048: SystemExit-at-import, oracle monkeypatching,
  public-surface deletion all fail the guard).
- Import time is charged by the bench (AC-EXA-049), so precompute is not free.

## What Fails

- **Only one harness has a hardened-guard live run.** Claude Code hit its
  weekly usage limit mid-run, so the opencode/hermes/dsh hardened re-runs are
  still pending; their pre-hardening results (independently confirmed) stand.
  The attack tests (AC-EXA-046..050) run the hardened guard against every
  known bypass on every host, so the guard's correctness does not depend on
  the number of live runs.
- **Harness quality varies.** Claude Code and opencode found the bit-parallel
  Myers algorithm on their own; DeepSeek reached it in 2 iterations; Hermes
  improved steadily without it in 5. The loop does not equalise model capability.
- **The remaining timing risk is introspection, not isolation.** Code that
  branches on `time.perf_counter` or frame inspection can still game a
  wall-clock bench; the differential oracle on unseen seeds is the backstop
  (documented in ex5's README as residual risk).

## Resolution

- The superseded run's caveats: the first guard shipped with three real
  bypasses (found by the stage-2 review, fixed attack-first in AC-EXA-046..050).
  Any future target must re-run the same attack tests against its own guard.
- If a harness produces a keep that the post-hoc check would reject, the check
  (unseen seeds, pristine-first, isolated child) is the arbitration procedure.
- Harness variance is a property of the models, not the loop: record it, do
  not tune the example to flatter the weakest harness.

## Verdict

**works** — with the scope stated above: the engine runs on four harnesses and
produces verified, evidence-linked improvement on a real OSS workload; the
hardened re-run's per-harness numbers are appended to *Verification* when the
runs complete, and until then the pre-hardening results (independently
confirmed) stand as the improvement evidence.
