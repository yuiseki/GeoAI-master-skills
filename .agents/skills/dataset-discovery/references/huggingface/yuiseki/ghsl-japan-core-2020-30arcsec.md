---
kind: dataset
id: yuiseki/ghsl-japan-core-2020-30arcsec
description: GHSL R2023A の2020年人口推計と建物面積を日本周辺の30秒角タイルから GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec
license: HF と元の JRC 資料は CC BY 4.0 を表示。元資料と変換版の両方を表示する
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 日本周辺を含む東アジアの5タイル、概ね東経120〜150度・北緯29〜49度。日本だけではない
temporal_coverage: R2023A の E2020 推計。全入力の一斉観測日ではない
as_of:
  checked: 2026-10-25
  hf_revision: 4ee767429ee03ea47a9003c547f92c320474e350
contents:
- GHS-POP の居住人口推計
- GHS-BUILT-S の建物面積推計
tables:
- name: population_R5_C32
  read: https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec/resolve/4ee767429ee03ea47a9003c547f92c320474e350/data/parquet/population/R5_C32.parquet
  grain: 30秒角の人口ラスター1セル。他に同じ形式の4タイルがある
  rows: 1440000
  id:
  - tile_code
  - cell_row
  - cell_col
  columns:
  - name: population_estimate
    type: DOUBLE
    meaning: セルの推計居住人口。国勢調査のセル実測ではない
- name: built_surface_R5_C32
  read: https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec/resolve/4ee767429ee03ea47a9003c547f92c320474e350/data/parquet/built_surface/R5_C32.parquet
  grain: 30秒角の建物面積ラスター1セル。他に同じ形式の4タイルがある
  rows: 1440000
  id:
  - tile_code
  - cell_row
  - cell_col
  columns:
  - name: built_surface_m2
    type: UINTEGER
    meaning: 推計建物面積、平方メートル
---

# GHSL 2020 東アジアの変換版

2026-10-25 に人口と建物面積の `R5_C32` をそれぞれ実読し、各1,440,000行と列型、EPSG:4326 の面を確認した。Hub の README は各製品5タイル計7,200,000セルと説明するが、残り4タイルの件数はここでは未実測。両製品は格子原点が異なるため、同名の `tile_code`・`cell_row`・`cell_col` だけで直接結ばず、面の重なりを確認する。0セルを除外した人口密度の母数にも注意。元製品の定義は親索引から GHSL の目録と人口・建物面積のカードを参照する。
