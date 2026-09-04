---
title: Autoresearch Video Corpus
created: 2026-09-04
updated: 2026-09-04
type: comparison
tags: [example, autoresearch]
sources:
  - raw/transcripts/-Ip9EtoBjbk.txt
  - raw/transcripts/bMoNOb0iXpA.txt
  - raw/transcripts/jCNeVZJAYGM.txt
  - raw/transcripts/uBWuKh1nZ2Y.txt
  - raw/transcripts/4Cb_l2LJAW8.txt
  - raw/transcripts/qKU-e0x2EmE.txt
  - raw/transcripts/9jxrmk_Xses.txt
  - raw/transcripts/U4kZ0t7Onhw.txt
confidence: medium
---

# Autoresearch Video Corpus

The ingested YouTube corpus that documents the loop in practice: one tutorial,
one generalization stress test, one agent benchmark, one harness-integration
demo, one skill self-improver, and a 9-video playlist of domain experiments.
(7 of the 11 ingested transcripts are cited here; the full list is in
`kb/raw/transcripts/`.)

| Video | Channel | Objective | Outcome |
|---|---|---|---|
| -Ip9EtoBjbk — music AI model | Tonbi's AI Garage | Generate ABC sheet music | val_bpb 2.08 → 0.978; coherent tunes from gibberish |
| bMoNOb0iXpA — can you autoresearch everything? | marimo | Solve TSP (Kaggle Traveling Santa) | Works; warm starts + steering; parallel runs lost best solution |
| jCNeVZJAYGM — best local LLM | Sharbel A. | Bake-off of 4 local controllers | Qwen won (1.142); see [[local-llm-controllers]] |
| uBWuKh1nZ2Y — the only tutorial you'll need | David Ondrej | Website load-time optimization | 50ms → 25ms demo; three success conditions |
| 4Cb_l2LJAW8 — Claude Code + autoresearch | Nick Saraev | Cold-email optimizer | GitHub Actions cron + Slack review; challengers mostly lose initially |
| qKU-e0x2EmE — autoresearch fixes skills | Maker School | Claude skill self-improvement | 32/40 → 39/40; see [[skill-self-improvement]] |
| Playlist (9 videos) | Tonbi's AI Garage | Broad: stories, D&D, code, music, GPU kernel, nanochat | Stories: 0.511 near-human; code: metric win but broken generation; see [[domain-adaptation]] |

## Cross-video lessons

- Three conditions every time: clear metric, automated eval, editable artifact ([[problem-selection]]).
- Metric wins can hide generation failures — always sample output ([[val-bpb-metric]]).
- Claude Code is the most-used harness; harness friction is real.
- Modest hardware (RTX 4060-class) is enough; fixed budget + overnight cadence
  is the norm.

Related: [[domain-adaptation]] · [[problem-selection]] · [[skill-self-improvement]] · [[local-llm-controllers]]