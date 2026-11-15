# GitHub App の作成の依頼書

情報システム部門の担当者に、GitHub App の作成を依頼するための文書です。
開発の文脈を知らなくても読めるように書いています。作業の手順は [github-app.md](github-app.md) にあります。

この文書の実例は、検証用の組織 `kazufuuu` のリポジトリ `dependabot-merge-queue-lab` で、2026-11-14 と 11-15 に確かめたものです。

## 依頼の要点

- GitHub App を 1 つ作り、指定したリポジトリ 1 つにだけ入れてください。App は 1 つで足ります
- 権限は、Contents と Pull requests の書き込みの 2 つだけです
- 秘密鍵は担当者が作り、担当者がリポジトリの所定の場所に登録してください。開発者は鍵の中身を見ません
- App が行うのは、条件を満たした依存の更新を承認し、マージの待ち行列に入れることだけです

## 用語

| 用語 | 意味 |
|---|---|
| Dependabot | GitHub の機能。使っているライブラリの新しいバージョンを見つけ、更新の PR を自動で出す |
| PR | pull request。変更を main に入れる前の、レビューの単位 |
| patch の更新 | バージョンの 3 つ目の数字だけが上がる更新（1.2.3 から 1.2.4）。不具合の修正が中心 |
| ロックファイル | 実際に使うバージョンを記録するファイル。人が書くのではなく、道具が書き出す |
| CI | PR ごとに自動で動くテスト |
| マージキュー | 承認済みの PR を並べ、最新の main と合わせて CI を動かし直してから入れる、GitHub の待ち行列 |
| workflow | リポジトリに置いた自動処理（GitHub Actions） |
| `GITHUB_TOKEN` | workflow に自動で渡る、そのリポジトリ用の一時的な権限 |
| environment | secret の置き場所。使えるブランチを絞れる |
| cooldown | Dependabot の設定。公開から決めた日数がたつまで、そのバージョンを提案しない |
| ruleset | ブランチやタグの保護の決まり。レビューや CI を必須にする |

## 目的

依存の更新のうち、危険の小さいものを人の手を介さずに取り込みます。
対象は、patch の更新で、ロックファイルだけが変わり、CI が通ったものです。
それ以外の更新は、これまでどおり人がレビューします。

## App が要る理由

workflow の `GITHUB_TOKEN` だけでは、マージキューを使った自動マージが成り立ちません。
`GITHUB_TOKEN` で PR をマージキューに入れると、キューの CI が起動せず、PR が待ったままになります。
`GITHUB_TOKEN` が起こした出来事は、ほかの workflow を起動しない決まりだからです。

実例は次のとおりです。

