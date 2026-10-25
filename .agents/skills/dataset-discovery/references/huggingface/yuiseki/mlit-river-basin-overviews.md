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
