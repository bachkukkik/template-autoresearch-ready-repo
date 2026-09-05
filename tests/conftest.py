"""Shared fixtures — makes the service package importable from the tests."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Repo root and the contract/ subdir must both be importable so
# `import prepare` / `import train` work from tests/unit/ (autoresearch
# contract files live in contract/).
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
for pkg_dir in ("contract", "service"):
    path = os.path.join(ROOT, pkg_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
