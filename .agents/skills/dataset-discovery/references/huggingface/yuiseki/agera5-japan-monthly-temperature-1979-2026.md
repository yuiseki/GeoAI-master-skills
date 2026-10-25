---
kind: dataset
id: "yuiseki/agera5-japan-monthly-temperature-1979-2026"
description: "AgERA5 日本周辺の月平均最高・最低気温の格子。"
url: https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026
license: "CC BY 4.0。Copernicus Climate Change Service / ECMWF と FAO GIS catalogue を出典表示"
formats:
- GeoParquet
crs: "EPSG:4326"
spatial_coverage: "東経122〜154度、北緯20〜46度。日本周辺の陸海。EPSG:4326"
temporal_coverage: "1979-01〜2026-07、月次、0.1度格子"
as_of:
  checked: 2026-10-26
  hf_revision: 348e4599bffe05bc48a7033021b7e212b0f00aad
contents:
- "固定版データ。詳細な派生・利用条件は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026/resolve/348e4599bffe05bc48a7033021b7e212b0f00aad/data/year=2026/part-0.parquet
  grain: "格子セル・月1件"
  rows: null
  id: []
---

# agera5-japan-monthly-temperature-1979-2026

月別の格子点気候データ。範囲矩形には海域と周辺国も含む。`tmax_mean_k` と `tmin_mean_k` は Kelvin、NoData は NULL。CC BY 4.0 に基づき C3S/ECMWF と FAO GIS catalogue の表示を残す。
