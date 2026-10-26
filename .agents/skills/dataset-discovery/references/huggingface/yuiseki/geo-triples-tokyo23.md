---
kind: dataset
id: "yuiseki/geo-triples-tokyo23"
description: "東京23区・地理関係 triple、英日テキスト、評価質問からなる GeoAI ベンチマーク。"
url: https://huggingface.co/datasets/yuiseki/geo-triples-tokyo23
license: "ODbL 1.0。OpenStreetMap contributors を表示し、派生データベースにも Share-Alike を適用"
formats:
- Parquet
crs: null
spatial_coverage: "東京都特別区。geometry ではなく区・POI 間の空間関係を記述"
temporal_coverage: "OSM 2026-08 スナップショット、Natural Earth 5.1.1"
as_of:
  checked: 2026-10-26
  hf_revision: 2de36a77561f57af861d483a0c013fac0ddb1307
contents:
- "固定版データ。ライセンスと解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/geo-triples-tokyo23/resolve/2de36a77561f57af861d483a0c013fac0ddb1307/data/triples.parquet
  grain: "空間関係 triple 1件"
  rows: 510616
  id: []
---

# geo-triples-tokyo23

同梱 manifest によれば triple 510,616行、CPT 483,922行、probe 8,854行。README 冒頭の一部件数は別データセットからの転記と manifest と食い違うため、ここでは manifest を根拠にした。OSM 東京23区スナップショットと Natural Earth 5.1.1 から計算した空間関係評価データ。geometry の現地観測ではなく、RCC8/DE-9IM の関係を扱う。ライセンスは入力データの最も厳しい条件を引き継ぐ。
