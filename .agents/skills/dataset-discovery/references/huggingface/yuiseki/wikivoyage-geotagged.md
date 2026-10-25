---
kind: dataset
id: yuiseki/wikivoyage-geotagged
description: "座標タグのある Wikivoyage 旅行記事の本文と位置情報。"
url: https://huggingface.co/datasets/yuiseki/wikivoyage-geotagged
license: "CC BY-SA 4.0。Wikivoyage本文の帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "lat/lon 列。地球上の座標"
spatial_coverage: "世界の英語 Wikivoyage 記事"
temporal_coverage: "2026-09-01 のダンプ"
as_of:
  checked: 2026-10-26
  hf_revision: 5b467dab88378d725318d1f0db060a9ee620b23f
contents:
- 旅行記事本文、座標、Wikidata ID
tables:
- name: articles
  read: https://huggingface.co/datasets/yuiseki/wikivoyage-geotagged/resolve/5b467dab88378d725318d1f0db060a9ee620b23f/20260901.en/train-00000-of-00001.parquet
  grain: 座標つき Wikivoyage 記事1件
  rows: 29505
  id:
  - id
---

# Geotagged Wikivoyage

2026-09-01 の英語ダンプから座標つき記事29,505件。1ファイルで29,505行。`id`、`url`、`title`、`text` に `qid`、`lat`、`lon`、`gt_dim`、`tags` を持つ。旅程、地域、テーマに付いた座標もあり、全てを目的地の位置とみなさない。本文の再配布・改変には CC BY-SA 4.0 の帰属・ShareAlike 条件が適用される。
