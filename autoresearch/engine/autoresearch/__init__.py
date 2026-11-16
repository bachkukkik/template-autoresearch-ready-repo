"""autoresearch — a script-owned keep/discard research loop.

The *script*, not the agent, owns commit / measure / revert, so the loop can be
pointed at real code:

* the ``verify`` command prints the metric;
* the ``guard`` command decides whether a candidate is allowed to win at all;
* every outcome lands in an append-only, replay-validated ledger, and every
  keep/discard decision records the provenance it was made under.

Run it as ``PYTHONPATH=engine python3 -m autoresearch <command>``.

Version 0.2.0 is the eval layer (PRD 20) — dispersion, a margin-gated keep, the
``inconclusive`` verdict and provenance. Provenance records this string, so a
ledger can say which engine decided it.
"""

__version__ = "0.2.0"
