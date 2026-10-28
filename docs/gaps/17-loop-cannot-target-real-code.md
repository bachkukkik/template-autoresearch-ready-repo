# 17 — The loop described by the docs cannot be pointed at real code

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-10-28

## Observation

Every doc that describes the loop (PRD-02, PRD-11, README) describes a
fixed-evaluator loop for one toy metric (`val_bpb` on a stdlib bigram) and
worked examples that each re-implement keep/discard in their own driver. The
only live example (ex4) drives a raw chat-completions endpoint, not an agent
harness, and its recorded run is 1 keep / 1 discard / 3 unusable out of 5 rounds.

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/02-autoresearch-contract.md`, `docs/prd/11-worked-examples.md` | the contract is program/prepare/train; the examples prove it works |
| B | `contract/`, `contract/examples/` at `afcab6c` | one hard-wired metric; keep/discard copy-pasted per example; no engine; no harness adapter; no real-code target |

## Evidence

- `contract/prepare.py` defines `TIME_BUDGET`, `evaluate_bpb`, `decide` —
  specific to one metric and one dataset; `contract/train.py` is the only
  editable artifact.
- Each of `contract/examples/ex1..ex4` ships its own `loop_driver.py` /
  `agent_driver.py` with a private copy of the keep/discard logic
  (four implementations of the same gate).
- `contract/examples/ex4-llm-repo-speedup/results.tsv` (vendored): 5 rounds —
  1 keep, 1 discard, 3 `crash` rows "unusable response (no fenced code block)";
  the driver posts raw JSON to a chat-completions endpoint
  (`agent_driver.py`, `call_model`), it does not drive a harness.
- No file under `engine/` existed before this gap opened; no adapter for
  Hermes / Claude Code / opencode / DeepSeek Harness existed anywhere.
- Grounding for the fix: the 15-system study
  [kb/raw/articles/2026-10-28-autoresearch-real-world-engines.md](../../kb/raw/articles/2026-10-28-autoresearch-real-world-engines.md)
  and its synthesis
  [kb/comparisons/autoresearch-engines-real-world.md](../../kb/comparisons/autoresearch-engines-real-world.md).

## Impact

The template cannot do what its name promises: an adopter cannot point the
loop at their own repository, on any harness, and get a measured, guarded
improvement in real code. "Code seems to work but fails to achieve meaningful
improvement in real-world application" (the triage report that opened this
gap) is a direct consequence.

## Resolution

Closed by PRD-17 (`docs/prd/17-autoresearch-engine.md`): the `engine/` package
(init/run/status/report/doctor; script-owned keep/revert; verify/guard/scope/
protected files; noise floor; bounded stops; `--dry-run`; `--record`/replay;
adapters for Hermes, Claude Code, opencode, DeepSeek Harness) and the real-OSS
target ex5 (NLTK 3.9.1 `distance.py` under a four-stage isolated guard).
Implementation and live-run evidence: `docs/17-autoresearch-engine.md`.
