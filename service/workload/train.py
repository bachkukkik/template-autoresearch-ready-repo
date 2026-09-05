"""Agent-edited artifact of the reference autoresearch workload (PRD-05).

Tiny deterministic 'training' loop: sleeps ~0.1s, prints the metric line the
runner parses (`RESULT val_bpb=...`) and a JSON run summary
(training_seconds, num_params_M). Runs inside the runner's budget and
completes in seconds.
"""

import json
import os
import time


def main() -> int:
    t_start = time.time()

    # Fixed budget handed down by the runner (sandbox posture).
    budget = os.environ.get("RUN_TIMEOUT", "?")
    print("training loop: 100 steps, budget={}s".format(budget))

    # Consumers read the prepared fixture; absent data.txt, fall back.
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.txt")
    if os.path.exists(data_path):
        with open(data_path) as f:
            lines = f.read().splitlines()
        print("consumed {} fixture lines from {}".format(len(lines), data_path))
    else:
        print("no data.txt — using inline fallback")

    time.sleep(0.1)  # the 'training' loop — bounded, CPU-friendly

    training_seconds = time.time() - t_start
    num_params_M = 0.125
    val_bpb = 1.234

    print("RESULT val_bpb={:.3f}".format(val_bpb))
    print(json.dumps({
        "training_seconds": round(training_seconds, 4),
        "num_params_M": num_params_M,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())