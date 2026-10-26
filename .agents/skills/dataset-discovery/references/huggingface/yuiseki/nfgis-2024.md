---
kind: dataset
id: yuiseki/nfgis-2024
description: "林野庁の2024年度版国有林GIS。小班、林班、林道などを座標系別に収録。"
url: https://huggingface.co/datasets/yuiseki/nfgis-2024
license: "林野庁の公共データ利用規約1.0相当/CC BY 4.0。出典表示と加工明記"
formats:
- GeoParquet
crs: "森林管理地域ごとに平面直角座標系 EPSG:2443〜2461。混在する"
spatial_coverage: "日本の国有林"
temporal_coverage: "2024年度版"
as_of:
  checked: 2026-10-26
  hf_revision: f756afa15c645fd223c695d95f315d7eb684cd96
contents:
- 林小班、林班、林道等の国有林GISレイヤー
tables:
- name: shouhan_zone01
  read: https://huggingface.co/datasets/yuiseki/nfgis-2024/resolve/f756afa15c645fd223c695d95f315d7eb684cd96/parquet/2024/shouhan_zone01.parquet
  grain: 国有林の林小班ポリゴン1件
  rows: null
  id:
  - null
---

# 国有林 GIS 2024

林小班975,666、林班58,293、林道57,912件。例は[林小班 zone01](https://huggingface.co/datasets/yuiseki/nfgis-2024/resolve/f756afa15c645fd223c695d95f315d7eb684cd96/parquet/2024/shouhan_zone01.parquet)。地域別ファイルは平面直角座標系19系 (EPSG:2443〜2461) に分かれ、全国単一 CRS ではない。`index.parquet` で地域とファイルを対応づける。変換時に無効 geometry が4,618件確認されているため、演算前に妥当性を点検し修復件数を記録する。林野庁の利用規約に従い出典と加工を明記する。
