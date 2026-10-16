---
source_url: https://www.youtube.com/watch?v=-Ip9EtoBjbk
ingested: 2026-09-26
topic: sheet-music (ABC notation) language model — contract instantiation from the video corpus
---

# Example 1 — music-abc: sheet-music LM (val_bpb, lower is better)

Template instantiation on the transcript-corpus topic "optimize a model for
sheet music" (Tonbi's AI Garage, kb/raw/transcripts/-Ip9EtoBjbk.txt — the
scratch copy under the private repo clone). The corpus here is procedurally
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

(These commits are from the worked run; they are not in this repo — a re-run
starts a fresh `git init` and produces different hashes.)

## Reproducing the ledger

The tracked `train.py` is the FINAL kept state (bigram `lam=0.7`, `alpha=0.5`);
the worked run started from `train_baseline.py` (pure unigram, `alpha=1.0`),
reconstructed by reverting the kept candidates. From a scratch clone:

```bash
cp -r contract/examples/ex1-music-abc /tmp/ex1 && cd /tmp/ex1
git init -q && git add -A && git commit -qm "contract: baseline"
python3 loop_driver.py --from-baseline
```

`loop_driver.py` is a **scripted reference run** — a fixed candidate list replayed
deterministically, not an LLM's choices. A re-run reproduces the
`val_bpb`/`status`/`description` columns row for row; the `seconds` column is a
fresh wall-clock measurement (T2, never compared) and the commit hashes differ.
