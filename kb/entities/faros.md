---
title: FAROS
created: 2026-10-28
updated: 2026-10-28
type: entity
tags: [autoresearch, architecture]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: medium
---

# FAROS

`OpenNSWM-Lab/FAROS` — a research-automation platform (FastAPI backend + Next.js UI) that
turns a research goal into a plan, generates up to three candidate unified-diff patches per
round, scores them with static + dynamic evaluation plus an LLM ranking, and requires human
approval of revisions. MIT, pinned at `60ce4bc235f169d71f2d11dbe37445b4e402b528` (~3.0k stars).
^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## Key facts

- **It is generate-and-rank, not a loop.** `CodeSessionConfig.maxIterations = 3` is serialised
  into the session config and `pipeline_runner.py::run()` is a single linear pass (search →
  summarise → gap analysis → candidate generation → ranking → completed) that never reads it.
  A ceiling that is declared but unenforced is worse than none, because operators budget
  against it.
- **Two scoring layers, neither a verify command.** (1) An LLM ranker scores up to three
  patches on correctness 0.30 / completeness 0.25 / efficiency 0.15 / readability 0.15 / safety
  0.15 and the top one is applied. (2) `EvalScorer.WEIGHTS` = syntax 0.30 / risks 0.20 / lint
  0.10 / tests 0.40 → a 0–100 score plus an A–F grade, with `DynamicEvaluator` detecting the
  project's test runner, running it once with a 60 s timeout and regex-scraping pass/fail/skip.
  Nothing re-verifies that the winning patch caused the score change.
- **No git keep/revert.** `backend/app/code/run/workspace.py::_copy_repo` copies the repository
  and `apply_patch` applies the winning diff into the copy, so the live tree is never mutated
  and a rejected candidate is simply a diff that was never applied. Blast radius is bounded by
  the copy; there is no per-path allowlist inside it.
- **`execution_gate()`** in `backend/app/modules/code/execution_assessment.py` is the only
  preflight: code runs only when its execution class is computational or simulation ready,
  status is ready and no inputs are missing — an eligibility gate, not a correctness gate.
- **One real harness.** `backend/app/services/claude_agent.py` builds
  `claude -p <prompt> --output-format stream-json --verbose --model <model> --allowedTools
  "Bash,Read,Write,Edit,Glob,Grep" --add-dir <workspace> --max-budget-usd 10.0
  --dangerously-skip-permissions [--resume <sid>]` with a 900 s timeout and the prompt truncated
  to 4000 characters. The fallback is a generic OpenAI-compatible chat provider — text only, no
  tool use, so it cannot run a code-change loop. See [[headless-harness-invocation]].
- **`CodeSession` is the ledger**: one JSON blob per session with an append-only `trace` of
  `{step, status, timestamp, durationMs, inputs, outputs, error}` inside a document rewritten in
  place. `from_dict` round-trips but no code path calls `storage.load`, so a re-run starts at
  search rather than resuming.

## Evidence

The only numbers are an offline NLP benchmark, not a code-improvement result: on SciFact dev
(339 claim–evidence pairs) ReviewX reaches F1 **0.7746** vs 0.7460 for a lexical baseline and
calibration ECE 0.0345 vs 0.0819 — **every 95% bootstrap CI crosses zero**, as the authors
acknowledge. No before/after on a live repository, no merged PR, no user study. Treat FAROS as
an architecture reference, not as evidence that the loop improves real code.

## What is worth taking

- **A claim→evidence audit of the report**: every claimed improvement must link a ledger row
  plus the exact verify command and its output, else it is downgraded to
  `needs_human_verification`. Cheap, and it is the only anti-hallucination gate on the artifact
  a human actually reads.
- **Structured revision records** `{target_field, old_value, new_value, rationale, evidence}` as
  the unit of human feedback, replayable into the proposer prompt.
- **Multi-dimension scoring with explicit risk/lint weights** so passing tests alone cannot max
  the score — the opposite of a single-metric gate, and a model for a `report` breakdown.
- **N-candidate fan-out with ranking** as an alternative to strict keep/revert when patches are
  large.

## What not to take

An LLM ranker called a verifier; `maxIterations` as a knob without a decrement; a declared
budget in place of an enforced one; `--dangerously-skip-permissions` inside a copied workspace
as the isolation story (a file copy protects the source tree, not the host); a single 60 s test
run as a score; a DB-backed session model when `run --resume` is a requirement.

## Relations

- The generate-and-rank counter-example in [[autoresearch-engines-real-world]]; contrast
  [[coral]], which loops and reverts.
- Its ranker/verifier confusion is the case study behind [[verify-guard-contract]]'s
  "an LLM ranker is not a verifier" rule and [[evaluator-legitimacy]].

## Related

- [[autoresearch-engines-real-world]] · [[verify-guard-contract]] ·
  [[reward-hacking-countermeasures]] · [[evaluator-legitimacy]] · [[coral]]
