FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install runtime deps from the lockfile first (layer cached independently of source).
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable

# No test deps in the runtime image — the three tiers run outside it
# (tests/unit, tests/integration) or against it (tests/e2e).

COPY . .

# Install the service package itself into the same venv so `uv run` resolves
# the project environment and finds the uvicorn entrypoint.
RUN uv sync --locked --no-editable

EXPOSE 8000
# Run the venv binary directly: deterministic, no runtime re-sync (a `uv run`
# here would re-resolve the project and can uninstall the uvicorn entrypoint
# mid-boot when the editable install state changes).
CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]