---
kind: dataset
id: yuiseki/gsi-global-map-jp
description: "国土地理院の地球地図日本の複数版ベクターとラスタを保存したデータ。"
url: https://huggingface.co/datasets/yuiseki/gsi-global-map-jp
license: "国土地理院コンテンツ利用規約/公共データ利用規約1.0。出典表示と加工明記。HF metadata はCC BY 4.0を表示"
formats:
- GeoParquet
crs: "版・レイヤーごとに異なる。主に ITRF94 EPSG:8994、一部 JGD2000 EPSG:4612"
spatial_coverage: "日本全国"
temporal_coverage: "ベクター版2.0、2.1、2.2。地物時点は一様でない"
as_of:
  checked: 2026-10-26
  hf_revision: f2c1e4333554ba5b34e437dffd1e176b8be85a25
contents:
- 行政界、道路、鉄道、河川、海岸線等
tables:
- name: vector_2_2_polbnda
  read: https://huggingface.co/datasets/yuiseki/gsi-global-map-jp/resolve/f2c1e4333554ba5b34e437dffd1e176b8be85a25/parquet/vector-2.2/polbnda.parquet
  grain: 地球地図行政界フィーチャ1件
  rows: null
  id:
  - null
---

# 地球地図日本

地球地図日本のベクター版2.0、2.1、2.2を各15レイヤーの GeoParquet で収録し、4つのラスタも含む。道路、行政界、鉄道、河川、海岸線など。例は[2.2版行政界面 polbnda](https://huggingface.co/datasets/yuiseki/gsi-global-map-jp/resolve/f2c1e4333554ba5b34e437dffd1e176b8be85a25/parquet/vector-2.2/polbnda.parquet)。版・レイヤーの CRS が異なるため個別に確認し、同じ CRS と仮定しない。配布元の国土地理院コンテンツ利用規約 (公共データ利用規約1.0) に従い出典と加工を明示。HF metadata の CC BY 4.0 表示も併記して確認する。
