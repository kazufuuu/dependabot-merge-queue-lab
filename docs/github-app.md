# 自動マージ用の GitHub App

patch の更新を自動で承認し、マージキューに入れるための GitHub App を用意する手順です。
ほかのリポジトリに同じ仕組みを入れるときも、この文書の手順で再現できます。

## App が要る理由

理由は 2 つあります。

1 つ目は、マージキューの CI です。
workflow の `GITHUB_TOKEN` で PR をマージキューに入れると、`merge_group` の CI が起動しません。
`GITHUB_TOKEN` が起こしたイベントは、workflow を起動しないためです。
このリポジトリでは、キューに入った PR が CI 待ちのまま 3 分以上動かないことを確かめました。
同じ PR を人のアカウントで入れ直すと、CI が起動し、30 秒ほどでマージされました。
キューのブランチを指して CI を `workflow_dispatch` で起動する方法も試しました。CI は成功しましたが、キューは 16 分たっても進みませんでした。

2 つ目は、承認の権限です。
`GITHUB_TOKEN` に承認を許すと、書き込み権限のある人は誰でも、自分のブランチに足した workflow で PR を承認できます。
App に承認させると、承認できるのは鍵を使える workflow だけになります。
鍵は main だけが使える environment に置くので、main に入っている workflow しか承認できません。

## 用意の手順

`.github/settings/create-app.py` を使います。画面での操作は、ボタンを 2 回押すことと、install 先を選ぶことだけです。
組織の所有者で、リポジトリの管理者でもある人が行います。`gh` でログインしておきます。

1. environment を作る。`.github/settings/apply.sh <owner>/<repo>` が、main だけが使える environment `automerge` を作る
2. スクリプトを動かす

   ```sh
   .github/settings/create-app.py <owner>/<repo>
   ```

   App の名前は `<owner>-dependabot-automerge` になる。変えるときは `--name` を付ける。名前は GitHub 全体で重ならないものにする
3. 表示された `http://localhost:8765/` をブラウザで開き、ボタンを押す。GitHub の画面に移るので、App の作成を確かめるボタンを押す
4. スクリプトが、App ID を environment の変数 `AUTOMERGE_APP_ID` に、秘密鍵を secret `AUTOMERGE_APP_PRIVATE_KEY` に登録する
5. スクリプトが表示する install の URL を開く。Only select repositories を選び、対象のリポジトリだけを選んで install する
6. スクリプトが install を確かめ、対象のリポジトリと権限を表示して終わる
7. `.github/settings/apply.sh <owner>/<repo>` をもう一度動かす。ロックファイルの所有者のレビューを、App にだけ求めない設定が入る。App を作る前の 1 回目では、この設定は入らない

スクリプトがしていることは次のとおりです。

- App の定義（manifest）を GitHub に送るページを、手元で出す。定義の中身は、公開しない、Webhook を使わない、権限は Contents と Pull requests の書き込みだけ、の 3 点
- GitHub から戻ってきた一時的な code を、App ID と秘密鍵に換える。code は 1 時間で切れるので、すぐに換える
- 秘密鍵を `gh secret set` に標準入力で渡す。秘密鍵は、画面にもファイルにも残さない。署名のあいだだけ一時ファイルに置き、すぐ消す

Contents の書き込みは、マージキューに入れてマージするために要ります。
Pull requests の書き込みは、承認とラベルのために要ります。

WSL2 では、Windows 側のブラウザから `localhost:8765` に届きます。届かない環境では、下の手作業の手順を使います。

## 手作業での用意

スクリプトを使えないときの手順です。この手順は、このリポジトリでは試していません。

### App の作成

組織の所有者が行います。

1. `https://github.com/organizations/<組織>/settings/apps/new` を開く
2. 名前を付ける。名前は GitHub 全体で重ならないものにする
3. Homepage URL に、リポジトリの URL を入れる
4. Webhook の Active を外す
5. Repository permissions を次のとおりにする。ほかは No access のままにする
   - Contents: Read and write
   - Pull requests: Read and write
6. 「Where can this GitHub App be installed?」は Only on this account を選ぶ
7. 作成後の画面で、App ID を控える
8. 同じ画面の Private keys で Generate a private key を押し、鍵のファイル（`.pem`）を保存する

### install

1. App の設定画面で Install App を開き、組織を選ぶ
2. Only select repositories を選び、対象のリポジトリだけを選ぶ

### 鍵の登録

environment は `.github/settings/apply.sh <owner>/<repo>` が作ります。名前は `automerge` で、使えるブランチは main だけです。
手で作る場合は、次のコマンドを使います。

```sh
repo=<owner>/<repo>
gh api -X PUT "repos/$repo/environments/automerge" --input - <<'JSON'
{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
gh api -X POST "repos/$repo/environments/automerge/deployment-branch-policies" -f name=main -f type=branch
```

App ID と秘密鍵を、environment に置きます。

```sh
gh variable set AUTOMERGE_APP_ID --env automerge --repo "$repo" --body <App ID>
gh secret set AUTOMERGE_APP_PRIVATE_KEY --env automerge --repo "$repo" < <保存した鍵のファイル>
```

登録が済んだら、鍵のファイルは手元から消します。

## App を入れたあとに切る設定

「GitHub Actions による PR の承認」を無効にします。

- リポジトリは `.github/settings/apply.sh` が無効にします。画面では Settings、Actions、General の Workflow permissions にあります
- 組織は、所有者が次のコマンドで無効にします。画面では、組織の Settings、Actions、General の同じ項目です

```sh
echo '{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}' |
  gh api -X PUT orgs/<組織>/actions/permissions/workflow --input -
gh api orgs/<組織>/actions/permissions/workflow
```

組織の設定は、値を JSON で渡します。`-F` で渡したときは、エラーにならないまま値が変わりませんでした。

## 動作の確かめ方

このリポジトリで確かめた結果は、[app-request.md](app-request.md) に実行の URL つきで書いています。

- patch の更新で、ロックファイルだけを変える Dependabot の PR を待つ。CI が通ると、App が承認し、`automerge` ラベルが付き、マージキューを通ってマージされる
- main 以外のブランチに、`environment: automerge` を指定した job を足す。その job は、ブランチが許可されていないという理由で動かない
- main 以外のブランチに、`GITHUB_TOKEN` で PR を承認する workflow を足す。承認の API は 422 で失敗する

## 運用

鍵の作り直しと、App を外す手順は、このリポジトリでは試していません。
鍵が漏れたときにできることと、リポジトリを増やすときの考え方は、[app-request.md](app-request.md) にあります。

### 鍵の作り直し

1. App の設定画面の Private keys で、新しい鍵を作る
2. 「鍵の登録」のコマンドで、secret を新しい鍵に置き換える
3. 振り分けの workflow を手動で動かし、成功を確かめる
4. App の設定画面で、古い鍵を消す

### 一時的に止める

振り分けの workflow を無効にします。再開するときは `enable` を使います。

```sh
gh workflow disable dependabot-merge --repo <owner>/<repo>
```

### App を外す

1. 組織の Settings、GitHub Apps で、App を Uninstall する
2. environment `automerge` の変数と secret を消す

App を外すと、自動マージは止まります。Dependabot の PR へのラベルは、`GITHUB_TOKEN` で続きます。レビューの依頼は、GitHub が CODEOWNERS から付けます。

### 設定を変えられる人

- App の権限と鍵: 組織の所有者と、App の管理者に加えた人
- environment の secret と、使えるブランチ: リポジトリの管理者
- 振り分けの判定: main に入る変更。所有者のレビューが要る