| 入れた主体 | 結果 | 証拠 |
|---|---|---|
| `GITHUB_TOKEN` | キューの CI が起動しない。3 分待っても CI 待ちのまま | [PR #12 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12)（13:30:23 に `github-actions` が投入） |
| `GITHUB_TOKEN`、CI を別の方法で起動 | CI は成功したが、キューは 16 分進まない | [実行 43600679442](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43600679442)、[PR #15 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/15) |
| 人のアカウント | キューの CI が起動し、46 秒後にマージ | [実行 43602072881](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43602072881) |
| GitHub App | キューの CI が起動し、71 秒後にマージ | [実行 43605089530](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605089530)、[PR #12](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12) |

## 退けた案

### 個人のトークン

- 権限が人に紐づきます。その人が持つほかの権限と切り離せません
- マージの記録に、その人の名前が残ります。機械の操作と人の操作を見分けられません
- 異動や退職で止まります

### workflow に承認を許す設定

GitHub には、workflow の `GITHUB_TOKEN` に PR の承認を許す設定があります。この設定は使いません。

- 書き込み権限のある人は誰でも、自分のブランチに workflow を足して、PR を承認させられます
- 承認できても、上の理由でマージキューは動きません

App を入れたあと、この設定は組織とリポジトリの両方で無効にします。無効の状態で workflow から承認を試すと、拒否されます（「悪用への備え」の表を見てください）。

## 権限

App の用途は 3 つです。条件を満たした PR の承認とマージ、Dependabot が上げたバージョンを`.python-version` などのファイルへ写すコミット（README の「バージョンの更新の流れ」）、そして、Python と Node のセキュリティアップデートに上げる PR の作成です（README の「セキュリティアップデートへの追随」）。

| 権限 | 水準 | 使う操作 |
|---|---|---|
| Contents | 書き込み | PR をマージキューに入れ、main に入れる。Dependabot の PR のブランチに、バージョンを写すコミットを積む。セキュリティアップデートに上げるブランチを作る |
| Pull requests | 書き込み | PR を承認する。`automerge` ラベルを付ける。セキュリティアップデートに上げる PR を出す |
| Metadata | 読み取り | GitHub が自動で付ける |

この 2 つで足りることは、実物で確かめました。[PR #12](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12) と [PR #34](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/34) は、この権限だけの App が承認し、マージしています。
Webhook は使いません。App は外部のサーバーを持たず、通知も受け取りません。

## 範囲

- 入れるのは、依頼するリポジトリ 1 つだけです。install のときに「Only select repositories」で選びます
- 組織全体には入れません
- App は公開しません。ほかの組織からは install できません

## App の動き

App のトークンを使う job は 3 つです。どれも main のバージョンで動き、PR の中身を実行しません。

| workflow と job | すること |
|---|---|
| `dependabot-merge` の `merge` | 条件を満たした PR を承認し、マージキューに入れる |
| `version-sync` の `push` | Dependabot が Dependabot 用の Dockerfile のバージョンを上げた PR に、`.python-version` などのファイルの変更を積む |
| `security-release` の `open` | Python と Node のセキュリティアップデートに上げる PR を出す |

`merge` は、次の条件をすべて満たす PR だけを承認し、マージキューに入れます。

1. PR の作成者が Dependabot である
2. コミットが 1 つだけである
3. そのコミットの作者が Dependabot で、GitHub 自身の鍵で署名されている
4. その head を push したのが Dependabot である
5. 変わったファイルがロックファイルだけである
6. 更新がすべて patch である。脆弱性の修正として出る更新（セキュリティアップデート）も、同じ条件で扱う。違いは、cooldown がかからないことだけ
7. CI がすべて通っている

3 と 4 の確かめ方は次のとおりです。

- コミットの作者の欄は、誰でも自由に書けます。作者の欄だけでは Dependabot と判断しません
- 署名は、GitHub の API が返す `wasSignedByGitHub` を見ます。Dependabot のコミットは、GitHub 自身の鍵（署名者は `web-flow`）で署名されます。人が自分の鍵で署名したコミットは、署名が有効でも対象にしません
- head を push した主体は、その head で CI を起こした主体（workflow の実行の `actor`）で確かめます。過去の本物のコミットを人が別のブランチへ持ってきた場合は、主体が人になるので対象にしません

判定の実装は `automation/dependabot_merge.py` の `classify` と `normalize` です。

App がしないことは次のとおりです。

- 人が出した PR を承認しない
- ロックファイル以外が変わる PR を承認しない。承認しても通りません。ロックファイル以外には所有者のレビューが必須で、App は所有者になれないからです
- CI が落ちた PR を承認しない
- Python と Node のランタイム、Terraform 本体のバージョンを上げる PR を承認しない。patch も含めて、すべて人が判断します
- main に直接 push しない。main への変更は、PR とマージキューを必ず通ります

この動きを保証している仕組みは次のとおりです。

| 仕組み | 効き目 |
|---|---|
| 判定は main に入っているバージョンで動く | PR の中身で判定を書き換えられない。判定を変えるには、所有者のレビューを通す必要がある |
| 鍵は environment `automerge` の secret に置く。この environment は main だけが使える | main 以外のブランチの workflow は、鍵を読めない |
| ブランチ保護（ruleset）で、すべてのファイルに所有者のレビューを必須にする。ロックファイルの規則だけ、App を対象から外す | App が所有者のレビューなしで通せるのは、ロックファイルだけを変える PR に限られる。人が出した PR は、ロックファイルだけでも所有者の承認が要る |
| 必須のチェックは、全部のテストをまとめた 1 つ | テストの一部だけが動いて通る、ということが起きない |
| マージキューで、最新の main と合わせて CI を動かし直す | 単独では通るが、合わせると壊れる変更が入らない |

鍵を使う job は、PR の中身を取り出しません。実行もしません。次の 2 か所で確かめられます。

- `.github/workflows/dependabot-merge.yml` の `merge` job。`actions/checkout` の `ref` が既定のブランチ（main）で、動かすのは main の `automation/dependabot_merge.py` だけ
- `automation/dependabot_merge.py`。PR については GitHub の API を呼ぶだけで、PR のブランチを取得する処理も、PR のファイルを実行する処理も無い

## 悪用への備え

実際に試した結果です。
「App のトークンを直接使い」と書いた行は、main に一時的な workflow を置いて試しました。試験のあと、この workflow は消しています。

| 試したこと | 結果 | 証拠 |
|---|---|---|
| main 以外のブランチの workflow から、鍵を読む | job が起動しない。「Branch "probe/approval-bypass" is not allowed to deploy to automerge due to environment protection rules.」 | [実行 43605292206](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605292206) の `read-key` |
| main 以外のブランチの workflow から、`GITHUB_TOKEN` で PR を承認する | 422 で拒否。「GitHub Actions is not permitted to approve pull requests.」 | 同じ実行の `approve-with-github-token` |
| Dependabot の PR のブランチに、人がコミットを積む | 対象から外れ、人に依頼が回る。「コミットが 2 個あります / Dependabot の署名の無いコミットがあります」 | [実行 43605421916](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605421916)、[PR #34 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/34) |
| 作者を Dependabot と偽り、署名の無いコミットを Dependabot の PR に push する（中身とメッセージは本物と同じ） | 対象から外れる。「Dependabot の署名の無いコミットがあります / head を push したのが Dependabot ではありません: kazufusa」 | [実行 43611062711](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43611062711) |
| GitHub の API でコミットを作り、作者を Dependabot と指定する | コミットは署名なし（`verified: false`、`reason: unsigned`）になり、対象から外れる | [実行 43611181132](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43611181132) |
| 本物の Dependabot のコミットを、人が push し直す | 対象から外れる。「head を push したのが Dependabot ではありません: dependabot[bot], kazufusa」 | [実行 43611286487](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43611286487) |
| CI が落ちる patch の更新 | 承認されない。`needs-review` ラベルが付き、人に依頼が回る | [PR #16](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/16) |
| セキュリティアップデート | 承認されない。人に依頼が回る | [PR #10](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/10) |
| App のトークンを直接使い、ロックファイル以外を変える PR を承認して、マージキューに入れる。直接のマージも試す（判定を通さない。鍵が漏れた場合の再現） | どちらも拒否。「Waiting on required approvals from 1 team.」 | [実行 43676254642](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43676254642)、[PR #54](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/54) |
| App のトークンを直接使い、CI が落ちているロックファイルだけの PR を、マージキューに入れる | 拒否。「Required status check "all-green" is failing.」 | 同じ実行、[PR #41](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/41) |
| 人が出したロックファイルだけの PR を、App の承認だけで、人がマージキューに入れる | 拒否。「Waiting on required approvals from kazufuuu/reviewers.」 | [PR #55](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/55)。App の承認は付いている |
| App のトークンを直接使い、ロックファイルとそれ以外の両方を変える PR を通す | 拒否。「Waiting on required approvals from 1 team.」 | [実行 43675757390](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43675757390)、[PR #53](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/53)（試験用のブランチ `lab-base` で確かめた） |

試していない偽装が 2 つあります。

- 人が、GitHub に登録した自分の鍵で署名し、作者を Dependabot と偽ったコミット。試験に使える登録済みの鍵が無く、実物では試していません。判定は `wasSignedByGitHub` が偽のコミットを弾きます。この分岐は `automation/test_dependabot_merge.py` の `SignatureTest` で確かめています。head を push した主体の条件でも弾かれます
- GitHub の画面で作ったコミット（GitHub の鍵で署名される）。画面では作者が操作した人になり、Dependabot を名乗れません。Dependabot の PR に積むと、コミットが 2 つになるか、head を push した主体が人になります

条件 4 は、この検証の途中で足しました。足す前は、人が Dependabot のコミットに戻した PR #34 が自動マージされました（14:34 に kazufusa が戻し、14:36 にマージ）。入った内容は Dependabot が作ったものですが、過去の更新を人の判断で入れ直せる状態でした。足したあとは、同じ操作が弾かれます（上の表の 3 行目）。

## 鍵の扱い

基本の形は次のとおりです。

- 担当者が App を作り、秘密鍵を生成する
- 担当者が、リポジトリの environment `automerge` に登録する。変数 `AUTOMERGE_APP_ID` に App ID、secret `AUTOMERGE_APP_PRIVATE_KEY` に秘密鍵
- 登録が済んだら、鍵のファイルを消す
- 開発者も、開発に使う AI エージェントも、鍵の中身を見ない。secret は、登録したあとは誰も読み出せない

担当者が単独で実行できる手順とコマンドは、[github-app.md](github-app.md) の「手作業での用意」にあります。この手順の画面操作は、検証用の組織では試していません。
検証用の組織では、同じ内容をスクリプト（`settings/create-app.py`）で行いました。スクリプトも、鍵を画面とファイルに残しません。

登録には、リポジトリの管理者の権限が要ります。担当者に権限が無い場合は、environment の作成までを開発側が行い、登録のあいだだけ権限を渡す形を相談させてください。

## 運用

| 項目 | 内容 | 確かめたか |
|---|---|---|
| 鍵の作り直し | 担当者の交代のときと、漏れの疑いがあるときに行う。定期の周期は、情報システム部門のほかの鍵の決まりに合わせる。この鍵には期限が無く、周期を決める技術上の根拠は無い。手順は github-app.md の「鍵の作り直し」 | 試していない |
| 一時的に止める | リポジトリの workflow `dependabot-merge` を無効にする。または secret を消す。workflow の無効化は、書き込み権限のある人ができる | workflow の無効化と再開は行った。無効の間、振り分けは起動しなかった。secret を消す方法は試していない |
| 完全に外す | 組織の設定で App を Uninstall し、environment の変数と secret を消す | 試していない |
| 記録の追い方 | PR の画面に、App の承認、`automerge` ラベル、キューへの投入、マージが、時刻と主体つきで残る。判定の理由は workflow `dependabot-merge` の実行ログに残る | 試した。上の各 PR の経過がその例 |
| 組織の監査ログ | App の作成、install、ruleset の変更が残るはず | 見ていない。検証用の組織は Free プランで、監査ログの API は 404 を返した。画面は確かめていない |

## 鍵が漏れたときにできること

鍵の持ち主は、App の権限でできることを、このリポジトリに対してすべて行えます。承認だけではありません。

| できること | 止めるもの | 確かめたか |
|---|---|---|
| PR の承認 | ロックファイル以外には所有者のレビューが要る。App は所有者になれない。App が出した PR を App 自身は承認できない | ロックファイル以外を変える PR が、App の承認では通らないことを確かめた（[実行 43676254642](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43676254642)） |
| main へのマージ | ruleset。PR、承認、CI、マージキューを通す必要がある。ロックファイル以外には、所有者のレビューも要る | CI が落ちた PR と、ロックファイル以外を変える PR は、マージキューにも直接のマージにも拒否された（[実行 43676254642](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43676254642)） |
| main への直接の push、main の削除 | ruleset `main`。対象から外す主体は登録していない | 人のアカウントで、push が拒否されることを確かめた。App では試していない |
| main 以外のブランチへの push、作成、削除 | 止めない | 試していない |
| タグの作成、更新、削除。リリースの作成 | タグの ruleset（`settings/ruleset-tags.json`）。管理者だけがタグを作れる | ruleset は入れた。App で拒否されることは試していない |
| workflow のファイル（`.github/workflows/`）の変更 | App に Workflows の権限が無い | 試していない |
| PR へのコメント、ラベル、レビュー依頼、クローズ | 止めない | 試していない |
| ほかのリポジトリへの操作 | install 先がこのリポジトリだけ | install 先は API で確かめた |

止めないものの影響は次のとおりです。

- main 以外のブランチに push できても、main に入れるにはレビューと CI が要ります
- Dependabot の PR のブランチに push すると、その PR は自動マージの対象から外れます（条件 4）
- 人が出した、ロックファイルだけを変える PR は、鍵の持ち主が App で承認し、App でマージキューに入れると通ります。書き込み権限のある人と鍵の持ち主が組むと、ロックファイルの変更を人のレビューなしで入れられます。CI は通す必要があります。App がこの形の PR をキューに入れられることは、実物で確かめました（[実行 43676422072](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43676422072)。キューからは、マージの前に外しました）
- main 以外のブランチやタグから配布や公開をしているリポジトリでは、そのブランチとタグにも ruleset が要ります

漏れに気づいたときは、App の設定画面で鍵を消します。消した鍵は、その時点で使えなくなります。

## リポジトリを増やすとき

リポジトリを増やす予定はありません。App を分けるか、使い回すかは、検討していません。

## 検証で行った保護の一時解除

この検証は、人が 1 人だけの組織で行いました。
ruleset は「自分の PR を自分で承認できない」ので、ruleset を入れたあとは、main を変える手段がありません。
そのため、main の変更のたびに、main にかかる ruleset を無効にし、push し、すぐ有効に戻しました。回数は 50 回です（2026-11-14 に 15 回、11-15 に 35 回）。
11-15 の途中からは、`owners-lockfiles` と `owners-others` も同時に無効にしています。無効の時間は、それぞれ数秒です。
組織の監査ログには、ruleset の変更として残るはずです。
人が 2 人以上いる組織では、この操作は要りません。

ruleset の対象から外す主体は、1 つだけ登録しています。`owners-lockfiles`（ロックファイルの所有者のレビュー）に、自動マージの App です。
`main`（PR、承認、CI、マージキュー）と `owners-others`（ロックファイル以外の所有者のレビュー）には、登録していません。

## cooldown の効く範囲

cooldown は 7 日に設定しています。ただし、配布元によって効くものと効かないものがあります。
設定は受け付けられ、警告も出ないので、効いていないことに気づきにくい点に注意が要ります。

| 配布元 | cooldown | 確かめ方 | 実例 |
|---|---|---|---|
| Docker Hub のイメージ | 効く | このリポジトリの Dependabot の実行 | terraform は 1.17.2（公開 3 日後）ではなく 1.17.1、node は 24.22.3 ではなく 24.22.2、python は 3.13.18 ではなく 3.13.17 が選ばれた。ログは「Skipping tag 1.17.2 due to cooldown period」 |
| Docker Hub 以外のイメージ（ghcr.io など） | 効かない | このリポジトリの Dependabot の実行 | ghcr.io の uv は、公開 2 日後の 0.13.8 が選ばれた（[PR #23](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/23)）。ログは「No verified registry publication date source for ghcr.io; skipping cooldown for astral-sh/uv:0.13.8」 |
| PyPI | 効く | このリポジトリの Dependabot の実行 | humanize は 4.17.0（公開 2 日後）ではなく 4.16.0 が選ばれた。ログは「Filtered out 1 versions due to cooldown」 |
| npm | 効く | 手元で Dependabot の本体を動かした | libphonenumber-js は、公開 4 日後の 1.13.16 が提案されなかった。cooldown を 0 日にすると提案された |
| Terraform のレジストリ | 効く | 手元で Dependabot の本体を動かした | hashicorp/azurerm は、公開 1 日後の 5.14.0 が提案されなかった。cooldown を 0 日にすると提案された |
| GitHub Actions | 効く。ただし数え方が違う | 手元で Dependabot の本体を動かした | 公開 4 日後のバージョンは提案されず、1 つ前のバージョンが提案された。日数は、公開日ではなく、タグが指すコミットの日付で数えていた。古いコミットにあとからタグを付けたバージョンは、公開の直後でも cooldown を通る |
| セキュリティアップデート | かからない | 試していない | GitHub の仕様では、cooldown はセキュリティアップデートにかからない。このリポジトリで出たセキュリティアップデートは、どれも公開から 7 日以上たったバージョンだったので、実例にならない |

「手元で動かした」は、Dependabot の本体（dependabot-core）を dependabot CLI で動かした結果です。GitHub のサービス上の実行ではありません。
Docker Hub 以外で効かない理由は、Dependabot の実装にあります。イメージの公開日を取る処理が Docker Hub にしか無く、取れないときは cooldown を飛ばします（dependabot-core の `docker/lib/dependabot/docker/update_checker.rb`）。ghcr.io に限らず、Docker Hub 以外のレジストリは同じ扱いです。
cooldown を設定に書かない場合も、Dependabot の本体は 3 日の cooldown をかけます。

自動マージの対象になるのは、ロックファイルだけを変える更新です。配布元は PyPI、npm、Terraform のレジストリの 3 つです。
コンテナイメージと GitHub Actions の更新は、バージョンを書いたファイルが変わるので、cooldown が効くかどうかに関係なく、所有者のレビューを通ります。

コンテナイメージは Docker Hub のものを使う決まりにしました。
uv のイメージを ghcr.io から Docker Hub（`astral/uv`、中身は同じ）に替えたところ、0.13.8 ではなく、cooldown を満たす 0.13.7 が提案されました（[PR #35](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/35)、[実行 43611591787](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43611591787)。ログは「Skipping tag 0.13.8 due to cooldown period」）。Docker Hub 以外のイメージを `FROM` に書くと、CI（`automation/versions.py check`）が落ちます。
Docker Hub に無いイメージを使うときは、cooldown が効かないと承知したうえで、人のレビューで守ります。
Docker Hub には、認証なしで取得できる回数に制限があります。CI が取得で失敗するようになったら、認証を足します。

## 残る危険

仕組みでは塞げないものです。受け入れるかどうかの判断を、情報システム部門とリポジトリの責任者にお願いします。

- リポジトリの管理者は、environment の使えるブランチや、ruleset を変えられます。管理者は、App が無くても保護を外せる立場です。管理者を絞ることが対策です
- 鍵が漏れたときにできることは、上の表のとおりです
- 配布元で悪意のある patch が公開され、cooldown の日数を過ぎても発覚せず、CI も通ると、自動で入ります。cooldown は発覚までの時間を取るもので、防ぐものではありません
- セキュリティアップデートの patch は、cooldown なしで自動で入ります。対象は、GitHub の脆弱性のデータベースに登録された修正に限られます。CI は通す必要があります。修正のバージョンそのものに悪意のある変更が混ざっていた場合、cooldown による猶予はありません
- Python と Node のセキュリティアップデートは、外部の公開情報（nodejs.org、OSV、python/cpython）で見分けます。情報が誤っていると、通常のバージョンを待たずに PR にするか、修正のバージョンを見逃します。どちらの場合も、PR のマージには所有者のレビューが要り、見逃したバージョンは 7 日後に通常の更新として出ます
- 人が出した、ロックファイルだけを変える PR は、人の操作では、所有者の承認なしに通りません。通せるのは App だけです。App の判定は Dependabot の PR だけを対象にするので、この経路が開くのは、鍵が漏れたときか、判定に誤りがあるときです
- 判定の workflow は、GitHub が配る部品（`actions/checkout`）を 1 つ使います。動かすコミットは、workflow のロックファイル（`.github/workflows/actions.lock`）で固定しています

悪意のある更新が入ったと分かったときの手順は次のとおりです。

1. 止める。リポジトリの書き込み権限のある人が、workflow `dependabot-merge` を無効にする。組織の所有者は、App を止める（Suspend）こともできる。Suspend は試していない
2. 探す。`automerge` ラベルの付いたマージ済みの PR を一覧にする。PR には、更新した依存とバージョン、承認とマージの時刻が残っている
3. 戻す。その PR を打ち消す PR を出す。人が出す PR なので、通常のレビューを通る

## 作業のあとに確かめる項目

- [ ] App の権限が、Contents と Pull requests の書き込みだけになっている
- [ ] App の Webhook が無効になっている
- [ ] install 先が、依頼したリポジトリ 1 つだけになっている
- [ ] environment `automerge` の使えるブランチが main だけになっている
- [ ] environment `automerge` に、変数 `AUTOMERGE_APP_ID` と secret `AUTOMERGE_APP_PRIVATE_KEY` がある
- [ ] 組織とリポジトリの「GitHub Actions による PR の承認」が無効になっている
- [ ] 鍵のファイルが、手元に残っていない
- [ ] App の管理者に、不要な人が入っていない

最初の 6 つは、次のコマンドで確かめられます。

```sh
repo=<owner>/<repo>
gh api "orgs/${repo%%/*}/installations" \
  --jq '.installations[] | {app_slug, repository_selection, permissions, events}'
gh api "repos/$repo/environments/automerge/deployment-branch-policies" --jq '.branch_policies[].name'
gh api "repos/$repo/environments/automerge/variables" --jq '.variables[].name'
gh api "repos/$repo/environments/automerge/secrets" --jq '.secrets[].name'
gh api "orgs/${repo%%/*}/actions/permissions/workflow" --jq '.can_approve_pull_request_reviews'
gh api "repos/$repo/actions/permissions/workflow" --jq '.can_approve_pull_request_reviews'
```
