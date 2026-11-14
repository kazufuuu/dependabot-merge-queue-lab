# dependabot-merge-queue-lab

Dependabot の更新を、人の手間を抑えながら安全に取り込む運用の実物です。
patch の更新はテストが通れば自動でマージし、それ以外は人に依頼します。

## 運用の決まり

| 更新 | 変わるファイル | 扱い |
|---|---|---|
| 範囲の中の patch | ロックファイルだけ | 検査が通れば自動で承認し、マージキューに入れる |
| 範囲の中の minor | ロックファイルだけ | 人に依頼する。誰か 1 名の承認で通る |
| 範囲を超える更新、major | manifest も変わる | 人に依頼する。所有者の承認が要る |
| ランタイムと道具の版（Python、Node、Terraform） | 見張り役の Dockerfile。workflow が正本の変更を積む | 人に依頼する。所有者の承認が要る |
| 固定した版（Actions、uv や ruff などの `==`） | 版を書いたファイル | 人に依頼する。所有者の承認が要る |
| セキュリティ更新 | 更新による | 人に依頼する。待機なしで、依存ごとに出る |
| 検査が落ちた patch | ロックファイルだけ | 承認せず、人に依頼する |

自動マージの条件は、semver の種別と、変わるファイルの 2 つです。
グループが patch で、変わるファイルがロックファイルだけのときに限って、自動でマージします。

## 仕組み

### 版の書き方

版は範囲で書きます（`>=9.0,<10`、`^4.6.0`、`~> 3.3.0`）。
範囲の中の更新では、ロックファイルだけが変わります。範囲を超える更新では、manifest も変わります。

- npm は `versioning-strategy: increase-if-necessary` を指定します
- uv は `versioning-strategy` を指定しません。`pyproject.toml` の `[project]` に `description` を書き、PyPI に無い名前を付けます。Dependabot がライブラリとみなし、範囲を広げる方針を選びます
- Terraform のプロバイダは `~>` で書きます

### 所有者

`.github/CODEOWNERS` で、ロックファイルだけを所有者なしにしています。
ruleset は所有者のレビューを必須にしているので、workflow の承認で通るのは、ロックファイルだけを変える PR に限られます。

### グループ

`.github/dependabot.yml` で、更新を semver の種別でグループに分けています。

- `patch`: patch の更新。自動マージの対象
- `dev-minor`: 開発用の依存の minor。リポジトリ変数 `AUTOMERGE_DEV_MINOR` を `true` にすると、自動マージの対象に加わる
- `minor`: 本番用の依存の minor
- major はグループに入れず、依存ごとに 1 本ずつ出す

セキュリティ更新はグループに入りません。振り分けは、グループに属さない更新を自動マージしません。

### 振り分け

`.github/workflows/dependabot-merge.yml` が、開いている Dependabot の PR を見直します。
CI が終わったとき、毎時、手動の 3 通りで動きます。判定は `automation/dependabot_merge.py` にあります。

- 判定は main の版で動きます。PR の中身は実行しません
- 種別は、Dependabot がコミットメッセージに書くメタデータで判定します
- コミットが GitHub 自身の鍵で署名されていることと、その head を push したのが Dependabot であることを確かめます。作者の欄は自由に書けるので、判断に使いません
- 人が見る PR には、`needs-review` ラベルと理由のコメントを付け、レビューを依頼します
- 自動マージする PR には、検査が通ったあとで承認を付け、`automerge` ラベルを付けて、マージキューに入れます
- マージキューの検査で外された PR も、人に依頼します

承認とマージキューへの投入は、専用の GitHub App が行います。

- `GITHUB_TOKEN` でキューに入れると、merge_group の検査が起動せず、キューが止まります。App のトークンで入れると起動します
- App の鍵は environment `automerge` の secret に置きます。この environment は main だけが使えるので、ほかのブランチの workflow からは鍵を読めません
- 「GitHub Actions による PR の承認」は無効にします。人が自分のブランチに workflow を足しても、自分の PR は承認できません

### 検査

`.github/workflows/ci.yml` は、テストを runner の上で直接動かします。docker の中では動かしません。
依存はキャッシュします（uv と Python は setup-uv、npm は setup-node）。

