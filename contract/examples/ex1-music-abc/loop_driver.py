#!/usr/bin/env python3
"""Faithful autoresearch loop driver for ex1-music-abc.

Each candidate: apply edit -> git commit -> run -> parse val_bpb from run.log
-> append results.tsv -> keep (strict improvement) or git reset --hard HEAD~1.
The edits below are the mutation operator's choices (LLM-driven), applied
mechanically. results.tsv stays untracked (gitignored).
"""
import subprocess
import sys

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

def main():
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
