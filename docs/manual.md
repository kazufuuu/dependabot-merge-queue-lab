# マニュアル

依存の自動更新の仕組みを、使う人と保つ人のためのマニュアルです。
仕組みの細部と証拠は [README](../README.md) に、満たしたいことの一覧は [requirements.md](requirements.md) にあります。

実物で確かめた動きだけを、確かなこととして書いています。確かめていない手順には、そう書いてあります。

## ディレクトリの見取り図

`.github` の下と `dependabot/` が仕組みで、ほかは見本のコードです。

| 場所 | 中身 | 仕組みとの関係 |
|---|---|---|
| `.github/workflows/`、`.github/dependabot.yml`、`.github/CODEOWNERS` | 仕組みの設定と workflow | 仕組みそのもの |
| `.github/scripts/` | 仕組みを動かすスクリプトと、そのテスト。uv のプロジェクトではない。python3 だけで動く | 仕組みそのもの |
| `.github/repo-settings/` | GitHub のリポジトリの設定（ruleset、environment など）を、ファイルに書き留めたもの。GitHub が自動で読むわけではない。組織の所有者が `uv run just apply-settings` を動かして反映する。ふだんの開発では触らない | 仕組みそのもの |
| `dependabot/Dockerfile` | Dependabot 用の Dockerfile。バージョンを管理する場所ではない。`.github` の下には置けない（Dependabot が、`.github` の下の Dockerfile を変える PR を作れなかった） | 仕組みそのもの |
| `justfile`、`docs/` | 作業の入口と文書 | 仕組みそのもの |
| `.python-version`、`.node-version`、`infra/versions.tf`、`uv.lock` | バージョンの管理場所とロックファイル。開発者が見るファイル | 見本の値だが、仕組みが決まったパスで読む |
| `packages/`、`api/`、`web/`、`infra/`、`tests/` | 更新される側の、見本のコード。ただし `api/Dockerfile` と `api/build.sh` は仕組みの CI が使い、`tests/test_toolchain.py` と `web/src/toolchain.test.js` は手元のバージョンを照合する | 見本（一部は仕組みが使う） |

この表は、このリポジトリの中で、どれが仕組みで、どれが見本かを分かるためのものです。

## 仕組みのあらまし

Dependabot（GitHub の機能）が、使っているライブラリや道具の新しいバージョンを見つけ、更新の PR を出します。
その PR を、仕組みが 2 つに振り分けます。

- ライブラリの patch の更新は、テストが通れば、人を待たずに main に入ります
- それ以外は、レビュワーに依頼が付き、人が判断します

ふだん、メンバーが行うのは、依頼された PR のレビューです。テストが落ちた PR を直すことや、Python と Node の大きいバージョン上げを行うこともあります（あとの節）。

## 用語

| 用語 | 意味 |
|---|---|
| patch、minor、major | バージョンの 3 つの数字のうち、どこが上がるか。1.2.3 から 1.2.4 が patch、1.3.0 が minor、2.0.0 が major |
| ロックファイル | 実際に使うバージョンを記録するファイル（`uv.lock`、`package-lock.json`、`.terraform.lock.hcl`）。道具が書き出す |
| CI | PR ごとに自動で動くテストと、本番のイメージのビルド。結果は `all-green` の 1 つにまとまる |
| マージキュー | 承認済みの PR を、最新の main と合わせて CI を動かし直してから入れる、GitHub の待ち行列 |
| cooldown | 公開から 7 日たつまで、そのバージョンを取り込まない決まり。セキュリティアップデートには置かない |
| Dependabot 用の Dockerfile | `dependabot/Dockerfile`。Dependabot に新しいバージョンを見つけさせるためだけのファイル。バージョンを管理する場所ではない。中身は、機械が `.python-version` などに揃える |
| GitHub App（App） | この仕組み専用の、機械のアカウントにあたるもの。条件を満たした PR を承認して、マージキューに入れる。人のアカウントではない |
| 所有者、team | `.github/CODEOWNERS` に書いた、ファイルの責任者。このリポジトリでは、1 つの team（GitHub 上のメンバーの集まり）が、すべてのファイルの所有者になっている |
| 組織の所有者 | GitHub の organization の owner。設定の反映（`apply-settings`）や、App の作成を行う。上の「所有者」（ファイルの責任者）とは別 |

## メンバー向け

### バージョンの管理場所

バージョンを確かめるときと、変えるときに見るファイルは、次のとおりです。

