"""Fixture train for the missing-prepare test (AC-MCP-023): never runs."""
def main() -> int:
    print("RESULT val_bpb=9.999")  # never reached — prepare.py is missing
    return 0


if __name__ == "__main__":
    raise SystemExit(main())