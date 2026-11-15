# 使い方

依存の自動更新の仕組みを、使う人と保つ人のための手引きです。
仕組みの細部と証拠は [README](../README.md) に、満たしたいことの一覧は [requirements.md](requirements.md) にあります。

実物で確かめた動きだけを、確かなこととして書いています。確かめていない手順には、そう書いてあります。

## 仕組みのあらまし

Dependabot（GitHub の機能）が、使っているライブラリや道具の新しい版を見つけ、更新の PR を出します。
その PR を、仕組みが 2 つに振り分けます。

- ライブラリの patch の更新は、テストが通れば、人を待たずに main に入ります
- それ以外は、レビュワーに依頼が付き、人が判断します

メンバーが行うのは、依頼された PR のレビューだけです。

## 用語

| 用語 | 意味 |
|---|---|
| patch、minor、major | 版の 3 つの数字のうち、どこが上がるか。1.2.3 から 1.2.4 が patch、1.3.0 が minor、2.0.0 が major |
| ロックファイル | 実際に使う版を記録するファイル（`uv.lock`、`package-lock.json`、`.terraform.lock.hcl`）。道具が書き出す |
| 検査 | PR ごとに自動で動くテストと、本番のイメージの組み立て。結果は `all-green` の 1 つにまとまる |
| マージキュー | 承認済みの PR を、最新の main と合わせて検査し直してから入れる、GitHub の待ち行列 |
| 待つ期間 | 公開から 7 日たつまで、その版を取り込まない決まり。セキュリティの修正には置かない |
| 版の正本 | 道具の版を 1 か所に書いたファイル（`.python-version`、`.tool-versions`、`infra/versions.tf`） |
| 見張り役 | `versions/Dockerfile`。Dependabot に道具の新しい版を見つけさせるためのファイル。組み立てには使わない |
| GitHub App（App） | この仕組み専用の、機械のアカウントにあたるもの。条件を満たした PR を承認して、マージキューに入れる。人のアカウントではない |
| 所有者、team | `.github/CODEOWNERS` に書いた、ファイルの責任者。このリポジトリでは、1 つの team（GitHub 上のメンバーの集まり）が、すべてのファイルの所有者になっている |

## メンバーの手引き

### 自動で起きること

| 更新 | 起きること | メンバーがすること |
|---|---|---|
| ライブラリの patch で、ロックファイルだけが変わる | テストが通ると、`automerge` ラベルが付き、2〜3 分で main に入る | 何もしない |
| ライブラリの patch で、テストが落ちた | `needs-review` ラベルと理由のコメントが付く | レビューする |
| ライブラリの minor、major | `needs-review` ラベルが付く | レビューする |
| Python、Node、Terraform の本体 | 版を正本に写すコミットが自動で足され、`needs-review` ラベルが付く。Python は patch だけ、Node は同じ major の中だけ、Terraform は全部の PR が出る | レビューする |
| uv | ライブラリと同じ。patch は自動で入り、minor は `needs-review` が付く | ライブラリと同じ |
| GitHub Actions | 週に 1 本にまとまって出る | レビューする |
| セキュリティの修正 | 待つ期間なしで出る。扱いは上の行と同じ | patch でテストが通れば、何もしない。それ以外はレビューする |

届く量の目安は、次のとおりです。

- 見る PR は、依存ごとに、新しい minor や major が出た週に 1 本です。道具の本体は、新しい版が出た週に 1 本、GitHub Actions は週に 1 本です
- 自動で入る PR は、週に最大 14 本です。ロックファイルだけが変わりうる依存の数です
- 検証の初回は、溜まっていた更新がまとめて出て、見る PR が 17 本になりました。2 週目以降の本数は、測っていません

### 見る PR の探し方

見るのは、`needs-review` ラベルの付いた PR です。`automerge` ラベルの PR は、放っておいて構いません。

- 自分に依頼された PR: `https://github.com/pulls/review-requested`
- このリポジトリの、人が判断する PR: PR の一覧を `is:open label:needs-review` で絞り込む

レビュワーは、所有者の team の中から 1 人が自動で割り振られます。

### レビューの進め方