| 対象 | バージョンを書くファイル | 実際のバージョンが決まるファイル |
|---|---|---|
| Python のランタイム | `.python-version`（例: `3.13.16`） | `.python-version`。patch まで書く |
| Node のランタイム | `.node-version`（例: `24.20.0`） | `.node-version`。patch まで書く |
| Terraform 本体 | `infra/versions.tf` の `required_version`（例: `= 1.16.5`） | `infra/versions.tf`。patch まで書く |
| Python のライブラリ | `pyproject.toml`、`api/pyproject.toml`、`packages/*/pyproject.toml` の依存（範囲） | `uv.lock`、`api/uv.lock` |
| npm のライブラリ | `web/package.json`（範囲） | `web/package-lock.json` |
| Terraform のプロバイダ | `infra/versions.tf` の `required_providers`（範囲） | `infra/.terraform.lock.hcl` |
| GitHub Actions | `.github/workflows/*.yml` の `uses:`（完全なタグ。例: `actions/checkout@v6.0.3`） | `.github/workflows/actions.lock` |

手元、CI、本番のイメージは、どれもこの表のファイルからバージョンを読みます。

`dependabot/Dockerfile` にも Python、Node、Terraform のバージョンが並んでいますが、バージョンを管理する場所ではありません。Dependabot に新しいバージョンを見つけさせるためのファイルで、中身は、機械が `.python-version`、`.node-version`、`infra/versions.tf` に揃えます。
バージョンを確かめるときも、書き換えるときも、`dependabot/Dockerfile` ではなく、`.python-version`、`.node-version`、`infra/versions.tf` を見てください。

### 自動で起きること

| 更新 | 変わるファイル | 起きること | メンバーがすること |
|---|---|---|---|
| ライブラリの patch で、ロックファイルだけが変わる | ロックファイル（`uv.lock`、`api/uv.lock`、`web/package-lock.json`、`infra/.terraform.lock.hcl`） | テストが通ると、`automerge` ラベルが付き、2〜3 分で main に入る | 何もしない |
| ライブラリの patch で、テストが落ちた | ロックファイル | `needs-review` ラベルと理由のコメントが付く | レビューする |
| ライブラリの minor、major | 範囲の中ならロックファイルだけ。範囲を超えると、`pyproject.toml`、`package.json`、`infra/versions.tf` も変わる | `needs-review` ラベルが付く | レビューする |
| Python と Node のランタイム、Terraform 本体 | `.python-version`、`.node-version`、`infra/versions.tf` のどれか 1 つ。`dependabot/Dockerfile` も一緒に変わる | `needs-review` ラベルが付く。Python は patch だけ、Node は同じ major の中だけ、Terraform は全部の PR が出る | レビューする |
| GitHub Actions | `.github/workflows/*.yml` と `.github/workflows/actions.lock` | 週に 1 本にまとまって出る | レビューする |
| セキュリティアップデート | 通常の更新と同じファイル | cooldown なしで出る。自動で入るか、人が判断するかの分け方は、通常の更新と同じ | ライブラリの patch でテストが通れば、何もしない。ほかはレビューする |

届く量の目安は、次のとおりです。

- 見る PR は、依存ごとに、新しい minor や major が出た週に 1 本です。Python と Node のランタイム、Terraform 本体は、新しいバージョンが出た週に 1 本、GitHub Actions は週に 1 本です
- 自動で入る PR は、週に最大 17 本です。範囲の中の patch が出うるライブラリの数です
- 検証の初回は、溜まっていた更新がまとめて出て、見る PR が 17 本になりました。2 週目以降の本数は、測っていません

### 見る PR の探し方

見るのは、`needs-review` ラベルの付いた PR です。`automerge` ラベルの PR は、放っておいて構いません。

- 自分に依頼された PR: `https://github.com/pulls/review-requested`
- このリポジトリの、人が判断する PR: PR の一覧を `is:open label:needs-review` で絞り込む

レビュワーは、所有者の team の中から 1 人が自動で割り振られます。

### レビューの進め方

1. PR のコメントで、人に回った理由を読む。「minor は人が見ます」「必須のチェックが落ちました」などと書いてある
2. Dependabot が PR の本文に付ける、リリースノートと変更の一覧を読む
3. CI の結果を見る。落ちていれば、次の節へ進む
4. 問題が無ければ、Approve して、Merge when ready を押す。マージキューが、最新の main と合わせて CI を動かし直してから入れる


