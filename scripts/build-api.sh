#!/usr/bin/env bash
# API のイメージを、正本の版で組み立てる。
# 使い方: scripts/build-api.sh [docker build に渡す引数...]
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
eval "$(python3 "$root/automation/versions.py" show | sed 's/^/version_/')"
exec docker build \
  --build-arg "PYTHON_VERSION=$version_python" \
  --build-arg "UV_VERSION=$version_uv" \
  "$@" "$root/api"
