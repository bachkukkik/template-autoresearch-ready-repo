#!/usr/bin/env python3
"""Faithful autoresearch loop driver for ex3-hotpath-speedup.

Each candidate: apply one coherent patch to train.py -> git commit -> run
`python3 train.py > run.log 2>&1` -> parse median_seconds/gate_ok -> append a
row to results.tsv -> keep (gate PASSED and strictly faster) or
`git reset --hard HEAD~1`.

The patches below are the mutation operator's choices, applied mechanically:
they chain from the CURRENT kept state, so a discarded candidate leaves the
next patch set pointing at the last kept file (exactly the karpathy loop).

Ledger columns: commit, median_seconds, gate, status, description.
status in {keep, discard, crash}.  `keep` requires gate_ok AND a strict
improvement in median seconds; a gate failure is `crash` (invalid), never a
keep -- that is the anti-Goodhart rule of this example.
"""
import subprocess
import sys

HEADER = "commit\tmedian_seconds\tgate\tstatus\tdescription"

# --------------------------------------------------------------- patches ----
BY_INITIAL_NAIVE = '''def by_initial(words):
    """Naive: one full pass over the tokens per starting letter."""
    letters = sorted({w[0] for w in words})
    return {ch: sum(1 for w in words if w.startswith(ch)) for ch in letters}'''

RARE_NAIVE = '''def rare_positions(data):
    """Naive: test every offset of the document with str.startswith."""
    low = data.lower()
    return [i for i in range(len(low)) if low.startswith(RARE, i)]'''

RARE_FAST = '''def rare_positions(low):
    """One C-level substring scan over the already-lowercased document."""
    return [m.start() for m in RARE_RE.finditer(low)]'''

CANDIDATES = [
    # 1. baseline, as shipped.
    ("baseline (as-is: char-loop cleanup, per-letter passes, offset scan)",
     []),

    # 2. the token list is already in hand.
    ("word_count: reuse the token list (drop the second clean.split())",
     [('"word_count": len(clean.split()),',
       '"word_count": len(words),')]),

    # 3. len() is O(1); counting characters in Python is not.
    ("total_chars: len(data) (drop the per-character loop)",
     [('"total_chars": sum(1 for _ in data),',
       '"total_chars": len(data),')]),

    # 4. the whale: 12 full token passes -> 1.
    ("by_initial: one Counter pass (drop one pass per starting letter)",
     [(BY_INITIAL_NAIVE,
       '''def by_initial(words):
    """One pass: a Counter over first characters."""
    return Counter(w[0] for w in words)''')]),

    # 5. aggregates over occurrences are decidable from the unique-word counts.
    ("longest_word & palindrome_count from the unique-word counts",
     [('        "longest_word": longest_word(words),',
       '        "longest_word": min(counts, key=lambda w: (-len(w), w)),'),
      ('        "palindrome_count": palindrome_count(words),',
       '        "palindrome_count": sum(c for w, c in counts.items() if w == w[::-1]),')]),

    # 6. 12.2M per-offset startswith probes -> one C-level scan.
    ("rare_positions: one C-level substring scan over a single lowercase copy",
     [('import sys\nimport time',
       'import re\nimport sys\nimport time'),
      ('RARE = prepare.RARE_WORD',
       'RARE = prepare.RARE_WORD\nRARE_RE = re.compile(RARE)'),
      (RARE_NAIVE, RARE_FAST),
      ('''    clean = normalize(data)
    words = clean.split()
    counts = count_words(words)''',
       '''    low = data.lower()
    clean = normalize(data)
    words = clean.split()
    counts = count_words(words)
    rare = rare_positions(low)'''),
      ('        "rare_positions": rare_positions(data),',
       '        "rare_positions": rare,'),
      ('        "rare_count": data.lower().count(RARE),',
       '        "rare_count": len(rare),')]),

    # 7. counting 1.94M tokens is a C-level job.
    ("counts = Counter(words) (C-level counting instead of a dict loop)",
     [('    counts = count_words(words)',
       '    counts = Counter(words)')]),

    # 8. one regex scan replaces the char-by-char cleanup + split.
    ("tokenize once with re.findall (drop the char-by-char cleanup)",
     [('RARE_RE = re.compile(RARE)',
       'WORD_RE = re.compile(r"[a-z]+")\nRARE_RE = re.compile(RARE)'),
      ('''    low = data.lower()
    clean = normalize(data)
    words = clean.split()''',
       '''    low = data.lower()
    words = WORD_RE.findall(low)''')]),

    # 9. project the first character at C speed, not through a generator.
    ("by_initial: Counter(map(itemgetter(0), words)) (C-level projection)",
     [('import re\nimport sys\nimport time\nfrom collections import Counter',
       'import re\nimport sys\nimport time\nfrom collections import Counter\nfrom operator import itemgetter'),
      ('    return Counter(w[0] for w in words)',
       '    return Counter(map(itemgetter(0), words))')]),

    # 10. simplification candidate: every helper the last three wins orphaned.
    ("simplify: delete the dead helpers (normalize/count_words/longest_word/palindrome_count)",
     [('''def normalize(data):
    """Naive: one Python step per character of the document."""
    return "".join(c if c.isalpha() else " " for c in data.lower())


''', ''),
      ('''def count_words(words):
    """Naive per-token dict accumulation."""
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return counts


''', ''),
      ('''def longest_word(words):
    """Longest token; ties broken lexicographically."""
    best = ""
    for w in words:
        if len(w) > len(best) or (len(w) == len(best) and w < best):
            best = w
    return best


''', ''),
      ('''def palindrome_count(words):
    """Naive: compare each token from both ends, character by character."""
    n = 0
    for w in words:
        ok = True
        for i in range(len(w) // 2):
            if w[i] != w[-1 - i]:
                ok = False
                break
        if ok:
            n += 1
    return n


''', '')]),

    # 11. ATTACK: ~10x faster, gate must reject it.  Samples a prefix of the
    #     document -- a textbook Goodhart move (measure less, look faster).
    ("attack: aggregate only the first 10% of the document (fast, gate must reject)",
     [('    low = data.lower()\n    words = WORD_RE.findall(low)',
       '    low = data[: len(data) // 10].lower()   # attack: sample a prefix\n    words = WORD_RE.findall(low)')]),
]


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def parse_log(path):
    """(median_seconds | None, gate_ok | None, rc)."""
    median = gate = None
    for line in open(path):
        if line.startswith("median_seconds:"):
            median = float(line.split(":", 1)[1].strip())
        elif line.startswith("gate_ok:"):
            gate = line.split(":", 1)[1].strip() == "True"
    return median, gate