マージキューの中の CI で落ちた PR は、キューから外れて、開いたままになります。自動マージの PR なら、`needs-review` ラベルが付いて人に回る作りです。この動きは、単体テストで確かめただけで、実物では起きていません。

入れない更新は、PR を閉じます。Dependabot は、そのバージョンを出し直しません。次のバージョンが出ると、新しい PR が出ます。

### テストが落ちた更新

落ちた更新は、自動では入りません。レビュワーが、その PR で直します。

1. 落ちた job を見る。コードのテスト（`workspace`、`api`、`web`、`infra`）か、本番のイメージのビルド（`image`）かが分かる
2. PR のブランチを取得し、コードかテストを直して push する
3. 人が push すると、その PR は自動マージの対象から外れる。ほかの人の承認で入れる

バージョンの同期が失敗したときは、PR に、理由と直し方のコメントが付きます。

### バージョンを変える手順

ふだんの更新では、ファイルを手で編集しません。自分でバージョンを変えるときは、ファイルを書き換えたあとに、`uv run just` でレシピを 1 つ動かします。

| 変えたいもの | 書き換えるファイル | そのあと動かすレシピ | コミットするファイル |
|---|---|---|---|
| Python、Node、Terraform のバージョン（同じ系列の中） | `.python-version`、`.node-version`、`infra/versions.tf` のどれか | `uv run just align` | 書き換えたファイルと、`dependabot/Dockerfile` |
| Python のライブラリのバージョンの範囲 | `pyproject.toml`、`api/pyproject.toml`、`packages/*/pyproject.toml` | `uv run just lock-python` | 書き換えたファイルと、`uv.lock`、`api/uv.lock` |
| npm のライブラリのバージョンの範囲 | `web/package.json` | `uv run just lock-web` | `web/package.json` と `web/package-lock.json` |
| Terraform のプロバイダのバージョンの範囲 | `infra/versions.tf` の `required_providers` | `uv run just lock-infra` | `infra/versions.tf` と `infra/.terraform.lock.hcl` |
| workflow が使う action | `.github/workflows/*.yml` の `uses:`。完全なタグ（`actions/checkout@v6.0.3`）で書く | `uv run just lock-actions` | 書き換えた workflow と、`.github/workflows/actions.lock` |

Python の minor や major、Node の major を上げる手順は、「Python と Node の大きい更新」の節にあります。

レシピを動かし忘れた PR は、CI で止まります。

