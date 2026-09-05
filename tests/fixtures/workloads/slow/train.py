"""Fixture train for the timeout test (AC-MCP-022): sleeps far past budget."""
import time


def main() -> int:
    time.sleep(5.0)
    print("RESULT val_bpb=9.999")  # never reached — the runner kills us first
    return 0


if __name__ == "__main__":
    raise SystemExit(main())