# GitHub App の作成の依頼書

情報システム部門の担当者に、GitHub App の作成を依頼するための文書です。
開発の文脈を知らなくても読めるように書いています。作業の手順は [github-app.md](github-app.md) にあります。

この文書の実例は、検証用の組織 `kazufuuu` のリポジトリ `dependabot-merge-queue-lab` で、2026-11-14 に確かめたものです。

## 依頼の要点

- GitHub App を 1 つ作り、指定したリポジトリ 1 つにだけ入れてください
- 権限は、Contents と Pull requests の書き込みの 2 つだけです
- 秘密鍵は担当者が作り、担当者がリポジトリの所定の場所に登録してください。開発者は鍵の中身を見ません
- App が行うのは、条件を満たした依存の更新を承認し、マージの待ち行列に入れることだけです

## 用語

| 用語 | 意味 |
|---|---|
| Dependabot | GitHub の機能。使っているライブラリの新しい版を見つけ、更新の PR を自動で出す |
| PR | pull request。変更を main に入れる前の、レビューの単位 |
| patch の更新 | 版の 3 つ目の数字だけが上がる更新（1.2.3 から 1.2.4）。不具合の修正が中心 |
| ロックファイル | 実際に使う版を記録するファイル。人が書くのではなく、道具が書き出す |
| 検査 | PR ごとに自動で動くテスト |
| マージキュー | 承認済みの PR を並べ、最新の main と合わせて検査し直してから入れる、GitHub の待ち行列 |
| workflow | リポジトリに置いた自動処理（GitHub Actions） |
| `GITHUB_TOKEN` | workflow に自動で渡る、そのリポジトリ用の一時的な権限 |
| environment | secret の置き場所。使えるブランチを絞れる |

## 目的

依存の更新のうち、危険の小さいものを人の手を介さずに取り込みます。
対象は、patch の更新で、ロックファイルだけが変わり、検査が通ったものです。
それ以外の更新は、これまでどおり人がレビューします。

## App が要る理由

workflow の `GITHUB_TOKEN` だけでは、マージキューを使った自動マージが成り立ちません。
`GITHUB_TOKEN` で PR をマージキューに入れると、キューの検査が起動せず、PR が待ったままになります。
`GITHUB_TOKEN` が起こした出来事は、ほかの workflow を起動しない決まりだからです。

実例は次のとおりです。

