# 自然言語の依頼からの分析 (オープンデータ版 Playground)、2026-11-12

問い: 利用者が自然言語で目的だけを書いたとき、エージェントがスキルを選び、データを探し、分析して、確かめられる報告を出せるか。Google の Playground の 3 つの領域 (POI、道路の交通、地上視点の画像) で確かめる。

## 1. 振り分け (発火テスト)

`evals/trigger_playground.yaml` の 9 ケース (Google の記事の 3 つの例の文をそのまま含む)。ケースは、道路と画像のスキルの SKILL.md を書き終える前、どの実行よりも前に書いて commit した (8b720fd)。スキルの版は a176925。各 1 回。

| エージェント | 合格 | 記録 |
|---|---|---|
| Claude Code 2.1.321、Sonnet 5.5、既定の effort | 9/9 | ~/Workspaces/tmp/trigger-playground-claude |
| Codex、gpt-6-luna、medium | 9/9 | ~/Workspaces/tmp/trigger-playground-codex |
| Gemini CLI (agy 1.3.5)、gemini-3.8-flash-low | 9/9 | ~/Workspaces/tmp/trigger-playground-gemini |

合格は、期待したスキル (と、ケースによってはその reference) を開いたこと。英語の例 3 つ (p1、p4、p7) も、日本語の言い換え 6 つも、全てのエージェントで正しいスキルに届いた。1 回ずつなので、外れの率が 0 か 1 割かは区別できない。

## 2. 最後までの分析 (End-to-End)

Docker の Claude Code (Sonnet 5.5、既定の effort、CPU 8、メモリ 16 GB) に、`evals/prompts/agent-task.md` の形で、問いだけを渡した。作業場所は prepare_workdir.py で作り、こちらで行った分析 (projects/_playground) は消した。こちらで流したのとは別の都市か期間を問うた。成果物はこのディレクトリに写した。

| 領域 | 依頼 (要約) | 結果 | 時間 | 写し |
|---|---|---|---|---|
| POI | 東京 23 区のコンビニの集積上位 10 を H3 で、区ごとの人口あたりと寡占も | 完了。check_project.py は ok。poi-insights の 3 つのスクリプトを使った。Overture の営業状態が全て欠けていること、ATM の行 313 と同じチェーンの 25 m 以内の重複を見つけ、除く前と後を並べた | 11 分 | [poi-tokyo](playground-e2e-2026-11-12/poi-tokyo/report.md) |
| 道路 | ニューヨーク市の 2026 年 9 月の朝夕のラッシュの遅れと読めなさ、差の不確かさ | 完了。check_project.py は ok。travel-time-reliability の ttr_metrics.py を使った。80 区間のうち夕が遅い 47、朝が遅い 16。LOTTR が 1.5 以上の区間の数が窓の取り方で 34 から 27 に変わることを示した。Gowanus 北行きの一日中の遅さを測定の異常の疑いとして挙げた | 49 分 | [roads-nyc](playground-e2e-2026-11-12/roads-nyc/report.md) |
| 画像 | パリ 11 区のオープンな画像で、柱の傾き、柱にかかる枝、路面の傷み、信頼できる度合いも | 未完了。120 分の制限で打ち切られ、報告と地図は出なかった。street-imagery-inspection の SKILL.md と 4 つの reference を全て読み、スクリプトを使った。範囲の 37,197 枚から 1 つの機材 (imajbox 360 HD) の 3,045 枚に絞り、一様な 200 枚。途中の表は残った (下) | 120 分 (打ち切り) | [imagery-paris](playground-e2e-2026-11-12/imagery-paris/PROMPT.md) |

- 2 つの実行は、どちらもスキルの SKILL.md を読んだが、後の段の reference (poi-insights の grids-and-hotspots など) は開かなかった。それでも、スクリプトの説明と dataset-discovery から手順を組み立てた。
- 東京の実行で見つかった重複と ATM の行は、poi-insights の references/attributes-and-gaps.md に書き足した (a176925)。

## 3. 画像の実行が途中で残したもの

報告が無いので、出力のファイルから読んだ値。ラベルは全てエージェント自身が画像を見て付けたもの (AI の目視) で、人は見ていない。

- 柱の検出: OWLv2 の枠 922。エージェントは、柱かどうかを OpenCLIP で確かめる段を自分で足し、開発の 60 枠でしきい値を決め、別の 40 枠で試した (適合率 0.59、再現率 0.85)。
- 柱の傾き: 同じ柱を 2 枚以上で測れた 22 か所で、測り直しの標準偏差の中央値 0.82 度、幅の最大 3.98 度。5 度を超えた枠は 8。ハフ変換と別の勾配の方法の相関 0.77。メリニャックで書いた「同じ柱を複数の画像で測って一致を見る」を実行した。
- 植生: 53 枠のラベルで AUC 0.94。メリニャックとは違い、パリの画像では緑の画素の割合が葉を拾った。
- 路面の損傷: RDD2022 のプローブ (米国で AUC 0.967 を再現) をパッチに当て、確率の帯ごとにラベルで適合率を測った。0.5 以上で 0.23、0.6 以上で 0.43。0.5 未満の 24 パッチにひびは無かった。
- 時間: 柱の検出 (800 の画像、CPU) に約 35 分かかり、ラベル付けのやり直しが続いて、表を書いたところで時間が尽きた。依頼の「1 時間ほど」に対して、標本 200 枚は多すぎた。

画像の写しは、撮影者ごとのライセンス (CC-BY-SA を含む) の表示を付けていないので、ここには入れなかった (CSV とスクリプトだけ)。
