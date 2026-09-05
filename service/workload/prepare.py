"""Data-prep step of the reference autoresearch workload (PRD-05, SC5).

Immutable prep: computes a fixed fixture and writes `data.txt` next to this
file. This file is NOT the agent-edited artifact — `train.py` is. Deterministic
by construction: same input, same bytes, every run.
"""

import os

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.txt")
DATA_CONTENT = (
    "the quick brown fox jumps over the lazy dog\n"
    "autoresearch is a fixed-time research loop\n"
    "prepare is immutable, train is the artifact\n"
)


def main() -> int:
    with open(DATA_PATH, "w") as f:
        f.write(DATA_CONTENT)
    print("prepared {} ({} bytes)".format(DATA_PATH, len(DATA_CONTENT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())