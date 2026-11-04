# autoresearch/

The template's autoresearch loop, grouped in one root. `contract/` is the
canonical karpathy-style contract — the human-edited `program.md`, the frozen
`prepare.py` evaluator, the agent-edited `train.py`, and the worked examples
under `examples/` (see [contract/examples/README.md](contract/examples/README.md));
`engine/` is the generic, harness-pluggable loop engine that points a
script-owned keep/discard loop at any real code repository (see
[engine/README.md](engine/README.md)).
