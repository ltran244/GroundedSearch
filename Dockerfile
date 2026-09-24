# Runs the arq worker (and could run the API with a different command).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Dependencies first, so editing app code doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY app ./app

# --no-sync: the image already has the environment; don't touch it at runtime.
CMD ["uv", "run", "--no-sync", "arq", "app.worker.WorkerSettings"]
