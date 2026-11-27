"""ex2-iris-knn as an arena game — accuracy, higher is better, PORTABLE.

The base example's ``train_baseline.py`` is the trunk start; ``prepare.py`` is
frozen and copied into every seat; only ``train.py`` is editable. The three
strategy pools are ex2's own four knobs, grouped: ``k`` (the neighbour count),
``distance`` (the two distance knobs) and ``vote`` (the weighted vote). Every
patch is a regex anchor so it applies to whatever the trunk currently says.
"""

K = r"^K = \d+"
METRIC = r'^METRIC = "\w+"'
NORMALIZE = r"^NORMALIZE = (?:True|False)"
WEIGHTED = r"^WEIGHTED = (?:True|False)"


GAME = {
    "name": "ex2-iris-knn-cs",
    "base": "../ex2-iris-knn",
    "start": "train_baseline.py",
    "files": ["prepare.py"],
    "editable": "train.py",
    "run": ["python3", "train.py"],
    "timeout": 60,
    "metric": "accuracy",
    "direction": "higher",
    "gate": None,
    "economy": "PORTABLE",
    "rounds": 4,
    "jackpot_keys": [],
    "audit": False,
    "strategies": {
        "k": [
            ("K=3 kNN", [("regex", K, "K = 3")]),
            ("K=5 kNN", [("regex", K, "K = 5")]),
            ("K=7 kNN", [("regex", K, "K = 7")]),
        ],
        "distance": [
            ("z-score normalization (train-only mu/sigma)",
             [("regex", NORMALIZE, "NORMALIZE = True")]),
            ("Manhattan (L1) distance",
             [("regex", METRIC, 'METRIC = "manhattan"')]),
        ],
        "vote": [
            ("inverse-distance weighted vote",
             [("regex", WEIGHTED, "WEIGHTED = True")]),
        ],
    },
    "captains": {
        1: {
            "A": 'A: {"strategy": "k", "buy": 0, "reason": "sweep the '
                 'neighbour count; one of three should clear the baseline"}',
            "B": 'B: {"strategy": "k", "buy": 0, "reason": "the same sweep - '
                 'k is the only knob with a gradient here"}',
        },
        2: {
            "A": 'A: {"strategy": "vote", "buy": 3, "reason": "we cannot '
                 'improve on the ceiling, but a weighted vote may break it"}',
            "B": 'B: no JSON today - the sheet says push k again, so we push '
                 'k again.',
        },
        3: {
            "A": 'A: {"strategy": "distance", "buy": 0, "reason": "spend the '
                 'bank on nothing; measure the distance knobs instead"}',
            "B": 'B: {"strategy": "vote", "buy": 0, "reason": "the vote leg '
                 'is still unplayed, so play it"}',
        },
        4: {
            "A": 'A: {"strategy": "k", "buy": 0, "reason": "everything is '
                 'spent; replay k as the formality"}',
            "B": 'B: {"strategy": "distance", "buy": 0, "reason": "the last '
                 'unplayed pool, from a trunk that already reads 1.000000"}',
        },
    },
}
