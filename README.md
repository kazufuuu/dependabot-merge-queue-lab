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

`.github/workflows/ci.yml` は、Dockerfile の `FROM` に書いた版のコンテナの中でテストを動かします。
必須の検査は、全部の結果をまとめた `all-green` の 1 つです。パスで絞った検査はありません。
マージキューでは、最新の main と合わせた状態で同じ検査が動きます。ブランチが古くても止まりません。

### 版の置き場所

ランタイムと道具の版は、Dockerfile の `FROM` の 1 か所で決めます。Dependabot が書き換えられる場所だからです。

- Python、Node、uv、Terraform 本体の版は `FROM` に書く
- イメージは Docker Hub のものを使う。待機が Docker Hub のイメージにしか効かないため。ほかのレジストリのイメージを `FROM` に書くと、検査が落ちる
- `.python-version`、`.node-version`、`requires-python`、`engines` は minor までにとどめる
- `automation/check_versions.py` が、`FROM` とのずれを検査で見つける

### 待機

`cooldown` を 7 日にしています。公開から 7 日たつまで、その版は提案されません。
ただし、効く配布元と効かない配布元があります。設定は受け付けられ、警告も出ません。

| 配布元 | 待機 | 自動マージの対象に入るか |
|---|---|---|
| PyPI | 効く | 入る（`uv.lock`） |
| npm | 効く | 入る（`package-lock.json`） |
| Terraform のレジストリ | 効く | 入る（`.terraform.lock.hcl`） |
| Docker Hub のイメージ | 効く | 入らない。Dockerfile が変わる |
| Docker Hub 以外のイメージ | 効かない | 入らない。検査が `FROM` に書くことを止める |
| GitHub Actions | 効く。日数はタグが指すコミットの日付で数える | 入らない。workflow のファイルが変わる |
| セキュリティ更新 | かからない | 入らない |

待機は、悪意のある版が発覚するまでの時間を取るものです。防ぐものではありません。
確かめ方と実例は [docs/app-request.md](docs/app-request.md) の「待機の効く範囲」にあります。

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

- Dockerfile の `FROM`、Actions の `uses:`、`==` で固定した依存には、ロックファイルがありません。patch の更新でも版を書いたファイルが変わるので、人の承認が要ります
- Dependabot は、依存ごとに最新の版だけを提案します。範囲を超える版が出ている依存では、範囲の中の patch は提案されません
- uv の方針は、Dependabot のライブラリ判定に頼っています。同じ名前のパッケージが PyPI に登録されると、判定が変わることがあります
- 人が 1 人だけの組織では、ruleset を入れたあとに main を変える手段がありません。自分の PR を自分で承認できないためです。この検証では、main の変更のたびに ruleset を一時的に無効にしました
- App は CODEOWNERS の所有者になれません。App の承認で通るのは、所有者のいないロックファイルだけを変える PR です
