# 要件の達成の状況

[requirements.md](requirements.md) の要件ごとに、どこまで出来ているかを書きます。2026-11-15 時点のものです。
実現の方法は [README](../README.md) に、証拠は [app-request.md](app-request.md) にあります。

| 番号 | 状況 | 残っていること |
|---|---|---|
| 1 | 満たす | 人の判断待ちの minor の PR が開いた状態で、patch の PR が自動でマージされた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70)、[#79](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/79)、[#85](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/85)、[#87](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/87)）。Dependabot の push からマージまで 2〜3 分 |
| 2 | 一部 | 出す範囲は設定に入れた。Python は patch だけ、Node は同じ major の中だけ、Terraform は全部。uv はライブラリの線に戻した。uv を上げないまま、Python の patch で検査が通った（[PR #92](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/92)）。uv の PR が直下の設定から出て、patch が自動で入るところは、main に入れたあとに確かめる。Terraform は minor の PR が出ている（[PR #76](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/76)）。major は、新しい major がまだ無いので見られない |
| 3 | 満たす | なし |
| 4 | 満たす | なし |
| 5 | 満たす | なし |
| 6 | 満たす | 所有者の作り直しのあとも、App はロックファイルだけの PR を、所有者のレビューの免除でマージキューに入れた（[PR #70](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/70) は 06:01:39 に投入、06:02:31 にマージ。承認は App の 1 件だけ）。人が自分の鍵で署名して Dependabot を名乗るコミットは、実物では試していない |
| 7 | 一部 | 割り振りの設定は入れた。組織のメンバーが 1 人なので、偏らないことと、人数を変えたときの動きは、実物で確かめていない |
| 8 | 満たす | なし |
| 9 | 一部 | 判定と、Python と Node の見分けは入れた。uv は PyPI のパッケージなので、Dependabot のセキュリティ更新に任せる。ライブラリのセキュリティ更新が自動でマージされるところは、実物でまだ確かめていない |
| 10 | 満たす | なし |
| 11 | 満たす | Python と Node は、版を書いたファイル（`.python-version`、`.tool-versions`）を、手元の道具、CI、本番のイメージの組み立てが読む。手元の版が違うとテストが落ちる。uv は、CI と本番のイメージが `uv.lock` の同じ版を使う。手元の uv は下限（0.13）だけ。道具で実際に入れるところは試していない。Node のテストが落ちる側は確かめていない |
| 12 | 満たす | なし |
| 13 | 満たす | 依存ごとの PR にしたあとの検査の回数は、PR 1 本につき 1 回（README の「PR の本数と検査の回数」）。同じロックファイルの patch が 3 本以上重なった場合は、測れていない |
| 14 | 満たす | App の鍵の入れ替え、App の停止と削除は、試していない |
| 15 | 一部 | 無視するための設定は README に示した。GitHub の文書で確かめたもので、実物では試していない。通知の数は、設定からの上限で示した。実測は 2 本ぶん |
| 16 | 満たす | patch、minor、major の 5 件が、1 本の PR にまとまって出た（[PR #69](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/69)）。週 1 本になることは、確認の間隔（週 1 回）からの見込みで、複数の週では見ていない |
| 17 | 満たす | 種類でまとめるグループをやめた。版が連動する群（vitest と @vitest/coverage-v8）だけをまとめ、2 件が 1 本で出た（[PR #77](https://github.com/kazufuuu/dependabot-merge-queue-lab/pull/77)） |

## 満たしていない要件を妨げているもの

### 9: セキュリティ更新の自動マージの確認

古いセキュリティ更新の PR は、壊れていたので閉じました。Dependabot は「閉じれば作り直す」と返しましたが、まだ出し直していません。
判定は単体テストで確かめています。実物のセキュリティ更新が自動でマージされるところは、見ていません。

開いている警告は、`/api` の pytest の 1 件です。この警告には、作られた時点から、修正の PR を作る実行が 1 回も起きていません。同じ時刻に、直下の pytest と、`/api` の Jinja2 には実行が起きました。エラーは出ていません。
同じ依存の minor の PR を閉じても、警告の画面の「Create Dependabot security update」を押しても、実行は起きませんでした。原因は分かっていません。
