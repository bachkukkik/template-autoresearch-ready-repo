---
title: Script-Owned Keep/Revert
created: 2026-10-28
updated: 2026-10-28
type: concept
tags: [autoresearch, architecture]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: high
---

# Script-Owned Keep/Revert

**The control script — not the agent — commits, measures and reverts.** The agent's only
write is the edit itself; its only calls are the script's verbs. This is the single
structural difference between the engines that survive scale and the ones that silently
corrupt themselves. ^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## Three owners, observed

| Owner | Systems | What goes wrong |
|-------|---------|-----------------|
| **Script / engine** | leo-lilinxiao, evo, steer, GEPA (file promotion), FAROS (copy + patch), research-loop (no revert at all) | costs infrastructure (worktrees, patches, daemons) |
| **The agent** | karpathy, CORAL, pi-autoresearch, autokernel, uditgoenka | the failure is invisible until the ledger is wrong |
| **Nobody** | goal-md, Thoth, aideml | "keep or revert" is prose; two runs produce different on-disk outcomes |

Each agent-owned system states the cost about itself. autokernel: "the engine should own the
revert via a worktree or a captured patch, otherwise the ledger cannot prove what was
undone". CORAL: `git reset --hard HEAD~1` "only works while the agent's decision matches the
tip, so a wrong revert discards a good commit", and an agent that forgets to revert keeps a
regression that the engine records but does not undo. pi-autoresearch: an agent-authored
commit has no allow-list and no message policy, and `git add -A` sweeps unrelated files that
`checkout -- .` cannot distinguish. karpathy: `git reset --hard` discards uncommitted work,
and a mis-grep silently records a wrong metric.

## Trial mechanics, cheapest first

1. **Throwaway worktree per attempt** — research-loop creates
   `autoresearch/<campaign>/<experiment>` in an external worktree so the base checkout is
   never edited and *nothing is ever reverted*; CORAL grades in a detached worktree so a score
   is computed on an immutable commit rather than a dirty tree.
2. **Uncommitted trial with a captured patch** — evo writes `diff.patch` per attempt, runs the
   benchmark, and restores the parent itself; a revert is "discard attempt N", not a git verb.
3. **Copy-of-repo + `apply_patch`** — FAROS never mutates the live tree, so there is nothing to
   revert; a rejected candidate is a diff that is simply never applied.
4. **Commit-then-revert** — leo-lilinxiao, uditgoenka, pi. Doubles commit volume and forces
   history rewriting on every discard; leo-lilinxiao's own anti-pattern list names this against
   itself.

The engine must be able to revert **by attempt id**. Every mechanism that reverts by position
(`HEAD~1`) depends on the tip being the attempt under judgement — which is exactly the
assumption an interrupted or parallel run breaks.

## Scope: three grades of enforcement

- **Allowlist + protected prefixes, diff-checked by the script.** leo-lilinxiao
  (`core.py:768-812`): repo-relative paths, globs rejected, `..` and absolute paths rejected,
  and `autoresearch-results`, `.git`, `.agents/skills/codex-autoresearch` refused outright.
  research-loop: `git diff --name-only parent..HEAD` must be non-empty, contain no
  `protected_paths`, and every path must sit inside `allowed_paths`. steer's structural
  equivalent: the whole `contract/` directory is frozen and read-only, so the measurement
  cannot be edited at all.
- **Frozen evaluator + convention.** karpathy's `prepare.py` is off-limits by instruction;
  autokernel's guard is a script living in the same repo the agent edits, with no checksum and
  no read-only mount.
- **None.** pi guards only the benchmark file; CORAL has "no per-path allowlist"; aideml has
  "no allowed-path list, no write guard".

## The ledger the script writes

Event-sourced and **validated on read** is the strongest form. leo-lilinxiao's
`events.jsonl`: an exact per-event field set for baseline / iteration / blocked / complete /
error / resumed / stopped; duplicate keys, NaN/Infinity, unknown types, missing fields and a
non-contiguous `seq` all fail loudly; `derive_state` then re-checks semantics on replay (a
keep must be a genuine improvement with a passing guard and `head == trial_commit`; a discard
must point at its revert commit; a `complete` must satisfy the target). Because of that,
`status`, `history`, `report` and `resume` are pure functions of one append-only file.

The weak form is a write-only log: goal-md's `iterations.jsonl` has no reader, aideml rewrites
`journal.json` every step but always starts a fresh Journal, karpathy's `results.tsv` has no
validation at all — a hallucinated row is indistinguishable from a real one.

## Contract for a generic engine

`init` creates the run directory and freezes `run.json`; `run` performs edit → commit trial →
verify → guard → keep-or-revert, all in the engine process; `revert <attempt-id>` is a verb;
`status` derives from the event log; `resume` replays it. The agent is given exactly two
verbs (`edit`, `finish`) and never `git`. Identity between the recorded commit and the
measured tree is mandatory — leo-lilinxiao measures *after* the commit for this reason.

## Related

- [[verify-guard-contract]] — what the script runs and what it may believe.
- [[deterministic-keep-gate]] — the decision the script computes.
- [[loop-stop-conditions]] — the script also owns the stop policy.
- [[harness-portability]] — why the vendor's flags belong in an adapter, not the loop.
- [[autoresearch-engines-real-world]] — the 15-system evidence.
