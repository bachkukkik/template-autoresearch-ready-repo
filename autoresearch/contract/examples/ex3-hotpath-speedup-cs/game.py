"""ex3-hotpath-speedup as an arena game — median_seconds, lower, PORTABLE.

The base example's ``train_baseline.py`` is the trunk start; ``prepare.py`` is
frozen (the exact-output gate) and copied into every seat; only ``train.py`` is
editable. The metric is wall-clock time, so this counterpart vendors no
record: timing is a T2 statistical field and a winner flips with it. What it
does prove is deterministic — the attack never passes the gate, the trunk that
survives still reproduces the frozen reference, and the banks are arithmetic.

Every anchor below is a LITERAL block of ``train_baseline.py`` and applies to
the baseline on its own, so a pool is a set of independent moves, not a chain:

* ``passes`` and ``scan`` are ex3's own candidates, regrouped by what they
  trade — Python-level passes over the token list, and C-level scans over the
  document. Each one is output-identical by construction; only its speed is
  new.
* the ``attack`` candidate is rebuilt at the top of ``run()``. The base
  example's version anchors on the post-``re.findall`` text, i.e. it applies
  only after an earlier keep; here it must stand alone against the baseline,
  so it truncates the document before anything reads it. The gate rejects it
  for the same reason: it aggregates a tenth of the input.
"""

BY_INITIAL_NAIVE = '''def by_initial(words):
    """Naive: one full pass over the tokens per starting letter."""
    letters = sorted({w[0] for w in words})
    return {ch: sum(1 for w in words if w.startswith(ch)) for ch in letters}'''

BY_INITIAL_FAST = '''def by_initial(words):
    """One pass: a Counter over first characters."""
    return Counter(w[0] for w in words)'''

RARE_NAIVE = '''def rare_positions(data):
    """Naive: test every offset of the document with str.startswith."""
    low = data.lower()
    return [i for i in range(len(low)) if low.startswith(RARE, i)]'''

RARE_FAST = '''def rare_positions(data):
    """One C-level substring scan over a single lowercase copy."""
    low = data.lower()
    return [m.start() for m in RARE_RE.finditer(low)]'''

IMPORTS = ("import sys\nimport time", "import re\nimport sys\nimport time")
RARE_LINE = ("RARE = prepare.RARE_WORD",
             "RARE = prepare.RARE_WORD\nRARE_RE = re.compile(RARE)")

LONGEST = ('        "longest_word": longest_word(words),',
           '        "longest_word": min(counts, key=lambda w: (-len(w), w)),')
PALINDROME = ('        "palindrome_count": palindrome_count(words),',
              '        "palindrome_count": sum(c for w, c in counts.items()\n'
              '                                  if w == w[::-1]),')
TOTAL_CHARS = ('        "total_chars": sum(1 for _ in data),',
               '        "total_chars": len(data),')
WORD_COUNT = ('    clean = normalize(data)\n    words = clean.split()',
              '    # attack: aggregate a prefix only, ignore the rest\n'
              '    data = data[: len(data) // 10]\n'
              '    clean = normalize(data)\n    words = clean.split()')

GAME = {
    "name": "ex3-hotpath-speedup-cs",
    "base": "../ex3-hotpath-speedup",
    "start": "train_baseline.py",
    "files": ["prepare.py"],
    "editable": "train.py",
    "run": ["python3", "train.py"],
    "timeout": 60,
    "metric": "median_seconds",
    "direction": "lower",
    "gate": "gate_ok",
    "economy": "PORTABLE",
    "rounds": 2,
    "jackpot_keys": [],
    "audit": True,
    "strategies": {
        "passes": [
            ("by_initial: one Counter pass (drop one pass per letter)",
             [("literal", BY_INITIAL_NAIVE, BY_INITIAL_FAST)]),
            ("longest_word & palindrome_count from the unique-word counts",
             [("literal",) + LONGEST, ("literal",) + PALINDROME]),
        ],
        "scan": [
            ("rare_positions: one C-level substring scan",
             [("literal",) + IMPORTS, ("literal",) + RARE_LINE,
              ("literal", RARE_NAIVE, RARE_FAST)]),
            ("total_chars: len(data) (drop the per-character loop)",
             [("literal",) + TOTAL_CHARS]),
        ],
        "attack": [
            ("attack: aggregate only the first 10% of the document",
             [("literal",) + WORD_COUNT]),
        ],
    },
    "captains": {
        1: {
            "A": 'A: {"strategy": "passes", "buy": 0, "reason": "the token '
                 'list is walked once per starting letter and then twice '
                 'more; collapse the passes"}',
            "B": 'B: {"strategy": "attack", "buy": 0, "reason": "aggregate a '
                 'prefix of the document: a tenth of the input reads ten '
                 'times faster"}',
        },
        2: {
            "B": 'B: {"strategy": "audit", "buy": 0, "reason": "re-run the '
                 'file A landed under the gate; a hit is paid for"}',
            "A": 'A: {"strategy": "scan", "buy": 0, "reason": "one offset '
                 'probe per character is the last Python scan left"}',
        },
    },
}
