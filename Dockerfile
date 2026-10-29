FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn src.adapters.fastapi_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
