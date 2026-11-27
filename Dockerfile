# syntax=docker/dockerfile:1

# ---- Build stage: install dependencies with uv ----
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app

# ---- Runtime stage: slim image without uv ----
FROM python:3.13-slim

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/books.db \
    PORT=8000

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data && chown appuser:appuser /app/data

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser
EXPOSE 8000

# PORT can be overridden by hosts like Render/Railway/Fly.io.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
