# dependabot-merge-queue-lab

Dependabot の更新を、少ない手間で回す設定を試すためのリポジトリです。
依存の版をわざと古いものに固定してあり、Dependabot を動かすと更新の PR が出ます。

## ねらい

- 版の書かれた場所すべてに、更新の PR が自動で出る
- ロックファイルだけを変える patch の更新は、人の操作なしでマージされる
- それ以外の PR には、所有者の team へのレビュー依頼が付く
- マージは merge queue を通すので、ブランチが古くなっても待たされない

## 構成

| 場所 | 内容 |
|---|---|
| `pyproject.toml`・`uv.lock`・`shared/`・`slack/` | uv workspace |
| `web/api/` | workspace の外の独立した uv プロジェクト |
| `web/ui/` | 版を完全固定にした npm プロジェクト |
| `web/ui-caret/` | 版を `^` の範囲にした npm プロジェクト |
| `web/mock/` | `dependabot.yml` の対象にしていないディレクトリ |
| `web/`・`web-fromuv/`・`shared/migrations/`・`tools/gitleaks/` | Dockerfile |
| `infra/terraform/` | Terraform の `versions.tf` と lock ファイル |
| `.github/workflows/shared.yml` | 必須の検査。PR と merge queue の両方で動きます |
| `.github/workflows/web.yml`・`slack.yml` | paths で絞った検査 |
| `.github/workflows/dependabot-auto-merge.yml` | ロックファイルだけを変える patch のグループを承認し、auto-merge を予約して `automerge` ラベルを付けます。ほかの Dependabot の PR にはレビューを依頼します |
| `.github/workflows/dependabot-review-request.yml` | 自動マージの候補が、PR の検査か merge queue で落ちたときにレビューを依頼します |
| `.github/workflows/terraform-version.yml` | Terraform 本体の版を上げる PR を作り、その PR で `shared` を起動します |

ランタイムの版は Dockerfile の `FROM` の 1 か所で決めます。
`.python-version` は minor まで、`.node-version` は major までにして、検査の workflow が `FROM` から patch を読みます。
Dependabot は、`python` を patch だけ、`node` を major の手前まで上げます。
version file の範囲を越える更新は、人が version file と一緒に変えます。

## 設定

リポジトリ設定と ruleset は `settings/` に置いてあり、次のスクリプトで反映します。

```sh
scripts/apply-settings.sh
```

ruleset `protect-main` は、承認 1 件、コード所有者のレビュー、必須の検査 `shared`、merge queue を求めます。
CODEOWNERS は、ロックファイルを除く全ファイルを team `reviewers` の所有にしています。
レビュー依頼の宛先は、リポジトリ変数 `REVIEW_TEAM`（team の slug）と `REVIEWER`（個人）で決めます。
`GITHUB_TOKEN` では team への依頼が通らないので、workflow は `REVIEWER` に依頼します。

組織の設定で、GitHub Actions による PR の承認を許可しておく必要があります。

## これまでに分かっていること

別のリポジトリ（個人アカウント、merge queue なし）で先に確かめた結果です。

- ロックファイルだけを変える PR は、bot の承認と必須の検査だけでマージされました
- 所有者のいるファイルを変える PR は、bot が承認してもレビュー待ちで止まりました
- Dockerfile の `FROM` は複数のディレクトリが 1 本にまとまって更新されました。`COPY --from` に書いた版は更新されません
- GitHub Actions は、コミットの SHA とコメントの版の両方が更新されました
- uv は `lockfile-only` にすると `uv.lock` だけが変わります。ただし範囲を超える更新と、完全固定の依存の PR は出ません
- npm は `increase-if-necessary` にすると、範囲の中は `package-lock.json` だけ、範囲を超えると `package.json` も変わりました
- Terraform 本体の版を上げる workflow は PR を作れましたが、`GITHUB_TOKEN` で作った PR では検査が動きませんでした

## このリポジトリで確かめたこと

組織の public リポジトリ（Free プラン）での結果です。

- 最初の実行で、Dependabot は uv（workspace）、npm 2 か所、Dockerfile、GitHub Actions、Terraform のプロバイダの PR を出しました（#1〜#6）
- 独立した uv プロジェクト（`web/api`）の PR は出ませんでした。ロックファイルが最新で、残りの依存は完全固定だったためです
- uv の workspace の実行は、メンバーの `shared` を解けないというエラーを記録しました。PR #1 はそれでも作られました
- 所有者のいるファイルを変える PR には、CODEOWNERS から team への依頼が自動で付きました
- `GITHUB_TOKEN` で team にレビューを依頼すると、422（`Could not resolve to a node`）になりました
- Dockerfile の PR は、patch を越えて最新の minor・major に上がりました（#4）。`web` の検査は version file との不一致で落ちました
- PR の承認の許可が無効のとき、承認の step は 422 で落ちました
- 自動マージの workflow を人が再実行すると、承認の step は動きません（`triggering_actor` が人になるため）
- `@dependabot rebase` は、ブランチが最新の PR には何もしません。`@dependabot recreate` には、20 分待っても応答がありませんでした

## まだ確かめていないこと

- ロックファイルだけの patch の PR が、merge queue を通って人の操作なしでマージされるか
- レビュー依頼の個人への切り替えと、検査や merge queue で落ちたときの依頼
- Docker の更新の範囲を絞ったあとの PR
- セキュリティ更新の PR。alerts は有効ですが、まだ 1 件も出ていません
- Terraform 本体の PR で、起動した `shared` が必須の検査として扱われるか
- 1 本のマージのあと、残りの自動マージの PR が人の操作なしで進むか
