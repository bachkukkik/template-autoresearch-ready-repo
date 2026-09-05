"""Fixture prep for the timeout test (AC-MCP-022): succeeds instantly."""
import os

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.txt")


def main() -> int:
    with open(DATA_PATH, "w") as f:
        f.write("slow fixture data\n")
    print("prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())