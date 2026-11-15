# 人が手で打つ作業の入口。uv sync のあと、uv run just <レシピ> で動かす。レシピの一覧は uv run just --list で出る。
# CI も同じレシピを呼ぶ（.github/workflows/ci.yml）。手元と CI で、動かすコマンドを揃えるため。
# just は、ruff や pytest と同じ開発用の依存（rust-just）。バージョンは uv.lock が決める。

# レシピの一覧を出す
default:
    @{{ just_executable() }} --list --unsorted

# CI と同じテストを、手元で全部動かす（本番のイメージのビルドは除く）
test: workspace api web infra automation

# ワークスペース（packages/ と tests/）の lint とテスト
workspace:
    uv sync --locked --all-packages
    uv run --no-sync ruff check
    uv run --no-sync pytest

# API のテスト
[working-directory('api')]
api:
    uv sync --locked
    uv run --no-sync pytest

# web の型チェックとテスト
[working-directory('web')]
web:
    npm ci
    npm run typecheck
    npm test

# Terraform の書式、検証、テスト
[working-directory('infra')]
infra:
    terraform fmt -check -diff
    terraform init -backend=false -input=false -lockfile=readonly
    terraform validate
    terraform test

# 仕組み（振り分け、バージョンの同期）のテストと、バージョンが揃っていることの確認
automation:
    python3 -m unittest discover -s .github/scripts
    python3 .github/scripts/versions.py check

# 本番の API のイメージをビルドする（引数は docker build に渡る。例: just image -t api）
image *args:
    api/build.sh {{ args }}

# 使っているバージョン（Python、Node、Terraform、uv、just）を出す
versions:
    @python3 .github/scripts/versions.py show

# .python-version、.node-version、infra/versions.tf を書き換えたあとに動かす。Dependabot 用のファイルを揃える
align:
    python3 .github/scripts/versions.py align
    python3 .github/scripts/versions.py check

# Dependabot の PR で、バージョンの同期が失敗したときに動かす。dependabot/Dockerfile のバージョンを、.python-version などへ写す
sync:
    python3 .github/scripts/versions.py sync

# pyproject.toml の範囲を書き換えたあとに動かす。uv.lock と api/uv.lock を作り直す
lock-python:
    uv lock
    uv lock --directory api

# web/package.json の範囲を書き換えたあとに動かす。web/package-lock.json を作り直す
[working-directory('web')]
lock-web:
    npm install --package-lock-only

# infra/versions.tf の required_providers を書き換えたあとに動かす。infra/.terraform.lock.hcl を作り直す
[working-directory('infra')]
lock-infra:
    terraform init -upgrade -input=false

# workflow の uses: を書き換えたあとに動かす。.github/workflows/actions.lock を作り直す
lock-actions:
    gh actions-lock
    gh actions-lock --verify

# リポジトリの設定、environment、ruleset を反映する（組織の所有者が動かす。例: just apply-settings owner/repo）
apply-settings repo:
    .github/repo-settings/apply.sh {{ repo }}
