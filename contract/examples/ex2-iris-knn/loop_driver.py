#!/usr/bin/env python3
"""Faithful autoresearch loop driver for ex2-iris-knn.

Same pattern as ex1-music-abc/loop_driver.py, with the comparison direction
inverted: the metric here is ACCURACY (higher is better), so a candidate is
kept only on a STRICT INCREASE (`acc > best`), otherwise
`git reset --hard HEAD~1`.

Each candidate: apply edit -> git commit -> run -> parse `^accuracy:` from
run.log -> append results.tsv -> keep or reset. The edits below are the
mutation operator's choices (LLM-driven), applied mechanically.

Patch syntax: (regex, replacement), applied with re.subn(count=1, flags=M) so a
candidate stays valid regardless of whether the previous candidates were kept
or reverted. A miss (n != 1) aborts the driver.

Contract guard: asserts train.evaluate_accuracy IS prepare.evaluate_accuracy
before running anything — `prepare.py` is frozen, the agent never redefines it.
"""
import re
import subprocess
import sys
import time

HEADER = "commit\taccuracy\tseconds\tstatus\tdescription"

# K, METRIC, NORMALIZE, WEIGHTED are the four knobs at the top of train.py.
# Each candidate chains from the CURRENT kept state; after a discard the driver
# re-reads train.py fresh (git reset restored it).
CANDIDATES = [
    ("baseline 1-NN euclidean, raw features", []),
    ("k=3 kNN", [(r"^K = \d+", "K = 3")]),
    ("z-score normalization (train-only mu/sigma)",
     [(r"^NORMALIZE = (?:True|False)", "NORMALIZE = True")]),
    ("k=5 kNN", [(r"^K = \d+", "K = 5")]),
    ("Manhattan (L1) distance", [(r'^METRIC = "\w+"', 'METRIC = "manhattan"')]),
    ("k=7 kNN", [(r"^K = \d+", "K = 7")]),
    ("inverse-distance weighted vote",
     [(r"^WEIGHTED = (?:True|False)", "WEIGHTED = True")]),
]


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def assert_frozen_evaluator():
    """The contract: train.py imports the evaluator, never redefines it."""
    import prepare
    import train
    if train.evaluate_accuracy is not prepare.evaluate_accuracy:
        print("CONTRACT VIOLATION: train.evaluate_accuracy is not "
              "prepare.evaluate_accuracy")
        sys.exit(1)
    print(f"contract ok: train.evaluate_accuracy is prepare.evaluate_accuracy "
          f"(train={len(train.TRAIN)} test={len(train.TEST)} "
          f"seed={prepare.SPLIT_SEED})")


def parse(log, key):
    for line in open(log):
        if line.startswith(key):
            return float(line.split(":")[1])
    return None


def main():
    assert_frozen_evaluator()
    # results.tsv is untracked (gitignored) and re-initialized by the driver.
    with open("results.tsv", "w") as f:
        f.write(HEADER + "\n")

    best = None
    rows = []
    for desc, patches in CANDIDATES:
        src = open("train.py").read()
        ok = True
        for i, (pattern, repl) in enumerate(patches):
            src, n = re.subn(pattern, repl, src, count=1, flags=re.M)
            if n != 1:
                print(f"PATCH MISS for {desc!r}: {pattern!r}")
                ok = False
                break
        if not ok:
            sys.exit(1)
        open("train.py", "w").write(src)
        sh("git", "add", "train.py")
        sh("git", "commit", "-qm", f"candidate: {desc}")
        t0 = time.time()
        sh("bash", "-lc", "python3 train.py > run.log 2>&1; echo RC=$?")
        secs = time.time() - t0

        acc = parse("run.log", "accuracy:")
        commit = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
        if acc is None:
            status, acc = "crash", 0.0
        elif best is None or acc > best:      # INVERTED vs ex1: higher is better
            status, best = "keep", acc
        else:
            status = "discard"
        rows.append((commit, acc, secs, status, desc))
        print(f"{commit}  accuracy={acc:.6f}  {status:8s}  {secs:5.2f}s  {desc}")
        if status == "discard":
            sh("git", "reset", "--hard", "-q", "HEAD~1")
    with open("results.tsv", "a") as f:
        for c, v, s, st, d in rows:
            f.write(f"{c}\t{v:.6f}\t{s:.2f}\t{st}\t{d}\n")
    print(f"\nbest accuracy: {best:.6f}")
    print("results.tsv rows:", len(rows))


if __name__ == "__main__":
    main()
