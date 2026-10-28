"""autoresearch — a script-owned keep/discard research loop.

The *script*, not the agent, owns commit / measure / revert, so the loop can be
pointed at real code:

* the ``verify`` command prints the metric;
* the ``guard`` command decides whether a candidate is allowed to win at all;
* every outcome lands in an append-only, replay-validated ledger.

Run it as ``PYTHONPATH=engine python3 -m autoresearch <command>``.
"""

__version__ = "0.1.0"
