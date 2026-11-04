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
STEP_WINDOW = 256  # adjacent-pair window consumed per training step


def peak_rss_gb():
    """Peak host resident set of this process, in GB — a REAL measurement (SC10).

    ru_maxrss is KiB on Linux and bytes on macOS, so it is normalised to bytes
    first. Returns 0.0 only where `resource` is unavailable (non-POSIX).
    """
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX host
        return 0.0
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_len = float(max_rss) * (1.0 if sys.platform == "darwin" else 1024.0)
    return byte_len / (1024.0 ** 3)


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


def iter_count_updates(train_ids, window=STEP_WINDOW):
    """Yield the bigram count-updates one window at a time — one step each.

    The caller consumes these under a wall-clock deadline, so TIME_BUDGET bounds
    the number of steps actually taken: a cut stream yields a partially
    trained model, never a silently-full one.
    """
    for start in range(0, len(train_ids) - 1, window):
        yield list(zip(train_ids[start:start + window],
                       train_ids[start + 1:start + 1 + window]))


def _laplace_logprobs(counts, prev_totals, vocab_size):
    """Smoothed (prev -> next) log-probabilities from raw bigram counts."""
    return {(a, b): math.log((c + 1.0) / (prev_totals[a] + vocab_size))
            for (a, b), c in counts.items()}


def build_bigram_logprobs(train_ids, vocab_size):
    """Count smoothed (prev -> next) character bigrams from training ids.

    Returns {(prev_id, next_id): log-probability} with Laplace smoothing.
    """
    counts = {}
    prev_totals = {}
    for updates in iter_count_updates(train_ids):
        for a, b in updates:
            counts[(a, b)] = counts.get((a, b), 0) + 1
            prev_totals[a] = prev_totals.get(a, 0) + 1
    return _laplace_logprobs(counts, prev_totals, vocab_size)


def read_incumbent(results_path):
    """Best `keep` metric in the ledger, or None when it has no baseline yet.

    DIRECTION decides which end is best, so the same reader ports to a
    higher-is-better metric. The ledger is the record the evaluator checks.
    """
    if not results_path or not os.path.exists(results_path):
        return None
    best = None
    with open(results_path) as f:
        for line in f.read().splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) != 5 or cols[3] != "keep":
                continue
            try:
                value = float(cols[1])
            except ValueError:
                continue
            if best is None:
                best = value
            elif prepare.DIRECTION == "lower":
                best = min(best, value)
            else:
                best = max(best, value)
    return best


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
        f.write("{}\t{:.6f}\t{:.3f}\t{}\t{}\n".format(
            commit, val_bpb, memory_gb, status, description))
    return results_path


def run(results_path=None, description=None, shrinks=False):
    """Train the tiny model; print the summary block; optionally log the row.

    The budget is read dynamically from prepare.TIME_BUDGET at run time (so it
    stays monkeypatchable under test — no wall-clock wait in tests) and checked
    every step, so it is a real ceiling. The status written to the ledger is
    prepare.decide()'s verdict against the incumbent — never a hard-coded keep.
    Results are written only when `results_path` is provided; a plain
    `python3 train.py` writes nothing to the repo.
    """
    t_start = time.time()
    budget = prepare.TIME_BUDGET  # dynamic — fixed time budget from prepare.py
    deadline = time.monotonic() + budget  # the ceiling, checked every step

    vocab, tokenize = prepare.tokenizer()
    V = len(vocab)
    train_ids = tokenize(prepare.TRAIN_TEXT)
    val_ids = tokenize(prepare.VAL_TEXT)

    # tiny baseline model: smoothed bigram counts, accumulated step by step so
    # the deadline can actually cut training short (stop_reason="budget")
    t_train = time.time()
    counts = {}
    prev_totals = {}
    num_steps = 0
    stop_reason = "converged"
    for step, updates in enumerate(iter_count_updates(train_ids), start=1):
        if time.monotonic() >= deadline:
            stop_reason = "budget"
            break
        num_steps = step
        for a, b in updates:
            counts[(a, b)] = counts.get((a, b), 0) + 1
            prev_totals[a] = prev_totals.get(a, 0) + 1
    lp = _laplace_logprobs(counts, prev_totals, V)
    training_seconds = time.time() - t_train

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
    peak_vram_mb = 0.0  # CPU-only demo baseline (the ledger measures host RSS)
    memory_gb = peak_rss_gb()

    print("---")
    print("val_bpb:          {:.6f}".format(val_bpb))
    print("training_seconds: {:.1f}".format(training_seconds))
    print("total_seconds:    {:.1f}".format(total_seconds))
    print("peak_vram_mb:     {:.1f}".format(peak_vram_mb))
    print("stop_reason:      {}".format(stop_reason))
    print("num_steps:        {}".format(num_steps))
    print("num_params_M:     {:.3f}".format(num_params / 1e6))
    print("---")

    if results_path:
        incumbent = read_incumbent(results_path)
        status = prepare.decide(val_bpb, incumbent, shrinks=shrinks)
        if description is None:
            description = "smoothed bigram, stop={}, budget={}s".format(
                stop_reason, budget)
        log_result(
            results_path,
            commit=_git_commit(),
            val_bpb=val_bpb,
            memory_gb=memory_gb,
            status=status,
            description=description,
        )

    return val_bpb


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Autoresearch agent artifact — edit this file, run within "
                    "prepare.TIME_BUDGET.")
    parser.add_argument(
        "--results", default=None, metavar="PATH",
        help="results.tsv path to append a row to (optional; file stays untracked)")
    parser.add_argument(
        "--description", default=None, metavar="TEXT",
        help="description for the appended row (default: an auto summary)")
    parser.add_argument(
        "--shrinks", action="store_true",
        help="the change deleted code — a within-noise-floor tie is then a keep")
    args = parser.parse_args(argv)
    run(results_path=args.results, description=args.description,
        shrinks=args.shrinks)
    return 0


if __name__ == "__main__":
    sys.exit(main())