---
title: CORAL
created: 2026-10-28
updated: 2026-10-28
type: entity
tags: [autoresearch, architecture]
sources: [raw/articles/2026-10-28-autoresearch-real-world-engines.md]
confidence: medium
---

# CORAL

`Human-Agent-Society/CORAL` — a multi-agent research harness (COLM 2026, arXiv 2604.01658)
where N coding-agent CLIs, each in its own git worktree, run a real edit/commit loop against a
task repository while an out-of-process **grader daemon** scores every committed attempt.
Apache-2.0, pinned at `0123dfb939b35228cf2c1fde224cd0561e727408` (~1.1k stars).
^[raw/articles/2026-10-28-autoresearch-real-world-engines.md]

## Key facts

- **Four built-in harness adapters** — Claude Code, opencode, Codex and the DeepSeek Harness
  (`dsh`) under `coral/agent/builtin/`. This is the widest adapter surface in the corpus and
  the only `dsh` invocation documented anywhere: `dsh --profile headless [--patch <p>]…
  --patch .dsh/coral-model.patch.yml <prompt>`. See [[headless-harness-invocation]].
- **Public/private state split** — `.coral/public` (attempts, notes, skills, agent defs) is
  symlinked into every worktree; `.coral/private` (grader virtualenv, hidden data, deny rules)
  is not readable, and in docker mode the agent runs as an unprivileged user, so the split is
  enforced by the OS rather than by path convention.
- **Out-of-process grading** — `coral eval -m <msg>` stages and commits the tree, writes a
  pending attempt, and polls; `coral/grader/daemon.py` checks each attempt out into a detached
  worktree under `.coral/private/grader_checkouts`, runs the task grader with a 300 s timeout,
  and writes a `ScoreBundle` atomically (tmp + rename). `grader.max_pending_per_agent = 1`
  bounds queue depth, so score attribution is never ambiguous.
- **Keep/revert is agent-driven** — `coral revert` is literally `git reset --hard HEAD~1` and
  `coral checkout <hash>` moves to an earlier commit; the engine records the attempt history
  but does not undo a worse score. This is the design's weak point, not its strength; see
  [[script-owned-keep-revert]].
- **Stops in code** — `run.stop.max_real_attempts`, `run.stop.score_threshold`,
  `grader.timeout = 300`, `grader.max_pending_per_agent = 1`. Plateau lives in the heartbeat:
  `coral/agent/heartbeat.py::streak_for_epsilon` counts sub-epsilon attempts and escalates the
  prompt reflect → consolidate → pivot. No hard plateau stop.
- **No noise handling** — each attempt is graded once, so grader stochasticity lands directly
  in the keep decision.

## Evidence

- Kernel `kernel_builder`: 1363 → 1350 cycles with one agent in 4.6 h, then 1363 → **1103**
  with four agents in ~4.5 h. The single agent had plateaued; the fan-out had not. This is the
  strongest signal in the corpus and it is about *parallelism as a plateau breaker*, not about
  per-agent quality.
- Erdős minimum-overlap C5: 0.38089 vs AlphaEvolve's 0.38092 — 99% of SOTA in 34 min vs 5.2 h.
- OpenVaccine RNA degradation: **+20.5%** over the top human leaderboard entry within 2
  evaluations.

All three are author-reported. CORAL's own limits: docker-in-docker is unsupported (the
strongest isolation needs a host socket), one commit per attempt pollutes history, and
one-shot grading inherits grader noise.

## Relations

- The multi-agent / public-private reference design in
  [[autoresearch-engines-real-world]]; contrasted with [[faros]], which ranks instead of
  looping.
- Its heartbeat escalation is the model for a `--plateau N --epsilon X` stop →
  [[loop-stop-conditions]].
- Its `.coral/private` denial is one of the strongest anti-hack mechanisms in the set →
  [[reward-hacking-countermeasures]].

## Related

- [[autoresearch-engines-real-world]] · [[script-owned-keep-revert]] ·
  [[headless-harness-invocation]] · [[loop-stop-conditions]] · [[autoresearch-contract]]
