"""train.py — the agent-edited artifact of the autoresearch loop.

This is the ONLY file you edit (see program.md). It currently ships a tiny,
stdlib-only character bigram model with Laplacian smoothing as an honest
baseline. Replace or extend it with anything that runs within
prepare.TIME_BUDGET and samples clean output (see program.md §Caveats).

Stdlib only. evaluate_bpb MUST be imported from prepare — never redefine it.
"""

import argparse
import math
import os
import subprocess
import sys
import time

import prepare
from prepare import evaluate_bpb  # the ground-truth metric — do NOT redefine

RESULTS_HEADER = "commit\tval_bpb\tmemory_gb\tstatus\tdescription"


def _git_commit():
    """Best-effort short (7-char) commit hash, or a placeholder off-git."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "0000000"
    except Exception:
        return "0000000"


def build_bigram_logprobs(train_ids, vocab_size):
    """Count smoothed (prev -> next) character bigrams from training ids.

    Returns {(prev_id, next_id): log-probability} with Laplace smoothing.
    """
    counts = {}
    prev_totals = {}
    for a, b in zip(train_ids, train_ids[1:]):
        counts[(a, b)] = counts.get((a, b), 0) + 1
        prev_totals[a] = prev_totals.get(a, 0) + 1
    lp = {}
    for (a, b), c in counts.items():
        lp[(a, b)] = math.log((c + 1.0) / (prev_totals[a] + vocab_size))
    return lp


def log_result(results_path, commit, val_bpb, memory_gb, status, description,
               header=RESULTS_HEADER):
    """Append a results.tsv row (upstream format), creating the header if needed.

    results.tsv stays untracked by git — see program.md §Logging results.
    Commas are fine in descriptions (tab-separated, NOT comma-separated).
    """
    new = not os.path.exists(results_path) or os.path.getsize(results_path) == 0
    with open(results_path, "a") as f:
        if new:
            f.write(header + "\n")
        f.write("{}\t{:.6f}\t{:.1f}\t{}\t{}\n".format(
            commit, val_bpb, memory_gb, status, description))
    return results_path


def run(results_path=None):
    """Train the tiny model; print the summary block; optionally log the row.

    The budget is read dynamically from prepare.TIME_BUDGET at run time (so it
    stays monkeypatchable under test — no wall-clock wait in tests). Results are
    written only when `results_path` is provided; a plain `python3 train.py`
    writes nothing to the repo.
    """
    t_start = time.time()
    budget = prepare.TIME_BUDGET  # dynamic — fixed time budget from prepare.py

    vocab, tokenize = prepare.tokenizer()
    V = len(vocab)
    train_ids = tokenize(prepare.TRAIN_TEXT)
    val_ids = tokenize(prepare.VAL_TEXT)

    # tiny baseline model: smoothed bigram counts over the training corpus
    t_train = time.time()
    lp = build_bigram_logprobs(train_ids, V)
    training_seconds = time.time() - t_train
    num_steps = len(train_ids) - 1

    # per-position logits over the validation set (char-level next-char task)
    val_logits = []
    val_targets = []
    for i in range(len(val_ids) - 1):
        prev = val_ids[i]
        nxt = val_ids[i + 1]
        row = [lp.get((prev, j), math.log(1.0 / V)) for j in range(V)]
        val_logits.append(row)
        val_targets.append(nxt)

    val_bpb = evaluate_bpb(val_logits, val_targets, prepare.TOKEN_BYTES)

    total_seconds = time.time() - t_start
    num_params = V * V  # bigram count table
    peak_vram_mb = 0.0  # CPU-only demo baseline

    print("---")
    print("val_bpb:          {:.6f}".format(val_bpb))
    print("training_seconds: {:.1f}".format(training_seconds))
    print("total_seconds:    {:.1f}".format(total_seconds))
    print("peak_vram_mb:     {:.1f}".format(peak_vram_mb))
    print("num_steps:        {}".format(num_steps))
    print("num_params_M:     {:.3f}".format(num_params / 1e6))
    print("---")

    if results_path:
        log_result(
            results_path,
            commit=_git_commit(),
            val_bpb=val_bpb,
            memory_gb=peak_vram_mb / 1024.0,
            status="keep",  # first run = baseline
            description="baseline smoothed bigram, budget={}s".format(budget),
        )

    return val_bpb


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Autoresearch agent artifact — edit this file, run within "
                    "prepare.TIME_BUDGET.")
    parser.add_argument(
        "--results", default=None, metavar="PATH",
        help="results.tsv path to append a row to (optional; file stays untracked)")
    args = parser.parse_args(argv)
    run(results_path=args.results)
    return 0


if __name__ == "__main__":
    sys.exit(main())