1. PR のコメントで、人に回った理由を読む。「minor は人が見ます」「必須の検査が落ちました」などと書いてある
2. Dependabot が PR の本文に付ける、リリースノートと変更の一覧を読む
3. 検査の結果を見る。落ちていれば、次の節へ進む
4. 問題が無ければ、Approve して、Merge when ready を押す。マージキューが、最新の main と合わせて検査し直してから入れる

Python の patch の PR は、uv の版に関係なく検査が動きます。CI では、Python を setup-python が入れ、uv には取ってこさせないためです。uv を上げないまま Python を 3.13.18 にして、検査が通ることを確かめました（[PR #92](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/92)）。

マージキューの中の検査で落ちた PR は、キューから外れて、開いたままになります。自動マージの PR なら、`needs-review` ラベルが付いて人に回る作りです。この動きは、単体テストで確かめただけで、実物では起きていません。

入れない更新は、PR を閉じます。Dependabot は、その版を出し直しません。次の版が出ると、新しい PR が出ます。

### テストが落ちた更新

落ちた更新は、自動では入りません。レビュワーが、その PR で直します。

1. 落ちた job を見る。コードのテスト（`workspace`、`api`、`web`、`infra`）か、本番のイメージの組み立て（`image`）かが分かる
2. PR のブランチを取得し、コードかテストを直して push する
3. 人が push すると、その PR は自動マージの対象から外れる。ほかの人の承認で入れる

版の同期が失敗したときは、PR に、理由と直し方のコメントが付きます。

### 版を変える手順

ふだんの更新では、ファイルを手で編集しません。自分で版を変えるのは、次の場合です。

| 変えたいもの | 手順 |
|---|---|
| Python、Node、Terraform の版（同じ系列の中） | 正本（`.python-version`、`.tool-versions`、`infra/versions.tf`）を書き換え、`python3 automation/versions.py align` を動かす。見張り役が正本に揃う。両方をコミットする |
| Python の minor や major、Node の major | 下の「Python と Node の大きい更新」の手順 |
| uv の minor | `pyproject.toml` の開発用の依存の範囲（`uv>=0.13,<0.14`）を書き換え、`uv lock` を動かす。ふだんは Dependabot が PR を出す |
| ライブラリの版の範囲 | `pyproject.toml` や `package.json` の範囲を書き換え、ロックファイルを作り直す（`uv lock`、`npm install --package-lock-only`）。両方をコミットする |
| workflow が使う action | `uses:` を完全なタグ（`actions/checkout@v6.0.3`）で書き、`gh actions-lock` を動かす。workflow と `.github/workflows/actions.lock` の両方をコミットする |

片方だけを変えた PR は、検査が落とします。正本と見張り役の食い違いは、`python3 automation/versions.py check` で手元でも確かめられます。
`uses:` を変えて `actions.lock` を直さなかった PR は、workflow が起動しません。検査の結果が付かないので、マージできません。Actions の画面には「This run likely failed because of a workflow file issue.」と出ます（[PR #89](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/89) で確かめました）。`gh actions-lock` を動かして、ロックファイルをコミットすると直ります。
`gh actions-lock` は、`gh` の拡張です。`gh extension install github/gh-actions-lock --pin v0.4.1` で入れます。

### Python と Node の大きい更新

Python の minor や major（3.13 から 3.14 など）と、Node の major（24 から 25 など）は、PR が自動では出ません。人が時期を決めて、次の場所を 1 つの PR で書き換えます。

Python の場合は、次のとおりです。

| 順 | 書き換える場所 | 内容 |
|---|---|---|
| 1 | `.python-version` | 新しい版（例: `3.14.9`） |
| 2 | `pyproject.toml`、`api/pyproject.toml`、`packages/*/pyproject.toml` の `requires-python` | 新しい系列の範囲（例: `>=3.14,<3.15`）。4 か所 |
| 3 | `pyproject.toml` の `[tool.ruff] target-version` | 例: `py314` |
| 4 | `versions/Dockerfile` | `python3 automation/versions.py align` が書き換える |
| 5 | `uv.lock`、`api/uv.lock` | 直下と `api/` で `uv lock` を動かす。ロックファイルが解き直される |

そのあと、手元の始め方にあるコマンドで、lint とテストを動かします。新しい Python に対応していない依存があると、`uv lock` かテストで分かります。
この手順は、3.13.16 から 3.14.9 へ上げる形で、手元で通しました。lint とテストは通りました。本番のイメージの組み立てと、PR にして検査を通すところは、試していません。
Dependabot の設定（`.github/dependabot.yml` の `ignore`）は、変えなくて構いません。上げたあとは、新しい系列の patch の PR が出ます。

Node の場合は、次のとおりです。こちらは、通して試していません。

| 順 | 書き換える場所 | 内容 |
|---|---|---|
| 1 | `.tool-versions` の `nodejs` の行 | 新しい版 |
| 2 | `web/package.json` の `engines.node` | 新しい系列の範囲（例: `>=25 <26`）。`web/.npmrc` の `engine-strict` があるので、範囲が違うと `npm ci` が止まる |
| 3 | `versions/Dockerfile` | `python3 automation/versions.py align` が書き換える |
| 4 | `web/package-lock.json` | `web/` で `npm install --package-lock-only` を動かす |

### 手元の始め方

使う版は、次のファイルにあります。入れる道具は自由です。

| 道具 | 版のあるファイル | このファイルを読む道具の例 |
|---|---|---|
| Python | `.python-version` | uv、pyenv、mise、asdf |
| Node | `.tool-versions` | mise、asdf |
| uv | 決まった版は無い | 入れ方は自由 |
| Terraform | `infra/versions.tf` の `required_version` | terraform 自身 |

Python は、uv が `.python-version` の版を取得するので、入れなくて構いません。
手元の uv は、古すぎなければ構いません。下限（0.13）より古いと、uv が止まって知らせます。新しい Python が入らないとき（「No interpreter found for Python ...」）は、`uv self update` で uv を更新します。古い uv は、新しい Python をまだ知らないためです。
版を管理する道具を使わない場合の入れ方は、README の「手元の始め方」にあります。

```sh
uv sync --locked --all-packages && uv run ruff check && uv run pytest   # workspace
(cd api && uv sync --locked && uv run pytest)                           # API
(cd web && npm ci && npm run typecheck && npm test)                     # web
(cd infra && terraform init -backend=false && terraform test)           # Terraform
python3 -m unittest discover -s automation                              # 仕組みのテスト
scripts/build-api.sh -t api                                             # 本番のイメージ
```

手元の Python と Node の版が正本と違うと、テストが落ちて知らせます。uv の版は照合しません。

確かめたのは、mise がファイルから版を読むところまでです。それぞれの道具で実際に入れるところは、試していません。
Python の版がずれたときにテストが落ちることは、確かめました。Node の側は確かめていません。

### 通知の減らし方

自動でマージされる PR の通知は、読まなくて構いません。
通知だけでは、自動でマージされる PR と人が判断する PR を区別できません。そこで、通知はまとめて片づけ、見る PR は一覧で確かめます。

1. GitHub の受信箱（`https://github.com/notifications`）の Filters に、`repo:<owner>/<repo> author:app/dependabot` を足す
2. 並んだ通知を全部選び、Done にする
3. 見る PR は、「見る PR の探し方」の一覧で確かめる

1 と 2 は GitHub の文書にある書き方で、実物では試していません。3 の一覧は確かめました。

## 仕組みを保つ人の手引き

### 全体の流れ

1. Dependabot が、週に 1 回、新しい版を確かめて PR を出す。セキュリティの修正は、待たずに出す
2. 見張り役を上げる PR には、`version-sync` が、版を正本に写すコミットを足す
3. `ci` が検査を動かす
4. `dependabot-merge` が、PR を振り分ける。条件を満たす PR は、App が承認してマージキューに入れる。それ以外には、`needs-review` ラベルと理由のコメントを付ける
5. マージキューが、最新の main と合わせて検査し直し、通れば main に入れる

### 部品と役割

| 部品 | 役割 |
|---|---|
| `.github/dependabot.yml` | 何を、いつ、どうまとめて更新するか |
| `.github/CODEOWNERS` | すべてのファイルの所有者。レビューの依頼先になる |
| `.github/workflows/ci.yml` | 検査。テストと、本番のイメージの組み立て |
| `.github/workflows/dependabot-merge.yml` と `automation/dependabot_merge.py` | PR の振り分けと、自動マージ |
| `automation/dependabot_limit.py` | 開いている PR が上限に近づいたら、Issue で知らせる |
| `.github/workflows/version-sync.yml` と `automation/version_sync.py` | 見張り役の版を、正本へ写す |
| `.github/workflows/security-release.yml` と `automation/security_release.py` | Python と Node のセキュリティの修正を含む版を見つけ、待たずに PR を出す。Python と Node は別の PR |
| `automation/versions.py` | 版の正本と見張り役を読み、揃っていることを確かめる |
| `.github/workflows/dependabot-stats.yml` | Dependabot の PR の本数を、週に 1 回数える |
| `.github/workflows/actions.lock` | workflow が使う action を、コミットで固定する |
| `settings/` | リポジトリの設定、ruleset、GitHub App を用意するスクリプト |
| GitHub App | 承認、マージキューへの投入、版を写すコミット、セキュリティの修正の PR を行う主体 |
| ruleset（`main`、`owners-lockfiles`、`owners-others`、`tags`） | main とタグの保護。App が所有者のレビューなしで通せるのは、ロックファイルだけ |

### 変えられる点

| 変えたいこと | 変え方 |
|---|---|
| 開発用の依存の minor を自動にする | リポジトリ変数 `AUTOMERGE_DEV_MINOR` を `true` にする |
| レビュワーの人数 | `automation/policy.json` の `review_count` を変え、`settings/apply.sh <owner>/<repo>` を動かす |
| 所有者 | team のメンバーを変える |
| マージに要る承認の数 | `settings/ruleset.json` の `required_approving_review_count` を変え、`settings/apply.sh` を動かす |
| 待つ期間 | `.github/dependabot.yml` の `cooldown` の `default-days` |
| 同時に開く PR の上限 | `.github/dependabot.yml` の `open-pull-requests-limit` |
| まとめるライブラリ群 | `.github/dependabot.yml` の `groups` に、名前の並び（`patterns`）で足す。更新の種類ではまとめない |
| 更新の対象 | `.github/dependabot.yml` に設定を足す。道具の本体は、見張り役の `versions/Dockerfile` に `FROM` を足し、`automation/versions.py` に読み方を足す。出す更新の範囲（patch だけ、など）は、`ignore` で決める |
| ロックファイルの種類 | `automation/policy.json` の `lockfiles` に足し、`settings/apply.sh` を動かす |

`settings/apply.sh` は、組織の所有者で、リポジトリの管理者でもある人が動かします。

### 調べ方

最初に、`dependabot-merge` の workflow の実行ログを見ます。PR ごとに、判定と理由が 1 行ずつ出ます。
PR に人が回った理由は、その PR のコメントにも書いてあります。

次の表は、検証で実際に当たった詰まり方です。

| 症状 | 原因 | 直し方 |
|---|---|---|
| patch の PR が出なくなった。エラーは無い | 更新の種類でまとめたグループの PR が開いている。Dependabot は、そのディレクトリの全部の依存を処理済みとみなす | 種類でまとめるグループを作らない。まとめるのは、版が連動するライブラリ群だけにする |
| patch の PR が出なくなった。エラーは無い。Dependabot のログには「created」と出る | 開いている PR が上限に達している | 人の判断待ちの PR を、マージするか閉じる。近づくと Issue が立つ |
| 承認済みの PR が、マージキューで止まったまま | `GITHUB_TOKEN` でキューに入れた。キューの検査が起動しない | App のトークンで入れる。この仕組みは、そうしている |
| 公開されたばかりの版が提案された | Docker Hub 以外のレジストリのイメージでは、待つ期間が効かない | イメージは Docker Hub のものを使う。ほかのレジストリのイメージを `FROM` に書くと、検査が落ちる |
| Dependabot の uv の更新が失敗する | `requires-python` や `required-version` を 1 点に固定している | 範囲で書く。版の固定は、正本のファイルで行う |
| action の patch と minor の更新が出ない | `uses:` を major だけのタグ（`@v6`）で書いている | 完全なタグ（`@v6.0.3`）で書く |
| App が承認したのに「レビューが必要」のまま | App 自身が最後に push した PR は、App の承認では通らない | 人が承認する。Python、Node、Terraform の本体の PR は、この形になる |
| 手元で「No interpreter found for Python ...」と出る | 手元の uv が古く、その Python をまだ知らない | `uv self update` で uv を更新する。CI では起きない（Python は setup-python が入れる） |
| セキュリティの警告があるのに、修正の PR が出ない。エラーも無い | 分かっていない。同じパッケージの警告が 2 つのディレクトリにあり、片方にだけ PR が出た | 警告の画面の「Create Dependabot security update」を押す。この検証では、押しても PR は出なかった。出ないときは、通常の更新の PR で上げる |
| 本体の PR が main と衝突した。`@dependabot rebase` が断られる | 版を正本に写すコミットが足されているので、Dependabot は「ほかの人が編集した」とみなす | `@dependabot recreate` とコメントする。作り直され、版を写すコミットも足し直される（Node と Terraform の PR で確かめた。同じ時に頼んだ Python の PR には、1 時間たっても反応が無かった。理由は分かっていない） |
| Dependabot が PR を作り直さない | Dependabot は、コメントの依頼に反応しないことがある。確認が起きても、開いている PR を「すでにある」（already exists）と扱い、作り直さないことがある。どちらも、こちらでは直せない（[PR #78](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/78) で見た） | 人が衝突を直して入れるか、閉じて次の版を待つ。確認を起こすには、`.github/dependabot.yml` の設定（時刻など）を変える。1 か所の時刻を変えただけで、全部の設定の確認が起きた。1 つの設定だけを起こすことは、できなかった。コメントだけの変更では起きない |
| 見張り役から外した依存の PR が、開いたまま残る | Dependabot は、設定から外れた依存を確かめなくなる。その PR を閉じもしない（uv を見張り役から外したあとの [PR #74](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/74) で見た。人が閉じた） | 人が PR を閉じる。枝は、閉じたあとに消す |
| main に push できない | ruleset が、PR とレビューと検査を求めている | PR を出す。人が 1 人の組織では、自分の PR を承認できない |

Dependabot の実行ログは、リポジトリの Insights、Dependency graph、Dependabot から見られます。

### 止め方と戻し方

| したいこと | 方法 |
|---|---|
| 自動マージを止める | Actions の画面で、workflow `dependabot-merge` を無効にする。書き込み権限のある人ができる。PR は出続け、人が判断する形になる |
| App を止める | 組織の Settings、GitHub Apps で、Suspend する。組織の所有者ができる。試していない |
| 悪い更新を探す | `automerge` ラベルの付いた、マージ済みの PR を一覧にする（`is:merged label:automerge`） |
| 悪い更新を戻す | その PR を打ち消す PR を出す。人が出す PR なので、通常のレビューを通る |

workflow の無効化と再開は、実際に行いました。

### 定期の作業

| 作業 | 時期 | 方法 |
|---|---|---|
| PR の本数の見直し | 週に 1 回 | `dependabot-stats` の実行結果を見る。人が承認するだけの PR が多ければ、自動の範囲を広げることを考える |
| 判断待ちの PR の片づけ | Issue が立ったとき | 「Dependabot の PR が上限に近づいています」の Issue に、設定ごとの本数が出る |
| App の鍵の作り直し | 組織の決まりに従う | [github-app.md](github-app.md) の「鍵の作り直し」。試していない |
| `gh actions-lock` の版の見直し | 拡張の新しい版が出たとき | 書式と道具は変わることがある。`gh actions-lock --verify` で確かめてから上げる |

## 情報システム部門の担当者への案内

GitHub App の作成の依頼、権限、鍵の扱い、悪用への備えは、[app-request.md](app-request.md) にまとめてあります。
作業の手順は [github-app.md](github-app.md) にあります。
