#!/usr/bin/env python3
"""SCRIPTED REFERENCE RUN driver for ex1-music-abc.

This is a scripted reference run: a fixed candidate list (`CANDIDATES`) replayed
by a deterministic driver. A live agent would generate candidates itself from the
run log; nothing here claims an LLM chose them.

Each candidate: apply edit -> git commit -> run -> parse val_bpb from run.log
-> append results.tsv -> keep (strict improvement) or git reset --hard HEAD~1.

Reproduce the vendored ledger in a scratch clone, starting from the tracked
baseline (results.tsv stays untracked / gitignored):

    cp -r contract/examples/ex1-music-abc /tmp/ex1 && cd /tmp/ex1
    git init -q && git add -A && git commit -qm "contract: baseline"
    python3 loop_driver.py --from-baseline

`--from-baseline` copies the tracked ``train_baseline.py`` over ``train.py`` and
commits it, so the patch anchors below (written against the baseline) apply. A
fresh scratch clone otherwise ships the FINAL kept ``train.py``, and the driver
would abort on ``PATCH MISS``. Commit hashes differ on a re-run; compare the
metric / status / description columns only.
"""
import os
import shutil
import subprocess
import sys

HEADER = "commit\tval_bpb\tseconds\tstatus\tdescription"
BASELINE = "train_baseline.py"

CANDIDATES = [
    # State model: patches chain from the CURRENT kept state. After a discard,
    # git reset restores the last kept state — the driver re-reads train.py fresh.
    ("baseline (unigram add-alpha=1, no context)", []),
    ("bigram interpolation lam=0.5",
     [("make_prob_fn(unigram, bigrams, lam=0.0)", "make_prob_fn(unigram, bigrams, lam=0.5)")]),
    ("bigram interpolation lam=0.7",
     [("make_prob_fn(unigram, bigrams, lam=0.5)", "make_prob_fn(unigram, bigrams, lam=0.7)")]),
    ("lam=0.6 fine-tune",
     [("make_prob_fn(unigram, bigrams, lam=0.7)", "make_prob_fn(unigram, bigrams, lam=0.6)")]),
    ("alpha=0.5 (lighter backoff)",
     [("unigram = build_model(alpha=1.0)", "unigram = build_model(alpha=0.5)")]),
    ("alpha=2.0 (heavier backoff)",
     [("unigram = build_model(alpha=0.5)", "unigram = build_model(alpha=2.0)")]),
]

def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)

def reset_to_baseline():
    """--from-baseline: copy the tracked baseline over train.py, then commit it."""
    if not os.path.exists(BASELINE):
        print(f"--from-baseline: {BASELINE} not found beside {__file__}")
        sys.exit(1)
    shutil.copyfile(BASELINE, "train.py")
    sh("git", "add", "train.py")
    sh("git", "commit", "-qm", "contract: baseline train.py (reconstructed)")
    head = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    print(f"--from-baseline: train.py <- {BASELINE} (HEAD {head})")

def main():
    if "--from-baseline" in sys.argv[1:]:
        reset_to_baseline()
    # results.tsv is untracked (gitignored) and re-initialized by the driver.
    with open("results.tsv", "w") as f:
        f.write(HEADER + "\n")

    best = None
    rows = []
    for desc, patches in CANDIDATES:
        src = open("train.py").read()
        ok = True
        for old, new in patches:
            if old not in src:
                print(f"PATCH MISS for {desc!r}: {old!r}")
                ok = False
                break
            src = src.replace(old, new, 1)
        if not ok:
            sys.exit(1)
        open("train.py", "w").write(src)
        sh("git", "add", "train.py")
        sh("git", "commit", "-qm", f"candidate: {desc}")
        r = sh("bash", "-lc", "python3 train.py > run.log 2>&1; echo RC=$?")
        val = None
        for line in open("run.log"):
            if line.startswith("val_bpb:"):
                val = float(line.split(":")[1])
        commit = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
        if val is None:
            status, val = "crash", 0.0
        elif best is None or val < best:
            status, best = "keep", val
        else:
            status = "discard"
        secs = 0.0
        for line in open("run.log"):
            if line.startswith("training_seconds:"):
                secs = float(line.split(":")[1])
        rows.append((commit, val, secs, status, desc))
        print(f"{commit}  val_bpb={val:.6f}  {status:8s}  {desc}")
        if status == "discard":
            sh("git", "reset", "--hard", "-q", "HEAD~1")
    with open("results.tsv", "a") as f:
        for c, v, s, st, d in rows:
            f.write(f"{c}\t{v:.6f}\t{s:.1f}\t{st}\t{d}\n")
    print(f"\nbest val_bpb: {best:.6f}")
    print("results.tsv rows:", len(rows))

if __name__ == "__main__":
    main()
