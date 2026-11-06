---
kind: dataset
id: "yuiseki/mlit-river-basin-overviews"
description: "国土交通省の一級水系・河川流域概要の公開本文。"
url: https://huggingface.co/datasets/yuiseki/mlit-river-basin-overviews
license: "政府標準利用規約（第1.0版）。引用される第三者資料の権利は別途尊重"
formats:
- "JSON Lines"
crs: null
spatial_coverage: "日本の一級水系流域"
temporal_coverage: "収録資料の発行・更新時点による"
as_of:
  checked: 2026-10-26
  hf_revision: bdd94d99263564ea837aaec33116b7d8d6b28f25
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/mlit-river-basin-overviews/resolve/bdd94d99263564ea837aaec33116b7d8d6b28f25/river_basin.jsonl
  grain: "文書ページ1件"
  rows: null
  id: []
---

# mlit-river-basin-overviews

115文書、9,894ページ。140候補からスキャンのみの22資料と、権利制限または共同著作の3資料を除外。流域名・河川名を含む本文の検索向けで、GIS境界データではない。

## 流域の照合に使える値 (2026-11-06)

一級水系の概要は、流域面積だけでなく、ダムごとの集水面積を表に載せていることがある。DEM から切った流域の面積を照合する相手になる。相模川の概要 (`title` が相模川水系) では、p.4 に流域面積 約 1,680 km²、p.70〜71 に相模ダム 1,016 km²、城山ダム 1,221.3 km²、道志ダム 112.5 km²、沼本ダム 1,039.4 km²、宮ヶ瀬ダム 213.9 km² (うち 112.5 km² と注記) があった。本文は PDF から抜いた文字なので、表の行と列が崩れている。値はページの前後の文脈と合わせて読む。

湖や放水路のつながりも本文にある。相模川の概要の p.64 は、河口湖と桂川の支川の宮川を結ぶ嘯放水路 (1994 年完成、計画流量 30 m³/s) を載せている。外へ川の流れ出ない盆地が流域に数えられているかは、こうした記述から判断する。西湖、精進湖、本栖湖が流域面積に含まれるかは、この概要からは分からなかった。

二級水系は収録されていない (酒匂川は本文で触れられるだけで、概要は無い)。
