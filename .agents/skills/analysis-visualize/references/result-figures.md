# 最適化の前線と時刻割当を描く

`scripts/result_figures.py` は、分析済みの解や割当を JSON で受け取り、PNG と同名の来歴 JSON を保存する。最適化や割当そのものは行わない。

```sh
uvx --with matplotlib python scripts/result_figures.py input.json output.png
uvx --with matplotlib --with pytest pytest scripts/test_result_figures.py
```

## パレート前線

入力例。`front: false` は重み付き法が返した弱い解など、前線に属さない点だけに使う。省略時は true。`methods` はその点を返した手法の名前。前線の点が支配されている、座標が重複する、値が有限でない場合は止める。

```json
{
  "kind": "pareto", "question": "浸水を抑えると被覆人口はどう変わるか",
  "source": "analysis output", "data_version": "2026-09-29",
  "x_label": "浸水ランクの和", "y_label": "400 m 以内の人口 (人)",
  "x_direction": "min", "y_direction": "max",
  "points": [
    {"x": 0, "y": 1000, "methods": ["ε 制約法", "重み付き和"]},
    {"x": 1, "y": 1200, "methods": ["ε 制約法"]}
  ]
}
```

横軸と縦軸は別の目的関数であり、曲線の傾きを因果効果と読まない。階段線は観測された離散解を結ぶ目印で、途中に実行可能な解があるという意味ではない。全解と手法別の点数を残し、都合のよい数点だけを抜かない。人口割合が必要なら分析結果に含まれる分母を来歴とともに明記する。

## 時刻割当

時刻はサービス日の午前0時からの秒。翌日へまたぐ運行は 86400 を超える秒で表す。1 行は 1 つの割当済み区間。区間同士が同じ `group` で重なる場合は止める。空き時間をバーとして描かない。

```json
{
  "kind": "schedule", "question": "各車両はいつ運行するか",
  "source": "analysis output", "data_version": "2026-09-29",
  "x_label": "時刻", "y_label": "車両", "time_unit": "seconds",
  "intervals": [
    {"group": "車両1", "start": 28800, "end": 32400, "kind": "運行"},
    {"group": "車両1", "start": 36000, "end": 39600, "kind": "運行"}
  ]
}
```

車両の割当と乗務員の割当は異なる制約の結果である。凡例に区間の意味を記し、図の外にある回送・準備・休憩を実際にモデル化したかを本文に書く。

出力 JSON は問い、入力ファイル、データ版、図中の件数、パレート前線の点数と手法別点数、または割当区間数と群数、描画に使ったフォントを記録する。画像を開いて文字や凡例を目視確認する。
