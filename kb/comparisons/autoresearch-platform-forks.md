---
title: Autoresearch Platform Forks
created: 2026-09-04
updated: 2026-09-04
type: comparison
tags: [autoresearch, integration]
sources: [raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Autoresearch Platform Forks

The maintained platform ports of karpathy/autoresearch. All keep the
prepare.py/train.py/program.md semantics; each changes only the
attention/kernel/optimizer backend.

| Fork | Platform | Key changes |
|---|---|---|
| upstream (karpathy) | NVIDIA Linux (H100 tested) | Reference; full-size defaults |
| miolini/autoresearch-macos | macOS MPS | SDPA + MPS optimizations; created 2026-03-07 |
| trevin-creator/autoresearch-mlx | macOS MLX | No PyTorch; adds `rigor.py` statistical keep/discard gate for run noise (~0.03 val_bpb) |
| jsegov/autoresearch-win-rtx | Windows consumer RTX | Tiered VRAM, TinyStories-friendly defaults |
| andyluo7/autoresearch | AMD ROCm/HIP (MI300X family) | Backend port; diverges mainly in train.py |

## Guidance

Self-select by hardware, then apply Karpathy's small-compute tuning: TinyStories
dataset, lower `vocab_size`, lower `MAX_SEQ_LEN`, lower `EVAL_TOKENS`, lower
`DEPTH`, `WINDOW_PATTERN="L"`, powers-of-2 `TOTAL_BATCH_SIZE`. A curated list
with ~153 entries lives at github.com/yibie/awesome-autoresearch.

Related: [[karpathy-autoresearch]] · [[autoresearch-contract]] · [[autonomous-research-systems]]