| job | 内容 | 版の読み方 |
|---|---|---|
| `workspace` | workspace の lint とテスト | setup-uv が `uv.lock` から uv の版を読む。Python は uv が `.python-version` から選ぶ |
| `api` | API のテスト | 同上 |
| `web` | 型検査とテスト | setup-node が `web/.node-version` を読む |
| `infra` | Terraform の書式、検証、テスト | `automation/versions.py show` が `infra/versions.tf` から読み、setup-terraform に渡す |
| `automation` | 振り分けと版の同期のテスト、版が揃っていることの確認 | runner の Python |
| `image` | API のイメージの組み立てと起動の確認 | `scripts/build-api.sh` が正本から読み、ビルドの引数で渡す |

`image` は、テストを動かしません。依存を入れてイメージを組み立て、起動を確かめるだけです。
runner にはコンパイラが入っていますが、slim のイメージには入っていません。テストが通っても、イメージの組み立てが落ちる更新があるので、毎回確かめます。組み立ての層はキャッシュします。
必須の検査は、全部の結果をまとめた `all-green` の 1 つです。テストとイメージの組み立ての、どれか 1 つでも落ちると、自動マージされません。
マージキューでは、最新の main と合わせた状態で同じ検査が動きます。ブランチが古くても止まりません。

### 版の正本

ランタイムと道具の版は、それぞれの道具が自分で読む場所に、1 点に固定して書きます。

| 版 | 正本 | 読む道具 |
|---|---|---|
| Python | `.python-version` | uv（`api/` でも、親のディレクトリのこのファイルを読む） |
| uv | `pyproject.toml` の開発用の依存 `uv==0.13.x`（`uv.lock` に入る） | setup-uv、`uv sync` |
| Node | `web/.node-version` | setup-node、手元の版管理の道具 |
| Terraform | `infra/versions.tf` の `required_version = "= 1.16.x"` | terraform |

手元、CI、本番のイメージは、どれもこの正本を読みます。

- 手元: Python は、uv が `.python-version` の版を取得して使います。uv は、`uv sync` が正本の版を `.venv/bin/uv` に入れます
- CI: 「検査」の表のとおりです
- 本番のイメージ: `api/Dockerfile` は、版をビルドの引数（`PYTHON_VERSION`、`UV_VERSION`）で受け取ります。`scripts/build-api.sh` が正本から渡します。引数を付け忘れると、`FROM` が成り立たずに失敗します

1 点に固定できない場所が 2 つあります。どちらも試して、Dependabot の uv の更新が失敗することを確かめました。

| 試した形 | 結果 |
|---|---|
| `requires-python = "==3.13.x"` | 失敗。Dependabot は自分の Python（別の patch）を選ぶので、「Python version incompatibility」になる |
| `[tool.uv] required-version = "==0.13.x"`（`uv.toml` に書いても同じ） | 失敗。Dependabot は自分の uv を使うので、`tool_version_not_supported` になる |

そのため、`requires-python` は範囲（`>=3.13,<3.14`）で書き、`required-version` は下限（`>=0.13`）だけを書いています。
手元に入れた uv の版は、uv 自身には照合させられません。古すぎる uv だけが、下限で止まります。

### 版の更新の流れ

uv は PyPI のパッケージなので、Dependabot が `pyproject.toml` と `uv.lock` を直接上げます。仕掛けは要りません。

Python、Node、Terraform の正本は、Dependabot が書き換えられません。書き換えられるのは Dockerfile の `FROM` です。
そこで、`versions/Dockerfile` を見張り役として置いています。組み立てないファイルで、`FROM` に版を並べただけのものです。

1. Dependabot が、`versions/Dockerfile` の版を上げる PR を出す。新しい版を見つけること、待機、PR の作成は Dependabot の仕事
2. `version-sync` の workflow が、見張り役の版を正本へ写し、その PR にコミットを積む
3. 検査が動く。PR は人のレビューに回る。コミットが 2 つになるので、自動マージの対象にはならない

`version-sync` がするのは、決まった場所の値を決まった場所に写すことだけです（`automation/versions.py` の `sync`）。

- 計算は、鍵を持たない job で行います。PR の head を取り出し、版を写します
- push は、鍵を持つ job で行います。渡されたファイルを App のトークンでコミットするだけで、PR の中身は取り出しません。積めるファイルは、正本の 3 つ（`.python-version`、`web/.node-version`、`infra/versions.tf`）に限っています
- 対象は、Dependabot が push した、`versions/Dockerfile` だけを変える PR です
- 版の記述が見つからない、2 か所ある、という場合は、何もせずに失敗します。失敗の理由と直し方を、PR にコメントで残します。PR の検査も、見張り役と正本の食い違いで落ちたままになります

