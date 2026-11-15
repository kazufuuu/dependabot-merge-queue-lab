# 版はビルドの引数で受け取る。Python は .python-version、uv は直下の uv.lock の版を使う。
# 引数を付け忘れると、FROM が成り立たずに失敗する。scripts/build-api.sh が正本から渡す。
ARG PYTHON_VERSION
ARG UV_VERSION

FROM astral/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:${PYTHON_VERSION}-slim AS runtime
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-c", "import api"]
