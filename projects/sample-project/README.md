# sample-project

1 つの分析の作業場所の例。分析を始めるときは、`projects/` の中を見て、既にある名前と重ならない名前のディレクトリを作り、その中でだけ作業する。このディレクトリは例なので、ここに書き込まない。

名前は、問いを表す短い英小文字とハイフン (例 `tokyo23-accident-rate`)。同じ問いをやり直すなら、日付を付けて分ける (例 `tokyo23-accident-rate-2026-10-23`)。

```
projects/<名前>/
  README.md               問いと使い道、どこに何があるか、再現の手順 (コマンドとライブラリの版)
  report.md               報告 (最終回答)。Markdown で書く。HTML やノートブックにしない
  EXPERIMENT_PLAN.md      計画を作る分析なら (流す前に固定したもの)
  EXPERIMENT_TRACKER.md   実行の記録
  scripts/                自分で書いたコード
  outputs/                報告が引く小さな表と図 (CSV、JSON、PNG)。図は PNG にして report.md に貼る

artifacts/<名前>/          大きな生成物 (取り出したデータ、中間の Parquet、ラスタ、模擬の結果)
```

- 報告の数字は `outputs/` か `artifacts/<名前>/` のファイルから写し、そのパスを報告に書く。
- 大きなファイルは `artifacts/<名前>/` に置き、`projects/<名前>/` には置かない。読む人が報告とコードだけを見られるようにするため。
- `projects/` と `artifacts/` の中身は git に入れない (この例だけが入っている)。