| 忘れたこと | 起きること | 直し方 |
|---|---|---|
| `.python-version`、`.node-version`、`infra/versions.tf` を書き換えたあと、`uv run just align` を動かさなかった | CI の `automation` が落ちる。`dependabot/Dockerfile` のバージョンと食い違う、と出る | `uv run just align` を動かし、`dependabot/Dockerfile` をコミットする |
| `pyproject.toml` の範囲を書き換えたあと、`uv run just lock-python` を動かさなかった | CI の `workspace` か `api` が落ちる。「The lockfile at `uv.lock` needs to be updated」と出る（手元で確かめた） | `uv run just lock-python` を動かし、`uv.lock` と `api/uv.lock` をコミットする |
| `web/package.json` の範囲を書き換えたあと、`uv run just lock-web` を動かさなかった | CI の `web` が、`npm ci` で落ちる（npm の決まった動き。このリポジトリでは試していない） | `uv run just lock-web` を動かし、`web/package-lock.json` をコミットする |
| workflow の `uses:` を書き換えたあと、`uv run just lock-actions` を動かさなかった | workflow が起動しない。CI の結果が付かないので、マージできない。Actions の画面に「This run likely failed because of a workflow file issue.」と出る（[PR #89](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/89) で確かめた） | `uv run just lock-actions` を動かし、`.github/workflows/actions.lock` をコミットする |

レシピが使う道具の入れ方は、「手元の始め方」の節にあります。

### Python と Node の大きい更新

Python の minor や major（3.13 から 3.14 など）と、Node の major（24 から 25 など）は、PR が自動では出ません。人が時期を決めて、1 つの PR で書き換えます。

Python の minor や major を上げるときに書き換える場所は、次のとおりです。

| 順 | 書き換える場所 | 内容 |
|---|---|---|
| 1 | `.python-version` | 新しいバージョン（例: `3.14.9`） |
| 2 | `pyproject.toml`、`api/pyproject.toml`、`packages/*/pyproject.toml` の `requires-python` | 新しい系列の範囲（例: `>=3.14,<3.15`）。4 か所 |
| 3 | `pyproject.toml` の `[tool.ruff] target-version` | 例: `py314` |
| 4 | `dependabot/Dockerfile` | 手では書き換えない。`uv run just align` を動かす |
| 5 | `uv.lock`、`api/uv.lock` | 手では書き換えない。`uv run just lock-python` を動かす。ロックファイルが解き直される |

書き換えたあと、`uv run just workspace` と `uv run just api` で、lint とテストを動かします。新しい Python に対応していない依存があると、`uv run just lock-python` かテストで分かります。
Python の手順は、3.13.16 から 3.14.9 へ上げて、手元で通しました。lint とテストは通りました。本番のイメージのビルドと、PR にして CI を通すところは、試していません。
Dependabot の設定（`.github/dependabot.yml` の `ignore`）は、変えなくて構いません。Python を上げたあとは、新しい系列の patch の PR が出ます。

Node の major を上げるときに書き換える場所は、次のとおりです。Node の手順は、通して試していません。

| 順 | 書き換える場所 | 内容 |
|---|---|---|
| 1 | `.node-version` | 新しいバージョン |
| 2 | `web/package.json` の `engines.node` | 新しい系列の範囲（例: `>=25 <26`）。`web/.npmrc` の `engine-strict` があるので、範囲が違うと `npm ci` が止まる |
| 3 | `dependabot/Dockerfile` | 手では書き換えない。`uv run just align` を動かす |
| 4 | `web/package-lock.json` | 手では書き換えない。`uv run just lock-web` を動かす |

### 手元の始め方

最初に、リポジトリの直下で `uv sync` を動かします。開発用の依存（pytest、ruff、just）が入ります。
作業は、`uv run just <レシピ>` で動かします。レシピは直下の `justfile` にあり、`uv run just --list` で、一覧と説明が出ます。CI も、同じレシピを呼びます。

`uv run just` が動く仕組みは、次のとおりです。

| 場面 | 起きること |
|---|---|
| `uv sync` を打つ | just は、直下の `pyproject.toml` の開発用の依存です（PyPI の `rust-just`）。ruff や pytest と同じ扱いです。`uv.lock` に書いてあるバージョンの just が、リポジトリの中の環境（`.venv`）に入ります。Python も、uv が `.python-version` のバージョンを用意します。手元に just を別に入れる必要はありません |
| `uv run just <レシピ>` を打つ | `.venv` に入った just が動きます |
| Dependabot の更新で `uv.lock` が変わった | 何もしなくて構いません。`uv run` は、`uv.lock` と `.venv` を見比べ、違っていれば入れ直してから動かします。`.venv` に古い just（1.58.0）を入れた状態で `uv run just --version` を打ち、1.59.0 に入れ直されることを確かめました |
| CI が動く | CI も、同じ `uv run --locked just <レシピ>` を呼びます。just のバージョンも、動くコマンドも、手元と同じです。CI は、毎回まっさらなマシンに Python と uv を入れるので、準備に job あたり数秒かかります。手元では、1 度入れれば残るので、この時間はかかりません |
| 自分で入れた just を使う | `just <レシピ>` でも動きます。just のバージョンは、自分で入れたものになります |

| レシピ | 行うこと |
|---|---|
| `uv run just test` | CI と同じテストを、手元で全部動かす（本番のイメージのビルドは除く）。`web` は Node、`infra` は Terraform を使うので、この 2 つを入れていないと、その job で止まる |
| `uv run just workspace`、`uv run just api`、`uv run just web`、`uv run just infra`、`uv run just automation` | CI の job を 1 つずつ動かす。レシピの名前は、job と同じ |
| `uv run just image -t api` | 本番の API のイメージをビルドする |
| `uv run just versions` | 使っているバージョンを出す |
| `uv run just align`、`uv run just lock-python`、`uv run just lock-web`、`uv run just lock-infra`、`uv run just lock-actions` | バージョンを書き換えたあとに動かす（「バージョンを変える手順」の節） |

CI が落ちたときは、落ちた job と同じ名前のレシピを手元で動かすと、同じコマンドが動きます。

`uv sync` で入らない道具と、バージョンのあるファイルは、次のとおりです。入れ方は自由です。

| 道具 | バージョンのあるファイル | 入れ方の例 |
|---|---|---|
| uv | 決まったバージョンは無い。0.13 以上 | 公式のインストーラ、Homebrew、mise |
| Python | `.python-version` | 入れなくてよい。uv が取得する |
| Node | `.node-version` | nodenv、fnm、mise、asdf。nodejs.org から入れてもよい |
| Terraform | `infra/versions.tf` の `required_version` | mise、asdf、公式の配布物 |
| Docker | 決まったバージョンは無い | `uv run just image` を動かすときだけ要る |
| `gh` と、拡張の `gh actions-lock` | 拡張は v0.4.1 | `gh extension install github/gh-actions-lock --pin v0.4.1`。`uv run just lock-actions` を動かすときだけ要る |

手元の uv が 0.13 より古いと、uv が止まって知らせます。
新しい Python が入らないとき（「No interpreter found for Python ...」）は、`uv self update` で uv を更新します。古い uv は、新しい Python をまだ知らないためです。
手元の Python と Node のバージョンが、`.python-version` や `.node-version` と違うと、テストが落ちて知らせます。uv のバージョンは照合しません。

`.node-version` を読む道具は、次のとおりです。それぞれの道具の文書で確かめました。実際に入れるところは、試していません。

| 道具 | `.node-version` の扱い |
|---|---|
| nodenv | そのまま読む |
| fnm | 読む。ディレクトリに入ったときに切り替えるには、シェルの設定に `fnm env --use-on-cd` を使う |
| mise | 設定が要る。`mise settings add idiomatic_version_file_enable_tools node` |
| asdf | 設定が要る。`~/.asdfrc` に `legacy_version_file = yes` と書く |

古い mise（2025.2.7）は、設定なしで `.node-version` と `.python-version` を読みました（`mise ls --current` で確かめました）。



### 通知の減らし方

自動でマージされる PR の通知は、読まなくて構いません。
通知だけでは、自動でマージされる PR と人が判断する PR を区別できません。通知はまとめて片づけ、見る PR は一覧で確かめます。

1. GitHub の受信箱（`https://github.com/notifications`）の Filters に、`repo:<owner>/<repo> author:app/dependabot` を足す
2. 並んだ通知を全部選び、Done にする
3. 見る PR は、「見る PR の探し方」の一覧で確かめる

1 と 2 は GitHub の文書にある書き方で、実物では試していません。3 の一覧は確かめました。

## 仕組みを保つ人向け

### 全体の流れ

1. Dependabot が、週に 1 回、新しいバージョンを確かめて PR を出す。セキュリティアップデートは、待たずに出す
2. Dependabot 用の Dockerfile を上げる PR には、`version-sync` が、`.python-version` などのバージョンを書き換えるコミットを足す
3. workflow の `ci` が、テストとイメージのビルドを動かす
4. `dependabot-merge` が、PR を振り分ける。条件を満たす PR は、App が承認してマージキューに入れる。それ以外には、`needs-review` ラベルと理由のコメントを付ける
5. マージキューが、最新の main と合わせて CI を動かし直し、通れば main に入れる

### 部品と役割

| 部品 | 役割 |
|---|---|
| `.github/dependabot.yml` | 何を、いつ、どうまとめて更新するか |
| `.github/CODEOWNERS` | すべてのファイルの所有者。レビューの依頼先になる |
| `.github/workflows/ci.yml` | CI。テストと、本番のイメージのビルド |
| `.github/workflows/dependabot-merge.yml` と `.github/scripts/dependabot_merge.py` | PR の振り分けと、自動マージ |
| `.github/scripts/dependabot_limit.py` | 開いている PR が上限に近づいたら、Issue で知らせる |
| `.github/workflows/version-sync.yml` と `.github/scripts/version_sync.py` | Dependabot 用の Dockerfile のバージョンを、`.python-version` などへ写す |
| `.github/workflows/security-release.yml` と `.github/scripts/security_release.py` | Python と Node のセキュリティアップデートを見つけ、待たずに PR を出す。Python と Node は別の PR |
| `.github/scripts/versions.py` | `.python-version` などのバージョンと、Dependabot 用の Dockerfile を読み、揃っていることを確かめる |
| `justfile` | 人が手で打つ作業の入口。CI も同じレシピを呼ぶ |
| `.github/workflows/dependabot-stats.yml` | Dependabot の PR の本数を、週に 1 回数える |
| `.github/workflows/actions.lock` | workflow が使う action を、コミットで固定する |
| `.github/repo-settings/` | リポジトリの設定、ruleset、GitHub App を用意するスクリプト |
| GitHub App | 承認、マージキューへの投入、バージョンを写すコミット、セキュリティアップデートの PR を行う主体 |
| ruleset（`main`、`owners-lockfiles`、`owners-others`、`tags`） | main とタグの保護。App が所有者のレビューなしで通せるのは、ロックファイルだけ |

### 変えられる点

| 変えたいこと | 変え方 |
|---|---|
| 開発用の依存の minor を自動にする | リポジトリ変数 `AUTOMERGE_DEV_MINOR` を `true` にする |
| レビュワーの人数 | `.github/scripts/policy.json` の `review_count` を変え、`uv run just apply-settings <owner>/<repo>` を動かす |
| 所有者 | team のメンバーを変える |
| マージに要る承認の数 | `.github/repo-settings/ruleset.json` の `required_approving_review_count` を変え、`uv run just apply-settings <owner>/<repo>` を動かす |
| cooldown | `.github/dependabot.yml` の `cooldown` の `default-days` |
| 同時に開く PR の上限 | `.github/dependabot.yml` の `open-pull-requests-limit` |
| まとめるライブラリ群 | `.github/dependabot.yml` の `groups` に、名前の並び（`patterns`）で足す。更新の種類ではまとめない |
| 更新の対象 | `.github/dependabot.yml` に設定を足す。Python や Node のようなランタイムを足すときは、Dependabot 用の `dependabot/Dockerfile` に `FROM` を足し、`.github/scripts/versions.py` に読み方を足す。出す更新の範囲（patch だけ、など）は、`ignore` で決める |
| ロックファイルの種類 | `.github/scripts/policy.json` の `lockfiles` に足し、`uv run just apply-settings <owner>/<repo>` を動かす |
| イメージの種類（`slim` を別の種類に替える） | `.github/scripts/policy.json` の `image_variants` を書き換え、`dependabot/Dockerfile` の `FROM` のタグを同じ種類に書き換える。本番のイメージのビルドは、同じ設定から種類を取るので、書き換えは要らない。設定と `FROM` が食い違うと、CI の `automation` が落ちる。`slim` 以外の種類で Dependabot が PR を出すところは、確かめていない |

`uv run just apply-settings` は、`.github/repo-settings/apply.sh` を呼びます。組織の所有者で、リポジトリの管理者でもある人が動かします。

### このリポジトリに固有の値

次の値は、このリポジトリと組織に合わせてあります。別のリポジトリで使うときは、書き換えます。

| 値 | 書いてある場所 |
|---|---|
| 組織名、リポジトリ名 | `.github/dependabot.yml` には無い。`uv run just apply-settings <owner>/<repo>` の引数で渡す。文書の中のリンクは `kazufuuu/dependabot-merge-queue-lab` |
| team の名前（`reviewers`） | `.github/CODEOWNERS`（`* @kazufuuu/reviewers`）、`.github/scripts/policy.json` の `review_team` |
| App の名前（`kazufuuu-dependabot-automerge`） | `.github/scripts/policy.json` の `app`。`.github/repo-settings/create-app.py` の既定は `<owner>-dependabot-automerge` |
| 担当者（`kazufusa`） | `.github/dependabot.yml` の `assignees`（6 か所） |
| ディレクトリの構成（`/api`、`/web`、`/infra`、`packages/*`） | `.github/dependabot.yml`、`justfile`、`.github/workflows/ci.yml`、`pyproject.toml` |
| 対象の道具（python、node、hashicorp/terraform） | `.github/scripts/versions.py` の `IMAGES`、`.github/scripts/security_release.py` の `NAMES`、`.github/scripts/policy.json` の `image_variants`、`dependabot/Dockerfile`、`.github/dependabot.yml` の `ignore` |
| イメージの種類（`slim`） | `.github/scripts/policy.json` の `image_variants` |
| 確認の時刻、タイムゾーン（月曜 09:00、Asia/Tokyo） | `.github/dependabot.yml` の `schedule`。workflow の cron（`.github/workflows/*.yml`）は UTC で、別に書いてある |

このリポジトリを別のリポジトリへ入れる作業そのものは、要件の対象外です。この表は、固有の値がどこにあるかを示すものです。

### 調べ方

最初に、`dependabot-merge` の workflow の実行ログを見ます。PR ごとに、判定と理由が 1 行ずつ出ます。
PR に人が回った理由は、その PR のコメントにも書いてあります。

次の表は、検証で実際に当たった詰まり方です。

| 症状 | 原因 | 直し方 |
|---|---|---|
| patch の PR が出なくなった。エラーは無い | 更新の種類でまとめたグループの PR が開いている。Dependabot は、そのディレクトリの全部の依存を処理済みとみなす | 種類でまとめるグループを作らない。まとめるのは、バージョンが連動するライブラリ群だけにする |
| patch の PR が出なくなった。エラーは無い。Dependabot のログには「created」と出る | 開いている PR が上限に達している | 人の判断待ちの PR を、マージするか閉じる。近づくと Issue が立つ |
| 承認済みの PR が、マージキューで止まったまま | `GITHUB_TOKEN` でキューに入れた。キューの CI が起動しない | App のトークンで入れる。この仕組みは、そうしている |
| 公開されたばかりのバージョンが提案された | Docker Hub 以外のレジストリのイメージでは、cooldown が効かない | イメージは Docker Hub のものを使う。ほかのレジストリのイメージを `FROM` に書くと、CI が落ちる |
| Dependabot の uv の更新が失敗する | `requires-python` や `required-version` を 1 点に固定している | 範囲で書く。バージョンの固定は、`.python-version` などのファイルで行う |
| action の patch と minor の更新が出ない | `uses:` を major だけのタグ（`@v6`）で書いている | 完全なタグ（`@v6.0.3`）で書く |
| App が承認したのに「レビューが必要」のまま | App 自身が最後に push した PR は、App の承認では通らない | 人が承認する。Python と Node のランタイム、Terraform 本体の PR は、この形になる |
| 手元で「No interpreter found for Python ...」と出る | 手元の uv が古く、その Python をまだ知らない | `uv self update` で uv を更新する。CI では起きない（Python は setup-python が入れる） |
| セキュリティの警告があるのに、修正の PR が出ない。エラーも無い | 分かっていない。pytest の警告が直下と `api/` の 2 つにあり、直下の警告にだけ PR が出た | 警告の画面の「Create Dependabot security update」を押す。この検証では、押しても PR は出なかった。出ないときは、通常の更新の PR で上げる |
| ランタイムや Terraform 本体の PR が main と衝突した。`@dependabot rebase` が断られる | `.python-version` などのバージョンを書き換えるコミットが足されているので、Dependabot は「ほかの人が編集した」とみなす | `@dependabot recreate` とコメントする。作り直され、バージョンを写すコミットも足し直される（Node と Terraform の PR で確かめた。同じ時に頼んだ Python の PR には、1 時間たっても反応が無かった。理由は分かっていない） |
| Dependabot が PR を作り直さない | Dependabot は、コメントの依頼に反応しないことがある。確認が起きても、開いている PR を「すでにある」（already exists）と扱い、作り直さないことがある。どちらも、こちらでは直せない（[PR #78](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/78) で見た） | 人が衝突を直して入れるか、閉じて次のバージョンを待つ。Dependabot の設定の `directory` を変えると、新しい PR が出直す（Dependabot 用の Dockerfile を移したときに見た。古い PR は残るので、人が閉じる）。確認を起こすには、`.github/dependabot.yml` の設定（時刻など）を変える。1 か所の時刻を変えただけで、全部の設定の確認が起きた。1 つの設定だけを起こすことは、できなかった。注意書きだけを変えた push でも、全部の設定の確認が起きたことがある |
| Dependabot 用の Dockerfile から外した依存の PR が、開いたまま残る | Dependabot は、設定から外れた依存を確かめなくなる。その PR を閉じもしない（uv を Dependabot 用の Dockerfile から外したあとの [PR #74](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/74) で見た。人が閉じた） | 人が PR を閉じる。ブランチは、閉じたあとに消す |
| main に push できない | ruleset が、PR とレビューと CI を求めている | PR を出す。人が 1 人の組織では、自分の PR を承認できない |

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
| `gh actions-lock` のバージョンの見直し | 拡張の新しいバージョンが出たとき | ロックファイルの書式は変わることがある。新しいバージョンで `uv run just lock-actions` を動かし、CI が通ることを確かめてから上げる |

### リリースの記録と、脆弱性の調べ方

本番のイメージをリリースすると、入っているものの一覧（SBOM）と、ビルドの来歴（provenance）が、自動で残ります。仕組みは[README](../README.md)の「リリースのときの記録」にあります。ここでは、動かし方と、調べ方を書きます。

リリースのしかた

1. リリースするコミットが、main に入っていることを確かめます。main に入っていないコミットのタグでは、release の workflow が途中で止まり、何も出ません。
2. そのコミットに、バージョンのタグ（`v1.2.3` の形）を打ち、push します。`git tag v1.2.3 <コミット> && git push origin v1.2.3`。
3. タグを打てるのは、tags の ruleset で許された人（リポジトリの管理者の役）だけです。
4. release の workflow が動き、イメージを ghcr に push し、SBOM 2 つを GitHub の Release に添付し、署名付きの証明を作ります。実行の要約に、イメージのダイジェスト、使ったベースイメージのダイジェスト、パッケージ数が出ます。

脆弱性が見つかったときの調べ方

- 「このパッケージの、このバージョンが、リリースしたものに入っているか」を調べます。`uv run just sbom-find <タグ> <パッケージ名>`。Release に添付した 2 つの SBOM（イメージの中身＝OS と Python、フロントの本番の依存）の両方を見ます。
- 例: `uv run just sbom-find v0.0.2 openssl` は、イメージの SBOM から `openssl 3.5.7-1~deb13u3` を出します。`uv run just sbom-find v0.0.2 date-fns` は、フロントの SBOM から `date-fns 4.1.0` を出します。
- Release の添付は、公開のリポジトリでは誰でも落とせます。だから、この調べ方は、ghcr のイメージが非公開のままでも動きます。

証明（attestation）の確かめ方

- 証明は、release の job の中で、毎回その場で検証しています（`gh attestation verify`）。リリースのたびに、通ることを確かめています。
- 手元から確かめるときは、`gh attestation verify oci://ghcr.io/kazufuuu/dependabot-merge-queue-lab/api:<タグ> --owner kazufuuu` を動かします。このとき、ghcr のイメージを読むので、`read:packages` の付いたトークンと、`docker login ghcr.io` が要ります。既定の `gh` のトークンには `read:packages` が無く、`403` になります。`gh auth refresh -s read:packages` でスコープを足してから動かします。
- `sbom-find` も、同じ証明の検証を試みます。トークンに `read:packages` が無いときは、検証を飛ばし、SBOM の照合だけを行います（SBOM の照合は Release の添付を読むので、トークンのスコープは要りません）。

SBOM を外へ渡すとき

リリースのたびに SBOM を外へ渡す運用では、次の手順を目安にします。特定の相手や、特定の依頼を前提にした書き方ではありません。

- 渡すファイルは 2 つです。Release の添付の `sbom.spdx.json`（イメージの中身）と `web.sbom.spdx.json`（フロントの本番の依存）です。`gh release download <タグ> -R <owner>/<repo>` で両方を落とすか、Release の画面の Assets から落とします。
- 渡す前に、相手に次を確かめます。
  - 形式とそのバージョン（SPDX か CycloneDX か）。この仕組みは SPDX 2.3 を出します。形式ごとの中身は[README](../README.md)の「リリースのときの記録」の「SBOM の形式」にあります。
  - 必須の項目。下の空になる項目が、相手の受け入れの条件に当たらないか。
  - 範囲。イメージの中身まで要るか、フロントの依存だけでよいか。
  - 渡し方。ファイルを添付するか、置き場所に上げるか。
  - 頻度。リリースのたびか、求めに応じてか。
  - 脆弱性の一覧も要るか。SBOM とは別に。
- この仕組みの SBOM で、空になる項目があります。供給元（supplier。OS のパッケージの一部と、フロントは空）、OS のパッケージのハッシュ、確定したライセンス（licenseConcluded）です。相手の受け入れの条件に当たるかもしれないので、先に伝えます。
- CycloneDX を求められた場合は、作る道具の指定を変えることになります。変換と走査し直しの手は[README](../README.md)の「SBOM の形式」にありますが、リリースの workflow を CycloneDX に変えることは、この見本では試していません。

## 情報システム部門の担当者への案内

GitHub App の作成の依頼、権限、鍵の扱い、悪用への備えは、[app-request.md](app-request.md) にまとめてあります。
作業の手順は [github-app.md](github-app.md) にあります。
リリースの記録についての、監査で聞かれることへの答えも、[app-request.md](app-request.md) にあります。
