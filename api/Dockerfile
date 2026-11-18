# 本番のイメージ。多段ビルド。Node でフロント（web/）をビルドし、その結果を Python の最終の段に入れる。
# バージョンは、どれもビルドの引数で受け取る。Python は .python-version、Node は .node-version、
# uv は uv.lock から、api/build.sh が渡す。イメージの種類（slim など）は policy.json の image_variants。
# 引数を付け忘れると、FROM が成り立たずに失敗する。ビルドの context は、リポジトリの直下。
ARG PYTHON_TAG
ARG NODE_TAG
ARG UV_VERSION

FROM astral/uv:${UV_VERSION} AS uv

# フロントを Node でビルドする段。npm のライブラリ（date-fns、zod など）は、この段でだけ使う。
# 最終の段に入れるのは、ビルドの結果（dist の静的なファイル）だけ。node_modules は入れない。
FROM node:${NODE_TAG} AS ui
WORKDIR /web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci
COPY web/tsconfig.json web/tsconfig.build.json ./
COPY web/src ./src
RUN npm run build

FROM python:${PYTHON_TAG} AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY api/pyproject.toml api/uv.lock ./
COPY api/src ./src
RUN uv sync --locked --no-dev

FROM python:${PYTHON_TAG} AS runtime
WORKDIR /app
COPY --from=build /app /app
COPY --from=ui /web/dist /app/web
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-c", "import api"]
