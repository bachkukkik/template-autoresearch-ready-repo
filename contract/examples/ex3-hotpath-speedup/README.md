---
topic: ex3-hotpath-speedup — NON-ML autoresearch instantiation (wall-time under an exact-output gate)
ingested: 2026-09-26
contract: karpathy/autoresearch (program.md / prepare.py / train.py / results.tsv, keep-discard)
gate: exact-output equality against a frozen reference (slash-commerce metrics-contract anti-Goodhart pattern)
---

# Example 3 — ex3-hotpath-speedup: wall-time optimization under an exact-output gate

The contract instantiated on a **non-ML** problem: minimize the wall-clock time
of a fixed hot-path workload, where the *only* thing that can make a candidate
valid is reproducing a frozen reference result exactly.

Objective: **lowest median seconds per `run(data)` call, subject to
`run(data) == frozen reference`.** No accuracy/speed tradeoff exists — the
whole point is that speed is measured only after correctness is proven, which
is what makes a "fast" candidate trustworthy and a fast-but-wrong one a crash.

## What the workload is

`prepare.py` (FROZEN) embeds a deterministic 12.2 MB document generated with
`random.Random(1234)`: 2,000,000 seeded tokens drawn from a 582-word vocabulary
(Zipf-ish weights, 6 genuinely palindromic words, ~3% punctuation), plus 200
occurrences of a rare word (`Zorblat`) at seeded positions. `train.py` must
implement

```python
run(data: str) -> dict   # total_chars, word_count, top50, by_initial,
                         # longest_word, palindrome_count, rare_positions, rare_count
```

and the frozen side owns `EXPECTED_OUTPUT` (computed once at import by a
trivial reference implementation), `EXPECTED_OUTPUT_VAL` (held-out workload,
seed 99999), `check(...)`, `benchmark(reps=5)`, `evaluate(train_module) ->
(median_seconds, gate_ok)` and `TIME_BUDGET=60`.


## Git history (verbatim from the worked run)

```
5e16524 docs: example README — ledger, attack evidence, open questions
fbaba87 candidate: by_initial: Counter(map(itemgetter(0), words)) (C-level projection)
dceb367 candidate: tokenize once with re.findall (drop the char-by-char cleanup)
6ea4683 candidate: counts = Counter(words) (C-level counting instead of a dict loop)
d27200c candidate: rare_positions: one C-level substring scan over a single lowercase copy
f17cfb7 candidate: longest_word & palindrome_count from the unique-word counts
17a2ec5 candidate: by_initial: one Counter pass (drop one pass per starting letter)
85186d9 candidate: total_chars: len(data) (drop the per-character loop)
7a5da35 candidate: word_count: reuse the token list (drop the second clean.split())
56cde0b contract: program.md + frozen prepare.py + baseline train.py
```
