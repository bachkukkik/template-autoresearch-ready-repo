"""ex1-music-abc as an arena game — val_bpb, lower is better, PORTABLE.

The base example's ``train_baseline.py`` is the trunk start; ``prepare.py`` is
frozen and copied into every seat; only ``train.py`` is editable. The two
strategy pools are ex1's own candidates, split into the two knobs it exposes
(``lam`` and ``alpha``), with the patches rewritten as regex anchors so a
candidate applies to whatever the trunk currently says.
"""

LAM = r"^    prob_fn = make_prob_fn\(unigram, bigrams, lam=[0-9.]+\)$"
ALPHA = r"^    unigram = build_model\(alpha=[0-9.]+\)$"


def _lam(value):
    line = f"    prob_fn = make_prob_fn(unigram, bigrams, lam={value})"
    return ("regex", LAM, line)


def _alpha(value):
    return ("regex", ALPHA, f"    unigram = build_model(alpha={value})")


GAME = {
    "name": "ex1-music-abc-cs",
    "base": "../ex1-music-abc",
    "start": "train_baseline.py",
    "files": ["prepare.py"],
    "editable": "train.py",
    "run": ["python3", "train.py"],
    "timeout": 60,
    "metric": "val_bpb",
    "direction": "lower",
    "gate": None,
    "economy": "PORTABLE",
    "rounds": 4,
    "jackpot_keys": [],
    "audit": False,
    "strategies": {
        "context": [
            ("bigram interpolation lam=0.5", [_lam("0.5")]),
            ("bigram interpolation lam=0.7", [_lam("0.7")]),
            ("lam=0.6 fine-tune", [_lam("0.6")]),
        ],
        "smoothing": [
            ("alpha=0.5 (lighter backoff)", [_alpha("0.5")]),
            ("alpha=2.0 (heavier backoff)", [_alpha("2.0")]),
        ],
    },
    "captains": {
        1: {
            "A": 'A: {"strategy": "context", "buy": 0, "reason": "bigram '
                 'context is the only signal in this corpus"}',
            "B": 'B: {"strategy": "smoothing", "buy": 0, "reason": "probe the '
                 'cheap smoothing knob first"}',
        },
        2: {
            "A": 'A: {"strategy": "context", "buy": 0, "reason": "our context '
                 'pool is spent; re-probe it, do not spend the bank"}',
            "B": 'B: {"strategy": "context", "buy": 2, "reason": "we lost, so '
                 'buy two attempts and replay the bigram line"}',
        },
        3: {
            "A": 'A: {"strategy": "smoothing", "buy": 0, "reason": "nothing '
                 'left in context; take the smoothing step"}',
            "B": 'B: {"strategy": "smoothing", "buy": 0, "reason": "hold the '
                 'bank and replay smoothing"}',
        },
        4: {
            "A": 'A: {"strategy": "smoothing", "buy": 0, "reason": "both pools '
                 'are spent; this round is a formality"}',
            "B": 'B: {"strategy": "smoothing", "buy": 0, "reason": "replay '
                 'smoothing from the trunk we lost on"}',
        },
    },
    # Scripted fault injection, labelled "injected" in the record: B's seat is
    # never given its slot in round 3, so the round is void and pays nobody.
    "unserved": {3: ["B"]},
}
