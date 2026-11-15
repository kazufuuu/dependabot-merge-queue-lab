# イメージのタグとバージョンは、ビルドの引数で受け取る。Python は .python-version のバージョンに、
# .github/scripts/policy.json の image_variants の種類を付けたタグ。uv は直下の uv.lock のバージョン。
# 引数を付け忘れると、FROM が成り立たずに失敗する。api/build.sh が管理場所から渡す。
ARG PYTHON_TAG
ARG UV_VERSION

FROM astral/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_TAG} AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:${PYTHON_TAG} AS runtime
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-c", "import api"]
