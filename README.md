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
| `.github/workflows/dependabot-auto-merge.yml` | ロックファイルだけを変える patch のグループを承認し、auto-merge を予約して `automerge` ラベルを付けます |
| `.github/workflows/dependabot-review-request.yml` | Dependabot の PR に、team へのレビュー依頼を付けます |
| `.github/workflows/terraform-version.yml` | Terraform 本体の版を上げる PR を作ります |

ランタイムの版は Dockerfile の `FROM` の 1 か所で決めます。
`.python-version` と `.node-version` は minor までにして、検査の workflow が `FROM` から patch を読みます。

## 設定

リポジトリ設定と ruleset は `settings/` に置いてあり、次のスクリプトで反映します。

```sh
scripts/apply-settings.sh
```

ruleset `protect-main` は、承認 1 件、コード所有者のレビュー、必須の検査 `shared`、merge queue を求めます。
CODEOWNERS は、ロックファイルを除く全ファイルを team `reviewers` の所有にしています。
レビュー依頼の宛先は、リポジトリ変数 `REVIEW_TEAM`（team の slug）で決めます。

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

このリポジトリでの結果は、確かめたものから書き足します。