| 入れた主体 | 結果 | 証拠 |
|---|---|---|
| `GITHUB_TOKEN` | キューの検査が起動しない。3 分待っても検査待ちのまま | [PR #12 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12)（13:30:23 に `github-actions` が投入） |
| `GITHUB_TOKEN`、検査を別の方法で起動 | 検査は成功したが、キューは 16 分進まない | [実行 43600679442](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43600679442)、[PR #15 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/15) |
| 人のアカウント | キューの検査が起動し、46 秒後にマージ | [実行 43602072881](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43602072881) |
| GitHub App | キューの検査が起動し、71 秒後にマージ | [実行 43605089530](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605089530)、[PR #12](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12) |

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

| 権限 | 水準 | 使う操作 |
|---|---|---|
| Contents | 書き込み | PR をマージキューに入れ、main に入れる |
| Pull requests | 書き込み | PR を承認する。`automerge` ラベルを付ける |
| Metadata | 読み取り | GitHub が自動で付ける |

この 2 つで足りることは、実物で確かめました。[PR #12](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/12) と [PR #34](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/34) は、この権限だけの App が承認し、マージしています。
Webhook は使いません。App は外部のサーバーを持たず、通知も受け取りません。

## 範囲

- 入れるのは、依頼するリポジトリ 1 つだけです。install のときに「Only select repositories」で選びます
- 組織全体には入れません
- App は公開しません。ほかの組織からは install できません

## App の動き

App のトークンを使うのは、リポジトリの workflow `dependabot-merge` の、`merge` という job だけです。
この job は、次の条件をすべて満たす PR だけを承認し、マージキューに入れます。

1. PR の作成者が Dependabot である
2. コミットが 1 つだけで、Dependabot が作り、GitHub の署名が付いている
3. 変わったファイルがロックファイルだけである
4. 更新がすべて patch のグループに属している。脆弱性の修正として出る更新（セキュリティ更新）はグループに属さないので、対象にならない
5. 検査がすべて通っている

App がしないことは次のとおりです。

- 人が出した PR を承認しない
- ロックファイル以外が変わる PR を承認しない。ロックファイル以外には所有者（CODEOWNERS）がいて、所有者のレビューが必須だからです。App は所有者になれません
- 検査が落ちた PR を承認しない
- main に直接 push しない。main への変更は、PR とマージキューを必ず通ります

この動きを保証している仕組みは次のとおりです。

| 仕組み | 効き目 |
|---|---|
| 判定は main に入っている版で動く | PR の中身で判定を書き換えられない。判定を変えるには、所有者のレビューを通す必要がある |
| 鍵は environment `automerge` の secret に置く。この environment は main だけが使える | main 以外のブランチの workflow は、鍵を読めない |
| ブランチ保護（ruleset）で、所有者のレビューを必須にする | App の承認だけで通るのは、所有者のいないロックファイルだけを変える PR に限られる |
| 必須の検査は、全部のテストをまとめた 1 つ | テストの一部だけが動いて通る、ということが起きない |
| マージキューで、最新の main と合わせて検査し直す | 単独では通るが、合わせると壊れる変更が入らない |

## 悪用への備え

実際に試した結果です。

| 試したこと | 結果 | 証拠 |
|---|---|---|
| main 以外のブランチの workflow から、鍵を読む | job が起動しない。「Branch "probe/approval-bypass" is not allowed to deploy to automerge due to environment protection rules.」 | [実行 43605292206](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605292206) の `read-key` |
| main 以外のブランチの workflow から、`GITHUB_TOKEN` で PR を承認する | 422 で拒否。「GitHub Actions is not permitted to approve pull requests.」 | 同じ実行の `approve-with-github-token` |
| Dependabot の PR のブランチに、人がコミットを積む | 自動マージの対象から外れ、人に依頼が回る。「コミットが 2 個あります / Dependabot の署名の無いコミットがあります」 | [実行 43605421916](https://github.com/kazufuuu/dependabot-merge-queue-lab/actions/runs/43605421916)、[PR #34 の経過](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/34) |
| 検査が落ちる patch の更新 | 承認されない。`needs-review` ラベルが付き、人に依頼が回る | [PR #16](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/16) |
| セキュリティ更新 | 承認されない。人に依頼が回る | [PR #10](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/10) |

PR #34 では、人のコミットを取り除いて Dependabot のコミットだけに戻したあと、自動マージされました。
head が Dependabot の署名付きのコミットであれば、誰がブランチを戻したかは問いません。入るのは Dependabot が作った内容だけです。

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
| 鍵の作り直し | 年に 1 回と、担当者の交代のときを提案します。手順は github-app.md の「鍵の作り直し」 | 試していない |
| 一時的に止める | リポジトリの workflow `dependabot-merge` を無効にする。または secret を消す | workflow の無効化と再開は行った。無効の間、振り分けは起動しなかった。secret を消す方法は試していない |
| 完全に外す | 組織の設定で App を Uninstall し、environment の変数と secret を消す | 試していない |
| 記録の追い方 | PR の画面に、App の承認、`automerge` ラベル、キューへの投入、マージが、時刻と主体つきで残る。判定の理由は workflow `dependabot-merge` の実行ログに残る | 試した。上の各 PR の経過がその例 |
| 組織の監査ログ | App の作成、install、権限の変更が残るはず | 見ていない |

## 残る危険

仕組みでは塞げないものです。受け入れるかどうかの判断を、情報システム部門とリポジトリの責任者にお願いします。

- リポジトリの管理者は、environment の使えるブランチや、ブランチ保護を変えられます。管理者は、App が無くても保護を外せる立場です。管理者を絞ることが対策です
- 鍵が漏れると、持ち主はこのリポジトリの PR を承認できます。それでも、ロックファイル以外の変更には所有者のレビューが要り、検査も通す必要があります。ほかのリポジトリには何もできません
- 配布元で悪意のある patch が公開され、検査も通ると、自動で入ります。公開から 7 日たった版だけを取り込む設定（cooldown）で、発覚までの時間を取っています
- 人が出した、ロックファイルだけを変える PR は、所有者ではない誰か 1 名の承認で通ります。App は関わりませんが、ロックファイルを所有者なしにしたことの帰結です
- 判定の workflow は、GitHub が配る部品（`actions/checkout`）を 1 つ使います。版はコミットの値で固定しています

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
