"""train.py — the ONLY agent-edited file (iris-knn example).

Baseline: 1-nearest-neighbour classifier, raw Euclidean distance, no
normalization. Every candidate edit changes ONLY this file; `evaluate_accuracy`
is imported from prepare (never redefined).

Knobs (the mutation operator edits exactly these four lines):
    K         — number of neighbours in the vote
    METRIC    — "euclidean" | "manhattan"
    NORMALIZE — z-score standardize features (per-feature mean/std of TRAIN)
    WEIGHTED  — inverse-distance weighted vote instead of a plain count
"""
import math
import time

import prepare
from prepare import CLASSES, TEST, TIME_BUDGET, TRAIN, evaluate_accuracy

K = 7                 # neighbours
METRIC = "euclidean"  # "euclidean" | "manhattan"
NORMALIZE = False     # z-score standardize features before distance
WEIGHTED = False      # inverse-distance weighted vote


def _euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _manhattan(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


def _distance(a, b, metric):
    return _manhattan(a, b) if metric == "manhattan" else _euclidean(a, b)


def _standardizer(rows):
    """Per-feature mu/sigma from TRAIN only (never from TEST)."""
    d = len(rows[0][0])
    n = len(rows)
    mu = [sum(r[0][j] for r in rows) / n for j in range(d)]
    sd = []
    for j in range(d):
        var = sum((r[0][j] - mu[j]) ** 2 for r in rows) / n
        sd.append(math.sqrt(var) or 1.0)
    return mu, sd


def make_predict_fn():
    """Return predict_fn(features: list[float]) -> label: str."""
    if NORMALIZE:
        mu, sd = _standardizer(TRAIN)
        norm = lambda x: [(x[j] - mu[j]) / sd[j] for j in range(len(x))]
        train = [(norm(f), lab) for f, lab in TRAIN]
    else:
        norm = lambda x: x
        train = TRAIN

    def predict_fn(x):
        x = norm(x)  # the query must be scaled by the SAME train-only mu/sigma
        neighbours = sorted(
            ((_distance(x, f, METRIC), lab) for f, lab in train),
            key=lambda t: t[0],
        )[:K]
        if WEIGHTED:
            votes = {}
            for dist, lab in neighbours:
                votes[lab] = votes.get(lab, 0.0) + 1.0 / (dist + 1e-12)
            return max(CLASSES, key=lambda c: votes.get(c, 0.0))
        votes = {}
        for _, lab in neighbours:
            votes[lab] = votes.get(lab, 0) + 1
        return max(CLASSES, key=lambda c: votes.get(c, 0))

    return predict_fn


def main():
    t0 = time.time()
    predict_fn = make_predict_fn()
    accuracy = evaluate_accuracy(predict_fn)
    elapsed = time.time() - t0

    print("---")
    print(f"accuracy:         {accuracy:.6f}")
    print(f"training_seconds: {elapsed:.1f}")
    print(f"total_seconds:    {elapsed:.1f}")
    print(f"config:           K={K} METRIC={METRIC} NORMALIZE={NORMALIZE} WEIGHTED={WEIGHTED}")
    print("---")
    return accuracy


if __name__ == "__main__":
    main()
