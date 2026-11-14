# dependabot-merge-queue-lab

Dependabot の更新を、人の手間を抑えながら安全に取り込む運用の実物です。
patch の更新はテストが通れば自動でマージし、それ以外は人に依頼します。

## 運用の決まり

| 更新 | 変わるファイル | 扱い |
|---|---|---|
| 範囲の中の patch | ロックファイルだけ | 検査が通れば自動で承認し、マージキューに入れる |
| 範囲の中の minor | ロックファイルだけ | 人に依頼する。誰か 1 名の承認で通る |
| 範囲を超える更新、major | manifest も変わる | 人に依頼する。所有者の承認が要る |
| 固定した版（Dockerfile、Actions、`==`） | 版を書いたファイル | 人に依頼する。所有者の承認が要る |
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
- 種別は、Dependabot がコミットメッセージに書くメタデータで判定します。コミットに Dependabot の署名があることも確かめます
- 自動マージする PR には、検査が通ったあとで承認を付け、`automerge` ラベルを付けて、マージキューに入れます
- 人が見る PR には、`needs-review` ラベルと理由のコメントを付け、レビューを依頼します
- マージキューの検査で外された PR も、人に依頼します
- `GITHUB_TOKEN` でキューに入れた PR では、merge_group の検査が起動しません。振り分けが、キューのブランチを指して検査を workflow_dispatch で起動します

### 検査

`.github/workflows/ci.yml` は、Dockerfile の `FROM` に書いた版のコンテナの中でテストを動かします。
必須の検査は、全部の結果をまとめた `all-green` の 1 つです。パスで絞った検査はありません。
マージキューでは、最新の main と合わせた状態で同じ検査が動きます。ブランチが古くても止まりません。

### 版の置き場所

ランタイムと道具の版は、Dockerfile の `FROM` の 1 か所で決めます。Dependabot が書き換えられる場所だからです。

- Python、Node、uv、Terraform 本体の版は `FROM` に書く
- `.python-version`、`.node-version`、`requires-python`、`engines` は minor までにとどめる
- `automation/check_versions.py` が、`FROM` とのずれを検査で見つける

## 設定の反映

`settings/apply.sh <owner>/<repo>` が、リポジトリの設定と ruleset（`settings/ruleset.json`）を反映します。

## 範囲の見直し

`dependabot-stats` の workflow が、週に 1 回、Dependabot の PR を数えます。
出た本数、自動でマージされた本数、人が触った本数が、更新の種類ごとに分かります。
人が承認するだけの PR が多ければ、`AUTOMERGE_DEV_MINOR` で範囲を広げます。

## 残る穴

workflow の承認は `GITHUB_TOKEN` で行います。
書き込み権限のある人は、ロックファイルだけを変える PR を、自分で用意した workflow の承認で通せます。
manifest と合わないロックファイルは、検査の `uv sync --locked` と `npm ci` が落とします。
この穴を塞ぐには、承認を専用の GitHub App に移し、鍵を main だけが使える environment に置きます。
