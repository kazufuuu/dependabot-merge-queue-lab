# 要件の達成の状況

[requirements.md](requirements.md) の要件ごとに、どこまで出来ているかを書きます。2026-11-15 時点のものです。
実現の方法は [README](../README.md) に、証拠は [app-request.md](app-request.md) にあります。

| 番号 | 状況 | 残っていること |
|---|---|---|
| 1 | 満たす | 人の判断待ちの minor の PR が開いた状態で、patch の PR が自動でマージされた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70)、[#79](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/79)、[#85](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/85)、[#87](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/87)）。Dependabot の push からマージまで 2〜3 分。`==` で固定していた ruff は、範囲に直すと、同じ patch の PR がロックファイルだけの変更になり、自動でマージされた（[PR #86](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/86)） |
| 2 | 満たす | 出す範囲は設定に入れた。Python は patch だけ、Node は同じ major の中だけ、Terraform は全部。uv はライブラリの線に戻し、直下の設定から出た patch の PR が自動でマージされた（[PR #93](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/93)、PR が出てから 2 分 24 秒）。uv を上げないまま、Python の patch で CI が通った（[PR #92](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/92)）。Terraform は minor の PR が出ている（[PR #76](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/76)）。Terraform の major は、新しい major がまだ無いので、実物では見ていない。止める設定が無いことだけを確かめた。Python の PR（[PR #78](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/78)）は、Dependabot 用の Dockerfile の書き方を変えたあと、作り直されなかった。原因は分かっていない。`@dependabot recreate` には 1 時間たっても反応が無く、設定を変えて起こした確認でも「すでにある」と扱われた。main と衝突したまま開いている。中身（Python 3.13.18）は、PR #92 で CI が通ることを確かめてある。ふだんの運用で同じことが起きたら、人が衝突を直して入れるか、閉じて次のバージョンを待つ。見立てでは、今回の衝突は、Dependabot 用の Dockerfile のファイルの書き方をこちらが変えたために起きたもので、ふだんの運用では起きにくい。この見立ては確かめていない。Dependabot 用の Dockerfile から外した uv の PR（[PR #74](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/74)）は、Dependabot が閉じなかったので、人が閉じた |
| 3 | 満たす | なし |
| 4 | 満たす | なし |
| 5 | 満たす | なし |
| 6 | 満たす | 所有者の作り直しのあとも、App はロックファイルだけの PR を、所有者のレビューの免除でマージキューに入れた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70) は 06:01:39 に投入、06:02:31 にマージ。承認は App の 1 件だけ）。人が自分の鍵で署名して Dependabot を名乗るコミットは、実物では試していない |
| 7 | 一部 | 割り振りの設定は入れた。組織のメンバーが 1 人なので、偏らないことと、人数を変えたときの動きは、実物で確かめていない |
| 8 | 満たす | 開発用の依存（pytest、ruff、just など）は、直下の `pyproject.toml` に範囲で書いてあり、ライブラリと同じ設定が追う |
| 9 | 一部 | 判定と、Python と Node の見分けは入れた。uv は PyPI のパッケージなので、Dependabot のセキュリティアップデートに任せる。ライブラリのセキュリティアップデートが自動でマージされるところは、実物でまだ確かめていない |
| 10 | 満たす | なし |
| 11 | 満たす | Python と Node は、バージョンを書いたファイル（`.python-version`、`.node-version`）を、手元の道具、CI、本番のイメージのビルドが読む。手元のバージョンが違うとテストが落ちる。uv は、CI と本番のイメージが `uv.lock` の同じバージョンを使う。手元の uv は下限（0.13）だけ。道具で実際に入れるところは試していない。Node のテストが落ちる側は確かめていない |
| 12 | 満たす | なし |
| 13 | 満たす | 依存ごとの PR にしたあとの CI の回数は、PR 1 本につき 1 回（README の「PR の本数と CI の回数」）。同じロックファイルの patch が 3 本以上重なった場合は、測れていない。CI の job は、手元と同じ `justfile` のレシピを呼ぶ。job とレシピの名前は同じ。どの job も、`uv run just` で呼ぶ |
| 14 | 満たす | App の鍵の入れ替え、App の停止と削除は、試していない |
| 15 | 一部 | 無視するための設定は README に示した。GitHub の文書で確かめたもので、実物では試していない。通知の数は、設定からの上限で示した。実測は 2 本ぶん |
| 16 | 満たす | patch、minor、major の 5 件が、1 本の PR にまとまって出た（[PR #69](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/69)）。週 1 本になることは、確認の間隔（週 1 回）からの見込みで、複数の週では見ていない |
| 17 | 満たす | 種類でまとめるグループをやめた。バージョンが連動する群（vitest と @vitest/coverage-v8）だけをまとめ、2 件が 1 本で出た（[PR #77](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/77)）。ランタイムのセキュリティアップデートの PR は、Python と Node で分けた。分けた形で PR が出るところは、単体テストだけの裏付け。次のセキュリティのバージョンで確かめる |

## 満たしていない要件を妨げているもの

### 9: セキュリティアップデートの自動マージの確認

古いセキュリティアップデートの PR は、壊れていたので閉じました。Dependabot は「閉じれば作り直す」と返しましたが、まだ出し直していません。
判定は単体テストで確かめています。実物のセキュリティアップデートが自動でマージされるところは、見ていません。
実物では、警告が作られた直後に Dependabot が修正の PR を出した例（PR #9、#10 など）と、出なかった例があります。

開いている警告は、`/api` の pytest の 1 件です。この警告には、作られた時点から、修正の PR を作る実行が 1 回も起きていません。同じ時刻に、直下の pytest と、`/api` の Jinja2 には実行が起きました。エラーは出ていません。
同じ依存の minor の PR を閉じても、警告の画面の「Create Dependabot security update」を押しても、実行は起きませんでした。原因は分かっていません。
