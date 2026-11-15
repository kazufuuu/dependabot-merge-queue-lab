# dependabot-merge-queue-lab

Dependabot の更新を、人の手間を抑えながら安全に取り込む運用の実物です。
patch の更新はテストが通れば自動でマージし、それ以外は人に依頼します。

使い方は [docs/manual.md](docs/manual.md) にあります。メンバーが行うことと、仕組みを保つ人が行うことを、手順で書いています。
要件の一覧は [docs/requirements.md](docs/requirements.md) にあります。
要件ごとの達成の状況は [docs/status.md](docs/status.md) にあります。

## 運用の決まり

| 更新 | 変わるファイル | 扱い |
|---|---|---|
| 範囲の中の patch | ロックファイルだけ | 検査が通れば自動で承認し、マージキューに入れる |
| 範囲の中の minor | ロックファイルだけ | 人に依頼する。所有者の承認が要る |
| 範囲を超える更新、major | manifest も変わる | 人に依頼する。所有者の承認が要る |
| ランタイムと道具の版（Python、Node、uv、Terraform） | 見張り役の Dockerfile。workflow が正本の変更を積む | 人に依頼する。所有者の承認が要る |
| Python と Node の、セキュリティの修正を含む版 | 見張り役の Dockerfile と正本 | 待つ期間なしで workflow が PR を出す。人に依頼する。所有者の承認が要る |
| 固定した版（Actions、uv や ruff などの `==`） | 版を書いたファイル | 人に依頼する。所有者の承認が要る |
| セキュリティ更新 | 更新による | 待つ期間なしで、依存ごとに出る。振り分けは上の行と同じ。patch でロックファイルだけなら、検査が通れば自動でマージする |
| 検査が落ちた patch | ロックファイルだけ | 承認せず、人に依頼する。所有者の承認が要る |

自動マージの条件は、semver の種別と、変わるファイルの 2 つです。
種別が patch で、変わるファイルがロックファイルだけのときに限って、自動でマージします。
セキュリティ更新と通常の更新の違いは、待つ期間の有無だけです。

## 仕組み

### 版の書き方

版は範囲で書きます（`>=9.0,<10`、`^4.6.0`、`~> 3.3.0`）。
範囲の中の更新では、ロックファイルだけが変わります。範囲を超える更新では、manifest も変わります。

- npm は `versioning-strategy: increase-if-necessary` を指定します
- uv は `versioning-strategy` を指定しません。`pyproject.toml` の `[project]` に `description` を書き、PyPI に無い名前を付けます。Dependabot がライブラリとみなし、範囲を広げる方針を選びます
- Terraform のプロバイダは `~>` で書きます

### 所有者

`.github/CODEOWNERS` で、すべてのファイルに所有者（team `kazufuuu/reviewers`）を付けています。
所有者のレビューは、ruleset の 2 つの規則で必須にしています。

| ruleset | 対象のファイル | 対象から外す主体 |
|---|---|---|
| `owners-lockfiles` | ロックファイル（`uv.lock`、`package-lock.json`、`.terraform.lock.hcl`） | 自動マージの App |
| `owners-others` | ロックファイル以外の全部 | なし |

App が所有者のレビューなしで通せるのは、ロックファイルだけを変える PR に限られます。
人が出した PR は、ロックファイルだけの変更でも、所有者の承認が要ります。
必須の検査、マージキュー、承認 1 件の規則（`main`）には、対象から外す主体がいません。App もこの 3 つを通します。

歯止めは 2 段あります。1 段目は振り分けの判定で、変わったファイルがロックファイルだけであることを確かめます。
2 段目は上の ruleset で、判定を通さずに App のトークンを直接使っても、GitHub が拒否します。

対象から外す指定は、`exempt`（その主体には規則を当てない）です。
`always`（迂回を許す）では、マージキューに入れる操作が「team の承認待ち」で拒否されました。

### PR のまとめ方

PR にまとめるのは、版が連動するライブラリ群だけです。それ以外は、patch も minor も major も、依存ごとに 1 本ずつ出します。