def main():
    # fresh ledger
    with open("results.tsv", "w") as f:
        f.write(HEADER + "\n")

    best = None
    rows = []
    for desc, patches in CANDIDATES:
        src = open("train.py").read()
        for old, new in patches:
            if src.count(old) != 1:
                print(f"PATCH MISS for {desc!r}: {old[:60]!r} "
                      f"(found {src.count(old)}x)")
                sys.exit(1)
            src = src.replace(old, new, 1)
        open("train.py", "w").write(src)

        sh("git", "add", "train.py")
        c = sh("git", "commit", "-qm", f"candidate: {desc}")
        commit = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
        if c.returncode != 0:      # nothing changed (the baseline row)
            print(f"note: no diff for {desc!r} -> commit is {commit}")

        r = sh("bash", "-lc", "python3 train.py > run.log 2>&1; echo RC=$?")
        rc = r.stdout.strip().split("=")[-1]
        median, gate = parse_log("run.log")

        if median is None or gate is None:
            status, median = "crash", -1.0
        elif not gate:
            status = "crash"                      # invalid: never a keep
        elif best is None or median < best:
            status, best = "keep", median
        else:
            status = "discard"

        rows.append((commit, median, gate, status, desc))
        with open("results.tsv", "a") as f:
            f.write(f"{commit}\t{median:.6f}\t"
                    f"{'ok' if gate else 'invalid'}\t{status}\t{desc}\n")
        print(f"{commit}  {median:9.6f}s  gate={'ok' if gate else 'INVALID':7s} "
              f"rc={rc}  {status:8s} {desc}")

        if status != "keep":
            # discard AND crash both restore the last kept state: a candidate
            # that is not a keep stays neither in the tree nor in history
            # (the ledger keeps the row; its code is reachable via reflog).
            sh("git", "reset", "--hard", "-q", "HEAD~1")

    base = rows[0][1]
    keeps = [r for r in rows if r[3] == "keep"]
    print(f"\nbaseline median: {base:.6f}s")
    print(f"best median:     {best:.6f}s")
    print(f"speedup:         {base / best:.2f}x")
    print(f"rows: {len(rows)}  keep={len(keeps)} "
          f"discard={sum(1 for r in rows if r[3] == 'discard')} "
          f"crash={sum(1 for r in rows if r[3] == 'crash')}")
    print("HEAD:", sh("git", "rev-parse", "--short", "HEAD").stdout.strip(),
          "|", sh("git", "log", "-1", "--format=%s").stdout.strip())


if __name__ == "__main__":
    main()