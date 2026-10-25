---
kind: dataset
id: yuiseki/gebco-2026-hokkaido-east-15as
description: GEBCO 2026 の東北海道沖3度四方を切り出し、15秒角セルの標高を面に変換した派生版。
url: https://huggingface.co/datasets/yuiseki/gebco-2026-hokkaido-east-15as
license: HF 表示は other。GEBCO は public domain だが出典表示が必要で、CEDA の OGL v3.0 表示も確認する
formats:
- GeoParquet 1.1
crs: EPSG:4326
spatial_coverage: 東経143〜146度・北緯42〜45度。陸域と海域を含む
temporal_coverage: GEBCO 2026 年版。元の測量時期は画素ごとに異なる
as_of:
  checked: 2026-10-25
  hf_revision: 5da32601a62457c36b001d8ab5524d905acb1cd7
contents:
- GEBCO Grid の標高値。元データの由来を示す TID は含まない
tables:
- name: elevation
  read: https://huggingface.co/datasets/yuiseki/gebco-2026-hokkaido-east-15as/resolve/5da32601a62457c36b001d8ab5524d905acb1cd7/data/elevation.parquet
  grain: 15秒角の元ラスタ1画素を面に変えた行
  rows: 518400
  id: []
  no_key:
  - name: source_cell_id
    note: 行列番号の列は無い。空間で結ぶ前に面の重複を検査する
  columns:
  - name: elevation_m
    type: SMALLINT
    meaning: 平均海面を基準とする標高のメートル値。負値は海底側
---

# GEBCO 2026 東北海道沖の標高セル

2026-10-25 に上記 SHA の Parquet を実読した。518,400行、`geometry` と `elevation_m` の2列、全行が EPSG:4326 の有効な `POLYGON`。範囲は東経143〜146度・北緯42〜45度、標高は −5,722〜1,869 m、負値は332,908行。GeoParquet は3,909,596バイト。行の一意キーは無く、画素の重複・重なりは未検査。

元データは [GEBCO 2026 Grid](https://www.gebco.net/data-products/gridded-bathymetry-data/gebco2026-grid)。[GEBCO の利用条件](https://www.gebco.net/data-products/gridded-bathymetry/terms-of-use)は Grid の再配布と改変を認め、出典表示、非公認であることの明示、航行・海上安全への不使用を求める。HF のカードは、取得元 CEDA の Open Government Licence v3.0 表示も併記している。15秒角は格子間隔であり、元測量の精度ではない。この切り出しには由来を表す TID が無いので、観測・推定の区別が必要なら元の Grid と TID を使う。[GEBCO 2025 のカード](../../gebco-2025.md)とは版が異なる。