- まとめている群は、npm の `vitest` と `@vitest/...` です。同じ版でないと動かないので、`.github/dependabot.yml` の `vitest` のグループで一緒に上げます（[PR #77](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/77)。2 件が 1 本にまとまった）
- 群の PR に patch と minor が混ざったときは、いちばん大きい種別で扱います。minor が 1 つでも入っていれば、人が判断します
- GitHub Actions だけは例外で、patch、minor、major を 1 本にまとめます。人が判断するためです

更新の種類（patch、minor）でまとめるグループは、作りません。作ると、自動マージが止まります。

- 種類のグループの PR が開いていると、Dependabot は、そのディレクトリの全部の依存を処理済みとみなし、ほかの更新を出しません
- minor のグループの PR が人の判断を待っている間、patch の PR が出なくなりました（[実行 43682150672](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43682150672)。ログは「Adding dependencies as handled」「Skipping hashicorp/null in group patch as it has already been handled by a previous group」）。エラーは出ません
- グループをやめると、minor の PR が開いたままでも、patch の PR が出て、自動でマージされました（[PR #79](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/79)、[PR #85](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/85)、[PR #87](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/87)）

開発用の依存の minor を自動マージの対象に足すときは、リポジトリ変数 `AUTOMERGE_DEV_MINOR` を `true` にします。
振り分けは、グループの名前を見ません。種別と依存の種類を、Dependabot が署名したコミットのメッセージから読みます。

セキュリティ更新のメタデータには、種別が書かれません。
振り分けは、Dependabot が同じコミットメッセージに書く「from 旧い版 to 新しい版」から種別を求めます。
数字 3 つの版どうしで、3 つ目だけが上がっているときに patch とみなします。それ以外は人に依頼します。

### 同時に開く PR の上限

`open-pull-requests-limit` は、設定（エコシステムとディレクトリの組）ごとに 10 本です。
開いている PR が上限に達すると、Dependabot は新しい PR を作りません。patch の PR も出なくなり、自動マージが止まります。

- 実物で確かめました。上限を 3 に下げ、人の判断待ちが 4 本ある状態にすると、patch の PR は作られませんでした。Dependabot の実行は成功し、ログには「created」と出ます（[実行 43684334942](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43684334942)）。エラーは出ません
- 上限を 10 に戻すと、同じ PR が出て、自動でマージされました（[PR #87](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/87)）
- 気づき方: 残りが 2 本以下になると、「Dependabot の PR が上限に近づいています」という Issue が 1 件立ちます。`dependabot-merge` の workflow が、毎時、設定ごとの本数を数えています（`automation/dependabot_limit.py`）。本数が減ると、Issue は自動で閉じます
- 直し方: 人の判断待ちの PR（`needs-review` ラベル）を、マージするか閉じます
- セキュリティ更新の PR は、別の枠で出る決まりです。このリポジトリでは確かめていません

### PR の本数と検査の回数

種類でまとめるのをやめたあと、Dependabot が 1 回の確認で出した PR は 13 本でした（2026-11-15）。

| 測ったもの | 数字 |
|---|---|
| 同時に開いている Dependabot の PR | 16 本（uv の直下 4、`/api` 3、npm 3、Terraform 1、見張り役 4、Actions 1） |
| 自動でマージされた patch の PR | 3 本。Dependabot の push からマージまで、2 分 47 秒、2 分 47 秒、2 分 11 秒 |
| 検査の回数 | PR 1 本につき 1 回。自動でマージされる PR は、マージキューの検査が 1 回加わる。版の同期がコミットを積む PR は、もう 1 回 |
| 同じロックファイルを変える PR どうしの衝突 | 起きなかった。`uv.lock` を変える PR が 4 本開いた状態で 1 本が入っても、残りは作り直されず、検査も走り直さなかった |

人が見る PR の本数は、次のとおりです。

| 種類 | 今開いている本数 | ふだんの出方 |
|---|---|---|
| ライブラリの minor | 7 本（vitest の群の 1 本を含む） | 依存ごとに、新しい minor が出た週に 1 本 |
| ライブラリの major | 2 本 | 依存ごとに、新しい major が出た週に 1 本 |
| ライブラリの patch で、人に回ったもの | 2 本（テストが落ちた phonenumbers、版を固定している ruff） | テストが落ちたときと、`==` で固定した依存 |
| Python、Node、uv、Terraform の本体 | 5 本（セキュリティの修正の 1 本を含む） | 道具ごとに、新しい版が出た週に 1 本。セキュリティの修正は、待たずに別の 1 本 |
| GitHub Actions | 1 本 | 週に 1 本 |

今開いている 17 本は、どれも本物の更新です。検証用に作った PR は、残っていません。
本数が多いのは、このリポジトリを古い版から始め、2 日間、人が 1 本も判断していないためです。溜まっていた更新が、1 回目の確認でまとめて出ました。
2 週目以降に、週に何本出るかは、測っていません。上限は、依存の数（ライブラリ 14、道具 4、Actions 1）です。

種類でまとめていたときは、patch の PR はディレクトリごとに 1 本、検査も 1 回でした。依存ごとに出す形では、patch の更新がある依存の数だけ、PR と検査が増えます。
同じロックファイルの patch が 3 本以上重なった場合は、測れていません。このリポジトリには、同時に patch の更新がある依存が、ロックファイルごとに 1 つしかありませんでした。

### 振り分け

`.github/workflows/dependabot-merge.yml` が、開いている Dependabot の PR を見直します。
CI が終わったとき、毎時、手動の 3 通りで動きます。判定は `automation/dependabot_merge.py` にあります。

- 判定は main の版で動きます。PR の中身は実行しません
- 種別は、Dependabot がコミットメッセージに書くメタデータで判定します
- コミットが GitHub 自身の鍵で署名されていることと、その head を push したのが Dependabot であることを確かめます。作者の欄は自由に書けるので、判断に使いません
- 人が見る PR には、`needs-review` ラベルと理由のコメントを付けます。レビューの依頼は、GitHub が CODEOWNERS から付けます
- 自動マージする PR には、検査が通ったあとで承認を付け、`automerge` ラベルを付けて、マージキューに入れます
- マージキューの検査で外された PR も、人に依頼します

承認とマージキューへの投入は、専用の GitHub App が行います。

- `GITHUB_TOKEN` でキューに入れると、merge_group の検査が起動せず、キューが止まります。App のトークンで入れると起動します
- App の鍵は environment `automerge` の secret に置きます。この environment は main だけが使えるので、ほかのブランチの workflow からは鍵を読めません
- 「GitHub Actions による PR の承認」は無効にします。人が自分のブランチに workflow を足しても、自分の PR は承認できません

### レビューの依頼

人が見る PR には、レビュワーを 1 人だけ付けます。所有者の全員には依頼しません。

- CODEOWNERS の所有者は team（`kazufuuu/reviewers`）です。すべてのファイルに所有者がいるので、どの PR にも GitHub が team への依頼を付けます
- team の code review assignment が、依頼を team の中の 1 人に割り振ります。方式は load balance（直近の依頼が少ない人に回す）です。team の全員には通知しません
- 自動でマージされる patch の PR にも、開いた時点で依頼が付きます。数分でマージされるので、レビュワーは何もしなくて構いません
- 休みの人は、GitHub のステータスを Busy にすると、割り振りから外れます。team の設定画面の Code review で、外す人を指定することもできます

人数と承認の数は、別の設定です。

| 変えたいこと | 変える場所 |
|---|---|
| 割り振る人数 | `automation/policy.json` の `review_count`。`settings/apply.sh` が team の設定に反映する |
| マージに要る承認の数 | `settings/ruleset.json` の `required_approving_review_count` |
| 所有者を増やす、減らす | team のメンバーを変える |

2 人に割り振っても、承認の数が 1 のままなら、どちらか 1 人の承認で通ります。

### 通知

自動でマージされる PR の通知は、読まなくて構いません。人が見なくても、検査が通れば入るためです。
検査が落ちたときは、振り分けが `needs-review` ラベルとコメントを付けるので、人が判断する PR に変わります。

#### 届く数

GitHub の受信箱では、PR 1 本が通知 1 件にまとまります。この検証では、Dependabot の PR 1 本につき 1 件でした。

| 届く相手 | 理由 | 自動でマージされる PR での数 |
|---|---|---|
| `.github/dependabot.yml` の `assignees` に書いた人 | 担当の割り当て（`assign`） | 週に最大 14 件。セキュリティ更新の patch が出た週は、その本数が加わる |
| 割り振られたレビュワー | レビューの依頼（`review_requested`） | 同じ。team の中で回るので、1 人あたりは人数で割った数になる |

週に最大 14 件は、設定から出した上限です。ロックファイルだけが変わりうる依存の数（uv の直下 4、`/api` 4、npm 4、Terraform 2）で、全部に patch の更新が出た週の数です。
実測は、2 日間で 6 本（PR #12、#34、#70、#79、#85、#87）です。依存ごとの形になってからは、3 本（#79、#85、#87）です。メールの通数は確かめていません。

#### 無視するための設定

通知が届いた時点では、自動でマージされる PR か、人が判断する PR かを、通知だけでは区別できません。
GitHub の受信箱は、題名やラベルで絞り込めず、除外の条件も書けないためです（GitHub の文書で確かめました）。
そこで、Dependabot の PR の通知をまとめて片づけ、人が判断する PR は一覧で確かめる形にします。

1. 受信箱（`https://github.com/notifications`）の Filters に、`repo:kazufuuu/dependabot-merge-queue-lab author:app/dependabot` を足す。Dependabot の PR の通知だけが並ぶ
2. 並んだ通知を全部選び、Done にする
3. 人が判断する PR は、下の一覧で確かめる

メールで受け取っている人は、メールの振り分けを使えます。通知のメールは、差出人が `notifications@github.com`、`List-Id` がリポジトリごとの値です。
このリポジトリの通知をまとめて別のフォルダに入れると、受信トレイには届きません。題名では、自動でマージされる PR を区別できません。

1 と 2 の絞り込みは GitHub の文書にある書き方で、実物では試していません。メールの振り分けも試していません。

#### 見落とさないための一覧

通知を片づけた人は、人が判断する PR を、次の一覧で確かめてください。どちらも実物で確かめました。

- 自分にレビューが依頼されている PR: `https://github.com/pulls/review-requested`
- このリポジトリの、人が判断する PR: PR の一覧を `is:open label:needs-review` で絞り込む

検査が落ちた patch も、題名の形は自動でマージされる PR と同じです。通知では区別できないので、一覧で確かめます。

### 検査

`.github/workflows/ci.yml` は、テストを runner の上で直接動かします。docker の中では動かしません。
依存はキャッシュします（uv と Python は setup-uv、npm は setup-node）。

| job | 内容 | 版の読み方 |
|---|---|---|
| `workspace` | workspace の lint とテスト | `automation/versions.py show` が `.tool-versions` から uv の版を読み、setup-uv に渡す。Python は uv が `.python-version` から選ぶ |
| `api` | API のテスト | 同上 |
| `web` | 型検査とテスト | setup-node が `.tool-versions` を読む |
| `infra` | Terraform の書式、検証、テスト | `automation/versions.py show` が `infra/versions.tf` から読み、setup-terraform に渡す |
| `automation` | 振り分けと版の同期のテスト、版が揃っていることの確認 | runner の Python |
| `image` | API のイメージの組み立て | `scripts/build-api.sh` が正本から読み、ビルドの引数で渡す |

`image` は、テストを動かしません。依存を入れてイメージを組み立てるだけです。組み立てたイメージの起動は確かめません。
runner にはコンパイラが入っていますが、slim のイメージには入っていません。テストが通っても、イメージの組み立てが落ちる更新があるので、毎回確かめます。組み立ての層はキャッシュします。
必須の検査は、全部の結果をまとめた `all-green` の 1 つです。テストとイメージの組み立ての、どれか 1 つでも落ちると、自動マージされません。
マージキューでは、最新の main と合わせた状態で同じ検査が動きます。ブランチが古くても止まりません。

### 版の正本

ランタイムと道具の版は、それぞれの道具が自分で読む場所に、1 点に固定して書きます。

| 版 | 正本 | 読む道具 |
|---|---|---|
| Python | `.python-version` | uv（`api/` でも、親のディレクトリのこのファイルを読む） |
| uv | `.tool-versions` の `uv` の行 | 手元の mise や asdf。CI では `automation/versions.py` |
| Node | `.tool-versions` の `nodejs` の行 | 手元の mise や asdf。CI では setup-node |
| Terraform | `infra/versions.tf` の `required_version = "= 1.16.x"` | terraform |

手元、CI、本番のイメージは、どれもこの正本を読みます。

- 手元: uv と Node は、mise や asdf が `.tool-versions` の版を入れます。Python は、uv が `.python-version` の版を取得して使います
- 手元の版がずれていると、テストが落ちます。`tests/test_toolchain.py` が Python と uv を、`web/src/toolchain.test.js` が Node を、正本と比べます
- CI: 「検査」の表のとおりです
- 本番のイメージ: `api/Dockerfile` は、版をビルドの引数（`PYTHON_VERSION`、`UV_VERSION`）で受け取ります。`scripts/build-api.sh` が正本から渡します。引数を付け忘れると、`FROM` が成り立たずに失敗します

1 点に固定できない場所が 2 つあります。どちらも試して、Dependabot の uv の更新が失敗することを確かめました。

| 試した形 | 結果 |
|---|---|
| `requires-python = "==3.13.x"` | 失敗。Dependabot は自分の Python（別の patch）を選ぶので、「Python version incompatibility」になる |
| `[tool.uv] required-version = "==0.13.x"`（`uv.toml` に書いても同じ） | 失敗。Dependabot は自分の uv を使うので、`tool_version_not_supported` になる |

そのため、`requires-python` は範囲（`>=3.13,<3.14`）で書き、`required-version` は下限（`>=0.13`）だけを書いています。
手元に入れた uv の版は、uv 自身には照合させられません。古すぎる uv だけが、下限で止まります。
そこで、照合はテストに持たせています。Dependabot はテストを動かさないので、更新は失敗しません。

### 版の更新の流れ

Python、Node、uv、Terraform の正本は、Dependabot が書き換えられません。書き換えられるのは Dockerfile の `FROM` です。
そこで、`versions/Dockerfile` を見張り役として置いています。組み立てないファイルで、`FROM` に版を並べただけのものです。

1. Dependabot が、`versions/Dockerfile` の版を上げる PR を出す。新しい版を見つけること、待機、PR の作成は Dependabot の仕事
2. `version-sync` の workflow が、見張り役の版を正本へ写し、その PR にコミットを積む
3. 検査が動く。PR は人のレビューに回る。コミットが 2 つになるので、自動マージの対象にはならない

`version-sync` がするのは、決まった場所の値を決まった場所に写すことだけです（`automation/versions.py` の `sync`）。

- 計算は、鍵を持たない job で行います。PR の head を取り出し、版を写します
- push は、鍵を持つ job で行います。渡されたファイルを App のトークンでコミットするだけで、PR の中身は取り出しません。積めるファイルは、正本の 3 つ（`.python-version`、`.tool-versions`、`infra/versions.tf`）に限っています
- 対象は、Dependabot が push した、`versions/Dockerfile` だけを変える PR です
- 版の記述が見つからない、2 か所ある、という場合は、何もせずに失敗します。失敗の理由と直し方を、PR にコメントで残します。PR の検査も、見張り役と正本の食い違いで落ちたままになります

Renovate は、`.python-version` や `.tool-versions` を直接書き換えられます。このリポジトリは Dependabot を使うと決めているので、見張り役と同期の仕掛けで補っています。

見張り役のイメージは Docker Hub のものに限ります。待機が Docker Hub のイメージにしか効かないためです。ほかのレジストリのイメージを書くと、検査が落ちます。

### GitHub Actions の版

workflow が使う action は、GitHub の workflow のロックファイル（`.github/workflows/actions.lock`）で、コミットに固定しています。
workflow の `uses:` にはタグ（`actions/checkout@v6.0.3`）を書きます。実際に動くのは、ロックファイルに記録したコミットです。
ロックファイルは `gh actions-lock`（GitHub 公式の `gh` の拡張）が作ります。手では編集しません。

`uses:` を足したり変えたりしたときは、`gh actions-lock` を動かして、ロックファイルも一緒にコミットします。
ロックファイルと食い違う `uses:` を書いた workflow は、起動しません。検査の結果が付かないので、その PR はマージできません（[PR #89](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/89)、[実行 43686598573](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43686598573)。「This run likely failed because of a workflow file issue.」）。
Dependabot が action を上げる PR では、ロックファイルの書き換えも Dependabot が行います。人の手作業は要りません（[PR #69](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/69)）。

Dependabot は、action を上げる PR で、workflow のファイルとロックファイルの両方を書き換えます。
ライブラリと違い、patch の更新でも workflow のファイルが変わるので、action の更新は、すべて人が判断します。
`uses:` の書き方を変えて、実物で確かめた結果です。

| `uses:` の書き方 | Dependabot の動き | 証拠 |
|---|---|---|
| 完全なタグ（`@v10.3.2`） | patch でも minor でも、workflow のファイルとロックファイルの両方を変える | [PR #63]({U}/pull/63)（patch）、[PR #64]({U}/pull/64)（minor） |
| major だけのタグ（`@v6`） | major の更新だけを出す。patch と minor の更新は出ない。ロックファイルのコミットは、人が `gh actions-lock --relock` を動かすまで古いまま | [実行 43681122355]({U}/actions/runs/43681122355)（`actions/cache@v6` に更新が出なかった） |

action の更新は、patch も含めて人が判断します。理由は 2 つです。ロックファイルだけが変わる PR にならないことと、workflow が鍵を扱うことです。
その代わり、action の更新は、patch、minor、major を 1 本の PR にまとめます（`.github/dependabot.yml` の `actions` のグループ）。確認は週 1 回なので、週に 1 本ほどになります。セキュリティの修正は、待たずに別の PR で出ます。

そのため、`uses:` は完全なタグで書きます。major だけのタグで書くと、更新の取りこぼしになります。
major のタグを持たない action もあります（`astral-sh/setup-uv` に `v10` は無い）。

この機能は新しく、書式と道具は変わることがあります。拡張は v0.4.1 で確かめました。

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
| セキュリティ更新 | かからない | 入る。patch で、ロックファイルだけが変わるとき |
| Python と Node の、セキュリティの修正を含む版 | かからない。`security-release` が出す | 入らない。見張り役と正本が変わる |

待機は、悪意のある版が発覚するまでの時間を取るものです。防ぐものではありません。
確かめ方と実例は [docs/app-request.md](docs/app-request.md) の「待機の効く範囲」にあります。

### セキュリティの修正への追随

セキュリティの修正と通常の更新の違いは、待つ期間を置くかどうかだけです。

| 対象 | 通常の更新 | セキュリティの修正 |
|---|---|---|
| ライブラリ（PyPI、npm） | Dependabot が、7 日待って出す | Dependabot のセキュリティ更新が、待たずに出す |
| Python、Node、uv の本体 | Dependabot が、7 日待って出す | `security-release` の workflow が、待たずに出す |

ライブラリのセキュリティ更新が待たずに自動で入るのは、次の全部を満たすときです。

- GitHub の脆弱性のデータベース（GitHub Advisory Database）に登録された修正である。Dependabot がセキュリティ更新を出すのは、この場合だけ
- patch の更新で、ロックファイルだけが変わる
- 検査が通る

minor や major になる修正、manifest が変わる修正、検査が落ちる修正は、人に依頼します。

コンテナのイメージには、Dependabot のセキュリティ更新がありません。
そこで、`.github/workflows/security-release.yml` が 4 時間ごとに、Python、Node、uv のセキュリティの修正を含む版を探します。
見つけると、見張り役と正本をその版にする PR を、App が出します。判定は `automation/security_release.py` にあります。

| 対象 | 見分け方 |
|---|---|
| Node | [nodejs.org の版の一覧](https://nodejs.org/dist/index.json)の、版ごとの `security` の値。同じ major の中で、`true` の版のうち、いちばん新しいもの |
| Python | 今の版に効く脆弱性を [OSV](https://osv.dev) に聞く。その修正のコミットが、新しい版で初めて入ったかを、python/cpython の履歴で確かめる。同じ minor の中で、修正が入った版のうち、いちばん新しいもの |
| uv | 今の版に効く勧告を、[GitHub の勧告のデータベース](https://github.com/advisories)に聞く。勧告に書かれた修正の版のうち、いちばん新しいもの |

- 見分けは、公開されている情報を読むだけの機械的な処理です。uv は、今の版に効く勧告が 0 件であることと、古い版（0.13.3）では修正の版（0.13.4）が返ることを、実際のデータで確かめました
- 公式イメージが Docker Hub にまだ無い版は、見送ります。次の回に確かめ直します
- 同じ版の PR は、2 度出しません。人が閉じた PR も、出し直しません
- 同じ回に見つかった版は、1 本の PR にまとめます
- 探す job は鍵を持ちません。PR を出す job は鍵を持ち、main のファイルと、渡された版の数字だけを使います
- PR は App が出すので、自動マージの対象になりません。所有者のレビューが要ります

Dependabot は、7 日たつと同じ版を通常の更新として出します。先の PR が開いたままだと、重なります。どちらかを閉じてください。

Docker Hub の公式イメージは、同じタグのまま作り直されます。Dependabot は最後に push された日で待つ期間を数えるので、通常の更新は、作り直しのたびに遅れます。

Python と Node の本体の更新は、patch も含めて、すべて人が判断します。更新が少ないためです。
PR が出ると、版を正本に写すコミットが機械で足され、検査が動き、レビュワーに依頼が付きます。人が行うのは承認だけです。

## 手元の始め方

使う版は、次のファイルにあります。入れ方は自由です。

| 道具 | 版のあるファイル | このファイルを読む道具の例 |
|---|---|---|
| Python | `.python-version` | uv、pyenv、mise、asdf |
| Node と uv | `.tool-versions` | mise、asdf |
| Terraform | `infra/versions.tf` の `required_version` | terraform 自身（版が違うと止まる） |

版を管理する道具を使わない場合は、ファイルに書いてある版を、次のように入れます。

- uv: すでに入っている uv で `uv self update <版>` を動かす。新しく入れるときは、公式のインストーラに版を指定する（`curl -LsSf https://astral.sh/uv/<版>/install.sh | sh`）
- Python: 入れなくてよい。uv が `.python-version` の版を取得する
- Node: nodejs.org から、その版を入れる

手元の版が正本と違うと、テストが落ちます。道具には依りません。
`tests/test_toolchain.py` が Python と uv を、`web/src/toolchain.test.js` が Node を、ファイルの版と比べます。

確かめたのは、mise が `.tool-versions` と `.python-version` から版を読むところ（`mise ls --current`）までです。それぞれの道具で実際に入れるところは、試していません。

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

1. 正本（`.python-version`、`.tool-versions`、`infra/versions.tf`）を書き換える
2. `python3 automation/versions.py align` を動かす。見張り役が正本に揃う

片方だけを直した PR は、検査（`automation/versions.py check`）が落とします。

## 設定の反映

`settings/apply.sh <owner>/<repo>` が、リポジトリの設定、environment、ruleset を反映します。
ruleset は 4 つです。

- `main`: main の保護（`settings/ruleset.json`）。PR、承認 1 件、必須の検査、マージキュー
- `owners-lockfiles` と `owners-others`: 所有者のレビュー。`settings/owner_rulesets.py` が、`automation/policy.json` のロックファイルの名前、team、App から作る
- `tags`: タグの保護（`settings/ruleset-tags.json`）

GitHub App は `settings/create-app.py` で用意します。手順は [docs/github-app.md](docs/github-app.md) にあります。
App の作成をほかの部門に頼むときの依頼書は [docs/app-request.md](docs/app-request.md) です。

## 範囲の見直し

`dependabot-stats` の workflow が、週に 1 回、Dependabot の PR を数えます。
出た本数、自動でマージされた本数、人が触った本数が、更新の種類ごとに分かります。
人が承認するだけの PR が多ければ、`AUTOMERGE_DEV_MINOR` で範囲を広げます。

## 残る制約

- ランタイムと道具の版、Actions の `uses:`、`==` で固定した依存は、patch の更新でも版を書いたファイルが変わるので、人の承認が要ります
- uv の本体は、Docker Hub のイメージ（`astral/uv`）の版として追います。セキュリティの修正を含む版が出ても、イメージが Docker Hub に出るまでは PR になりません
- 手元の版の照合は、テストを動かしたときに働きます。別の版を入れた人は、テストが落ちて気づきます
- Dependabot は、依存ごとに最新の版だけを提案します。範囲を超える版が出ている依存では、範囲の中の patch は提案されません
- uv の方針は、Dependabot のライブラリ判定に頼っています。同じ名前のパッケージが PyPI に登録されると、判定が変わることがあります
- 人が 1 人だけの組織では、ruleset を入れたあとに main を変える手段がありません。自分の PR を自分で承認できないためです。この検証では、main の変更のたびに ruleset を一時的に無効にしました
- App は CODEOWNERS の所有者になれません。App が通せるのは、ロックファイルだけを変える PR です。ロックファイルの所有者のレビューを、App にだけ求めない設定にしています
- 新しい Python の版を、固定した uv がまだ知らないことがあります。その PR は検査が落ち、人に回ります。uv を先に上げてください（[PR #58](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/58)）
- 自動でマージされる patch の PR でも、レビュワーに依頼の通知が届きます。CODEOWNERS の依頼は PR を開いた時点で付くので、止められません
