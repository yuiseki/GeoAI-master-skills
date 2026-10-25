---
kind: dataset
id: yuiseki/kontur-population-2023-11-01-22km
description: Kontur Population の2023-11-01版の H3 resolution 4 を GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/kontur-population-2023-11-01-22km
license: HF 表示は other、名称は CC BY。版数と元ファイルの再配布条件は別途確認する
formats:
- GeoParquet
crs: EPSG:3857
spatial_coverage: 全球の H3 セル。22 km は公称の分解能
temporal_coverage: 2023-11-01版の人口推計。その日の現地観測人数ではない
as_of:
  checked: 2026-10-25
  hf_revision: 2e7291f8c2d4b9c06bb4ff0e43be14e538e0600d
contents:
- H3 r4 セルの人口推計と面
tables:
- name: population_r4
  read: https://huggingface.co/datasets/yuiseki/kontur-population-2023-11-01-22km/resolve/2e7291f8c2d4b9c06bb4ff0e43be14e538e0600d/parquet/kontur_population_20231101_r4.parquet
  grain: H3 resolution 4 のセル
  rows: 71283
  id:
  - h3
  columns:
  - name: h3
    type: VARCHAR
    meaning: H3 セルの ID
  - name: population
    type: DOUBLE
    meaning: 推計人口。年齢や昼夜の内訳は無い
---

# Kontur 人口の凍結 GeoParquet

2026-10-25 に固定版の Parquet メタデータを実読し、71,283行、`h3`・`population` と EPSG:3857 の面を確認した。元の [HDX 版](../../kontur-population-20231101.md)で実測された22 km版と行数は一致するが、行ごとの値の一致やキーの一意性はこの変換版では未検証。HF のライセンス表示は `other` と `license_name: cc-by` で、CC BY 4.0 と断定しない。大きな H3 セルの人口を地域内の任意の点の人数と解釈しない。
