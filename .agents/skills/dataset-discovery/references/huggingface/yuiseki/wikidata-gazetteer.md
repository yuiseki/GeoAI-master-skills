---
kind: dataset
id: yuiseki/wikidata-gazetteer
description: "Wikidata の位置つき地理項目と、552言語のラベル・別名を結んだ CC0 地名辞書。"
url: https://huggingface.co/datasets/yuiseki/wikidata-gazetteer
license: "CC0 1.0。Wikidata のデータベースを元にした再利用物"
formats:
- Parquet
crs: "lat/lon 列。CRS84 の経度・緯度"
spatial_coverage: "世界の Wikidata 地理項目"
temporal_coverage: "2026-08-31 Wikidata JSON ダンプ"
as_of:
  checked: 2026-10-26
  hf_revision: ef7674b5b00f2af07e792332b1d2d9f8ffccdff1
contents:
- 地理項目と多言語名
tables:
- name: places
  read: https://huggingface.co/datasets/yuiseki/wikidata-gazetteer/resolve/ef7674b5b00f2af07e792332b1d2d9f8ffccdff1/places.parquet
  grain: Wikidata の場所項目1件
  rows: 12205328
  id:
  - qid
---

# Wikidata Gazetteer

`places` 12,205,328行、`names` 62,506,107行。座標つきの場所は12,133,776件、552言語の名称を収録する。2026-08-31 の Wikidata ダンプから構築。`places.qid` と `names.qid` で結ぶ。`lat`、`lon` は座標列で geometry はない。人口・面積・階層は項目により欠ける。Hub SHA とダンプ日を固定して利用する。
