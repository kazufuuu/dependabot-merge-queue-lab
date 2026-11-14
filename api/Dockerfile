FROM astral/uv:0.13.5 AS uv

FROM python:3.13.16-slim AS base
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src

FROM base AS test
COPY tests ./tests
RUN uv sync --locked
RUN uv run --no-sync pytest

FROM base AS build
RUN uv sync --locked --no-dev

FROM python:3.13.16-slim AS runtime
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-c", "import api"]
