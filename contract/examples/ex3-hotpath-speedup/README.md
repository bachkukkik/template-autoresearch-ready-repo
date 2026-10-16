---
topic: ex3-hotpath-speedup — NON-ML autoresearch instantiation (wall-time under an exact-output gate)
ingested: 2026-09-26
contract: karpathy/autoresearch (program.md / prepare.py / train.py / results.tsv, keep-discard)
gate: exact-output equality against a frozen reference (a private commerce-pipeline instance's metrics-contract anti-Goodhart pattern)
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

(These commits are from the worked run; they are not in this repo — a re-run
starts a fresh `git init` and produces different hashes.)

## Reproducing the ledger

The tracked `train.py` is the FINAL kept state (the fastest valid candidate); the
worked run started from `train_baseline.py` (the suboptimal-but-correct baseline
with the per-character cleanup, per-letter passes and per-offset scan), the
reconstruction of which every kept candidate in `loop_driver.py` is a patch
against. From a scratch clone:

```bash
cp -r contract/examples/ex3-hotpath-speedup /tmp/ex3 && cd /tmp/ex3
git init -q && git add -A && git commit -qm "contract: baseline"
python3 loop_driver.py --from-baseline
```

`loop_driver.py` is a **scripted reference run** — a fixed candidate list replayed
deterministically, not an LLM's choices. A re-run reproduces the **gate column and
the descriptions** row for row, and the final kept `train.py` still passes the
exact-output gate. It does **not** reproduce the `median_seconds` column (T2
timing) or the keep/discard statuses: the `simplify` candidate sits within a few
percent of the incumbent and flips between keep and discard across runs, so only
the gate column is compared (`tests/integration/test_examples_replay.py`).
