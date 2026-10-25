---
kind: dataset
id: "yuiseki/worldpop-idn-population-2015-2030-1km-r2025a"
description: "WorldPop R2025A のインドネシア年次人口推計 1 km 格子。"
url: https://huggingface.co/datasets/yuiseki/worldpop-idn-population-2015-2030-1km-r2025a
license: "ODbL 1.0 の派生データ。WorldPop 元データの条件も併記し、派生データベースの Share-Alike と帰属表示を守る"
formats:
- GeoParquet
crs: "EPSG:4326"
spatial_coverage: "インドネシア。EPSG:4326"
temporal_coverage: "2015〜2030年。2030年までの値は推計"
as_of:
  checked: 2026-10-26
  hf_revision: b70415daf2035015bbc72ff5b89baf47ba4d08d
contents:
- "固定版データ。詳細な派生・利用条件は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/worldpop-idn-population-2015-2030-1km-r2025a/resolve/main/data/population.parquet
  grain: "人口セル1件・年ごと"
  rows: null
  id: []
---

# worldpop-idn-population-2015-2030-1km-r2025a

WorldPop R2025A の国別派生版。Hub の `other` 表示だけでなく、収録 LICENSE と manifest の元データ条件を確認した。WorldPop の帰属表示に加え、ODbL のデータベース権・派生データベース共有条件を適用する。
