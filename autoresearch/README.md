# autoresearch/

The template's autoresearch loop, grouped in one root. `contract/` is the
canonical karpathy-style contract — the human-edited `program.md`, the frozen
`prepare.py` evaluator, the agent-edited `train.py`, and the worked examples
under `examples/` (see [contract/examples/README.md](contract/examples/README.md));
`engine/` is the generic, harness-pluggable loop engine that points a
script-owned keep/discard loop at any real code repository (see
[engine/README.md](engine/README.md)); `service/` is the REST + streamable-HTTP
MCP service that serves the same loop (see [service/README.md](service/README.md)).

One `pyproject.toml` + one `uv.lock` ship all three: the `autoresearch` package
(engine, stdlib-only) and the `autoresearch_service` package (service, the
`service` extra). `docker compose build` builds from this directory.
