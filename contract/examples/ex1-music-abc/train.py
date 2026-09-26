"""train.py — the ONLY agent-edited file (music-abc example).

Baseline: unigram LM with add-alpha smoothing. Candidate edits change ONLY
this file; evaluate_bpb is imported from prepare (never redefined).
"""
import math
import time
from collections import defaultdict

import prepare
from prepare import evaluate_bpb, TRAIN_TEXT, VAL_TEXT, VOCAB_SIZE, TIME_BUDGET


def build_model(alpha=1.0):
    """Unigram counts with add-alpha smoothing."""
    counts = [0.0] * VOCAB_SIZE
    for c in TRAIN_TEXT:
        counts[prepare.STOI[c]] += 1
    total = sum(counts)
    probs = [(cnt + alpha) / (total + alpha * VOCAB_SIZE) for cnt in counts]
    return probs


def make_prob_fn(unigram_probs, bigram_counts=None, lam=0.0):
    """prob_fn(prev_id) -> next-token distribution.

    lam=0: pure smoothed unigram (context-free).
    lam>0: interpolate smoothed bigram with the unigram backoff.
    """
    if bigram_counts is None or lam == 0.0:
        return lambda prev: unigram_probs

    bi_totals = {}
    for (a, b), n in bigram_counts.items():
        bi_totals.setdefault(a, 0.0)
        bi_totals[a] += n

    def prob_fn(prev):
        row = [unigram_probs[b] for b in range(VOCAB_SIZE)]  # backoff base
        tot = bi_totals.get(prev, 0.0)
        if tot > 0:
            for b in range(VOCAB_SIZE):
                n = bigram_counts.get((prev, b), 0)
                if n:
                    row[b] = (1 - lam) * row[b] + lam * (n / tot)
        return row

    return prob_fn


def main():
    t0 = time.time()
    unigram = build_model(alpha=0.5)
    bigrams = defaultdict(int)
    train_ids = prepare.tokenizer(TRAIN_TEXT)
    for a, b in zip(train_ids, train_ids[1:]):
        bigrams[(a, b)] += 1
    prob_fn = make_prob_fn(unigram, bigrams, lam=0.7)

    val_ids = prepare.tokenizer(VAL_TEXT)
    val_bpb = evaluate_bpb(val_ids, prob_fn)
    elapsed = time.time() - t0

    print("---")
    print(f"val_bpb:          {val_bpb:.6f}")
    print(f"training_seconds: {elapsed:.1f}")
    print(f"total_seconds:    {elapsed:.1f}")
    print("---")
    return val_bpb


if __name__ == "__main__":
    main()
