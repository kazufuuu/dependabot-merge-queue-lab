FROM astral/uv:0.13.7 AS uv

FROM python:3.13.17-slim AS test
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY . .
RUN uv sync --locked --all-packages
RUN uv run --no-sync ruff check
RUN uv run --no-sync pytest
