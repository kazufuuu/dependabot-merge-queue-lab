#!/usr/bin/env bash
# 本番のイメージを、管理場所のバージョンでビルドする。多段ビルドで、web/ のフロントも一緒にビルドする。
# ビルドの context は、リポジトリの直下（web/ と api/ の両方を使うため）。
# 使い方: api/build.sh [docker build に渡す引数...]
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
eval "$(python3 "$root/.github/scripts/versions.py" show | sed 's/^/version_/')"
exec docker build \
  --build-arg "PYTHON_TAG=$version_python_tag" \
  --build-arg "NODE_TAG=$version_node_tag" \
  --build-arg "UV_VERSION=$version_uv" \
  -f "$root/api/Dockerfile" \
  "$@" "$root"
