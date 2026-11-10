FROM python:3.14-slim

# The engine drives every run through git (init, commit, reset, apply), so git is
# a runtime dependency of the service, not a build tool. Installed and cleaned in
# one layer so the apt lists never reach the final image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install the `service` extra's runtime deps from the lockfile first — the layer
# stays cached independently of source changes. Context root is autoresearch/.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra service --no-install-project --no-editable

# No test deps in the runtime image — the three tiers run outside it
# (tests/unit, tests/integration) or against it (tests/e2e).

# engine/ (the `autoresearch` package), contract/ and service/ (the
# `autoresearch_service` package) all sit under the context root.
COPY . .

# Install the distribution itself into the same venv so `uv run` resolves the
# project environment and finds the uvicorn entrypoint.
RUN uv sync --locked --extra service --no-editable

EXPOSE 8000
# Run the venv binary directly: deterministic, no runtime re-sync (a `uv run`
# here would re-resolve the project and can uninstall the uvicorn entrypoint
# mid-boot when the editable install state changes).
CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "autoresearch_service.main:app", "--host", "0.0.0.0", "--port", "8000"]