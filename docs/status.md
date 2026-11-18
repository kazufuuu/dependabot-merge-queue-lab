# 要件の達成の状況

[requirements.md](requirements.md) の要件ごとに、どこまで出来ているかを書きます。2026-11-18 時点のものです。
実現の方法は [README](../README.md) に、証拠は [app-request.md](app-request.md) にあります。

| 番号 | 状況 | 残っていること |
|---|---|---|
| 1 | 満たす | 人の判断待ちの minor の PR が開いた状態で、patch の PR が自動でマージされた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70)、[#79](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/79)、[#85](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/85)、[#87](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/87)）。Dependabot の push からマージまで 2〜3 分。`==` で固定していた ruff は、範囲に直すと、同じ patch の PR がロックファイルだけの変更になり、自動でマージされた（[PR #86](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/86)）。semver の判定は、名指しされた直接の依存の上がり幅で行う。ロックファイルの中で動く間接の依存の上がり幅は、判定に使わない（[PR #80](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/80) は pydantic の minor だが、間接の pydantic-core も上がる。[PR #77](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/77) は vitest 群の minor だが、間接の依存が major で上がる。どちらも、名指しされた依存の上がり幅で扱う） |
| 2 | 満たす | 出す範囲は設定に入れた。Python は patch だけ、Node は同じ major の中だけ、Terraform は全部。uv はライブラリの線に戻し、直下の設定から出た patch の PR が自動でマージされた（[PR #93](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/93)、PR が出てから 2 分 24 秒）。uv を上げないまま、Python の patch で CI が通った。Dependabot の本物の PR で確かめた（[PR #101](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/101)。Python 3.13.18、uv は 0.13.7 のまま）。Node は同じ major の中の minor（[PR #102](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/102)）、Terraform は minor（[PR #103](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/103)）の PR が出ている。3 本とも、`.python-version` などを書き換えるコミットが積まれ、CI が通り、人の判断待ちになった。Terraform の major は、新しい major がまだ無いので、実物では見ていない。止める設定が無いことだけを確かめた。Node の 24.22.3 と Terraform の 1.17.2 は、cooldown の中なので、まだ出ていない。Dependabot が PR を作り直さなかった例が 1 つある（[PR #78](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/78)。Dependabot 用の Dockerfile の書き方をこちらが変えたあとの衝突。`@dependabot recreate` に 1 時間たっても反応が無く、原因は分かっていない）。この PR は、Dependabot 用の Dockerfile を移したときに閉じた。見立てでは、ふだんの運用では起きにくい。この見立ては確かめていない。Dependabot 用の Dockerfile から外した uv の PR（[PR #74](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/74)）は、Dependabot が閉じなかったので、人が閉じた |
| 3 | 満たす | テストが落ちた patch の PR は、自動でマージされず、`needs-review` が付いた（[PR #81](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/81)）。本番のイメージのビルドだけが落ちた PR も、`all-green` が落ちた（[PR #47](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/47)） |
| 4 | 満たす | ruleset は、ブランチが最新であることを求めない（`strict_required_status_checks_policy` が false）。マージキューが、最新の main と合わせて CI を動かし直す（[PR #79](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/79)） |
| 5 | 満たす | なし |
| 6 | 満たす | 所有者の作り直しのあとも、App はロックファイルだけの PR を、所有者のレビューの免除でマージキューに入れた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70) は 06:01:39 に投入、06:02:31 にマージ。承認は App の 1 件だけ）。人が自分の鍵で署名して Dependabot を名乗るコミットは、実物では試していない。置き方を `.github` の下へ移し、振り分けの直しを入れたあとも、自動マージが実物で通った（[PR #108](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/108)。ruff のロックを下げて Dependabot に patch の PR を出させ、App が 15:41:42 に承認、merge_group の CI が通り、15:42:55 にマージ。PR から約 3 分。このとき、必須のチェックの発行元の固定（integration_id）も入っていた） |
| 7 | 一部 | 割り振りの設定は入れた。組織のメンバーが 1 人なので、偏らないことと、人数を変えたときの動きは、実物で確かめていない |
| 8 | 満たす | 開発用の依存（pytest、ruff、just など）は、直下の `pyproject.toml` に範囲で書いてあり、ライブラリと同じ設定が追う |
| 9 | 一部 | 判定と、Python と Node の見分けは入れた。uv は PyPI のパッケージなので、Dependabot のセキュリティアップデートに任せる。ライブラリのセキュリティアップデートが自動でマージされるところは、実物でまだ確かめていない |
| 10 | 満たす | なし |
| 11 | 満たす | Python と Node は、バージョンを書いたファイル（`.python-version`、`.node-version`）を、手元の道具、CI、本番のイメージのビルドが読む。手元のバージョンが違うとテストが落ちる。uv は、CI と本番のイメージが `uv.lock` の同じバージョンを使う。手元の uv は下限（0.13）だけ。道具で実際に入れるところは試していない。Node のテストが落ちる側は確かめていない |
| 12 | 満たす | なし |
| 13 | 満たす | 依存ごとの PR にしたあとの CI の回数は、PR 1 本につき 1 回（README の「PR の本数と CI の回数」）。自動でマージされる PR は、マージキューの 1 回と、main に入ったあとの 1 回が加わる。同じロックファイルの patch が 3 本以上重なった場合は、測れていない。CI の job は、手元と同じ `justfile` のレシピを呼ぶ。job とレシピの名前は同じ。どの job も、`uv run just` で呼ぶ |
| 14 | 満たす | App の鍵の入れ替え、App の停止と削除は、試していない |
| 15 | 一部 | 無視するための設定は README に示した。GitHub の文書で確かめたもので、実物では試していない。通知の数は、設定からの上限（週に最大 17 件）で示した。自動でマージされた PR は、2 日間で 9 本。メールの通数は確かめていない |
| 16 | 満たす | patch、minor、major の 5 件が、1 本の PR にまとまって出た（[PR #69](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/69)）。週 1 本になることは、確認の間隔（週 1 回）からの見込みで、複数の週では見ていない |
| 17 | 満たす | 種類でまとめるグループをやめた。バージョンが連動する群（vitest と @vitest/coverage-v8）だけをまとめ、2 件が 1 本で出た（[PR #77](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/77)）。ランタイムのセキュリティアップデートの PR は、Python と Node で分けた。分けた形で PR が出るところは、単体テストだけの裏付け。次のセキュリティのバージョンで確かめる |
| 18 | 一部 | リリースの workflow（`release.yml`）で、イメージの SBOM（OS と Python）、フロントの本番の依存の SBOM（`npm sbom --omit dev`）、来歴、署名付きの証明を作り、Release に添付する。試しのタグ v0.0.2 で実物を通した。`sbom-find` で、`openssl 3.5.7-1~deb13u3` と `date-fns 4.1.0` が引けた。main に入っていないコミットのタグ（v0.0.99）では、ガードで止まり、何も出なかった。一部の理由: 記録を作る前にイメージが ghcr に置かれ、途中が失敗すると SBOM の無いイメージが残りうる、フロントの SBOM は署名が無い（同じコミットの `package-lock.json` から作り Release に添付して結び付ける）、supplier などが空（supplier は一部、確定したライセンスと OS のパッケージのハッシュは空）、署名付きの証明の保持の期間は未確認、走査の道具が動くタグで引かれる。詳しくは [app-request.md](app-request.md) の「リリースの記録と、監査への答え」 |

## 満たしていない要件を妨げているもの

### 9: セキュリティアップデートの自動マージの確認

古いセキュリティアップデートの PR は、壊れていたので閉じました。Dependabot は「閉じれば作り直す」と返しましたが、まだ出し直していません。
判定は単体テストで確かめています。実物のセキュリティアップデートが自動でマージされるところは、見ていません。
実物では、警告が作られた直後に Dependabot が修正の PR を出した例（PR #9、#10 など）と、出なかった例があります。

開いている警告は、直下の pytest と、`/api` の pytest の 2 件です。直下の pytest には、修正の PR（PR #9）が出ましたが、壊れていたので閉じました。`/api` の pytest には、警告が作られた時点から、修正の PR を作る実行が 1 回も起きていません。同じ時刻に、直下の pytest と、`/api` の Jinja2 には実行が起きました。エラーは出ていません。
同じ依存の minor の PR を閉じても、警告の画面の「Create Dependabot security update」を押しても、実行は起きませんでした。原因は分かっていません。
