---
source_url: https://www.youtube.com/watch?v=-Ip9EtoBjbk
ingested: 2026-09-26
topic: sheet-music (ABC notation) language model — contract instantiation from the video corpus
---

# Example 1 — music-abc: sheet-music LM (val_bpb, lower is better)

Template instantiation on the transcript-corpus topic "optimize a model for
sheet music" (Tonbi's AI Garage, kb/raw/transcripts/-Ip9EtoBjbk.txt — the
scratch copy under the slash-repo clone). The corpus here is procedurally
generated ABC notation (seeded, deterministic, embedded in prepare.py) — an
honest stand-in for the real ABC corpora, chosen so the example is fully
self-contained and reproducible.


## Git history (verbatim from the worked run)

```
b071b93 candidate: alpha=0.5 (lighter backoff)
f3d6349 candidate: bigram interpolation lam=0.7
3dfcd1d candidate: bigram interpolation lam=0.5
15d522f contract: program.md + frozen prepare.py + baseline train.py
```
