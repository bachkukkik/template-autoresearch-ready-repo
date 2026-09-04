---
title: Domain Adaptation
created: 2026-09-04
updated: 2026-09-04
type: concept
tags: [autoresearch, example]
sources: [raw/transcripts/-Ip9EtoBjbk.txt, raw/transcripts/T6pQVgIt8ZY.txt, raw/transcripts/U4kZ0t7Onhw.txt, raw/articles/autoresearch-template-research-conclusions.md]
confidence: medium
---

# Domain Adaptation

Taking the autoresearch loop to a new domain. The loop, the metric, and the
selection rules are unchanged; only the data side of `prepare.py` and the notes
in `program.md` change.

## The recipe

1. Get the data (e.g. ABC-notation sheet music, D&D dialogue, Python source).
2. Adapt `prepare.py`: constants, tokenizer training on the new corpus.
3. Keep `val_bpb` as the metric — it is byte-based and domain-agnostic.
4. Run the loop; expect a higher baseline and slower convergence on new domains.

## Evidence

- **Music (ABC sheet music):** baseline 2.08 → 0.978 (~53% improvement) in ~18
  experiments on a mid-range laptop GPU; batch-size reduction was the biggest
  win; increasing depth hurt (throughput-bound on small, regular data).
- **D&D dialogue (GPT-2 LoRA fine-tune):** fluent dialogue with speaker labels;
  first attempt was buggy and had to be recovered.
- **Python code (failure case):** val_bpb 1.85 → 0.82 yet the generated output
  degraded into repetition loops ("import torch CH CH CH…") — teacher-forced
  eval vs autoregressive generation gap. Tiny models overfit common tokens.
- **Stories (TinyStories warm-up):** 1.173 → 0.511 (~56%, near the ~0.5 human
  level) in ~2 hours on an RTX 4060-class laptop.

## Lesson

Simple, low-entropy, highly regular data favours small fast models that see the
data many times within budget; complex varied data fails at generation despite
metric wins. Always sample generated output — see [[val-bpb-metric]] and
[[problem-selection]].

Related: [[autoresearch-contract]] · [[autoresearch-video-corpus]]

^[raw/transcripts/-Ip9EtoBjbk.txt] ^[raw/transcripts/U4kZ0t7Onhw.txt] ^[raw/transcripts/9jxrmk_Xses.txt]