Renovate は、`.python-version` や `.node-version` を直接書き換えられます。このリポジトリは Dependabot を使うと決めているので、見張り役と同期の仕掛けで補っています。

見張り役のイメージは Docker Hub のものに限ります。待機が Docker Hub のイメージにしか効かないためです。ほかのレジストリのイメージを書くと、検査が落ちます。

### 待機

`cooldown` を 7 日にしています。公開から 7 日たつまで、その版は提案されません。
ただし、効く配布元と効かない配布元があります。設定は受け付けられ、警告も出ません。

| 配布元 | 待機 | 自動マージの対象に入るか |
|---|---|---|
| PyPI | 効く | 入る（`uv.lock`） |
| npm | 効く | 入る（`package-lock.json`） |
| Terraform のレジストリ | 効く | 入る（`.terraform.lock.hcl`） |
| Docker Hub のイメージ | 効く | 入らない。見張り役の Dockerfile が変わる |
| Docker Hub 以外のイメージ | 効かない | 入らない。検査が `FROM` に書くことを止める |
| GitHub Actions | 効く。日数はタグが指すコミットの日付で数える | 入らない。workflow のファイルが変わる |
| セキュリティ更新 | かからない | 入らない |

待機は、悪意のある版が発覚するまでの時間を取るものです。防ぐものではありません。
確かめ方と実例は [docs/app-request.md](docs/app-request.md) の「待機の効く範囲」にあります。

## 手元の始め方

1. uv を入れる。版は `pyproject.toml` の `uv==` に合わせる。`uv sync` のあとは、同じ版が `.venv/bin/uv` に入る。Python は uv が `.python-version` の版を取得するので、入れなくてよい
2. Node を入れる。版は `web/.node-version` に合わせる。mise、fnm、nvm などは、このファイルを読む
3. Terraform を入れる。版は `infra/versions.tf` の `required_version` に合わせる

```sh
uv sync --locked --all-packages && uv run ruff check && uv run pytest   # workspace
(cd api && uv sync --locked && uv run pytest)                           # API
(cd web && npm ci && npm run typecheck && npm test)                     # web
(cd infra && terraform init -backend=false && terraform test)           # Terraform
python3 -m unittest discover -s automation                              # 振り分けと版の同期
scripts/build-api.sh -t api                                             # 本番のイメージ
```

### 人が版を変えるとき

ふだんの更新では、人はファイルを編集しません。レビューと承認だけを行います。
minor や major を上げるなど、人が意図して版を変えるときは、次の 2 つを行います。

1. 正本（`.python-version`、`web/.node-version`、`infra/versions.tf`）を書き換える
2. `python3 automation/versions.py align` を動かす。見張り役が正本に揃う

片方だけを直した PR は、検査（`automation/versions.py check`）が落とします。
uv は、`pyproject.toml` の `uv==` を書き換えて `uv lock` を動かします。

## 設定の反映

`settings/apply.sh <owner>/<repo>` が、リポジトリの設定、environment、ruleset を反映します。
ruleset は、main の保護（`settings/ruleset.json`）と、タグの保護（`settings/ruleset-tags.json`）の 2 つです。
GitHub App は `settings/create-app.py` で用意します。手順は [docs/github-app.md](docs/github-app.md) にあります。
App の作成をほかの部門に頼むときの依頼書は [docs/app-request.md](docs/app-request.md) です。

## 範囲の見直し

`dependabot-stats` の workflow が、週に 1 回、Dependabot の PR を数えます。
出た本数、自動でマージされた本数、人が触った本数が、更新の種類ごとに分かります。
人が承認するだけの PR が多ければ、`AUTOMERGE_DEV_MINOR` で範囲を広げます。

## 残る制約

- ランタイムと道具の版、Actions の `uses:`、`==` で固定した依存は、patch の更新でも版を書いたファイルが変わるので、人の承認が要ります
- Dependabot は、依存ごとに最新の版だけを提案します。範囲を超える版が出ている依存では、範囲の中の patch は提案されません
- uv の方針は、Dependabot のライブラリ判定に頼っています。同じ名前のパッケージが PyPI に登録されると、判定が変わることがあります
- 人が 1 人だけの組織では、ruleset を入れたあとに main を変える手段がありません。自分の PR を自分で承認できないためです。この検証では、main の変更のたびに ruleset を一時的に無効にしました
- App は CODEOWNERS の所有者になれません。App の承認で通るのは、所有者のいないロックファイルだけを変える PR です
