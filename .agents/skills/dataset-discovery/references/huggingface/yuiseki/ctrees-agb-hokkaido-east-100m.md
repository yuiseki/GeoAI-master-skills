---
kind: dataset
id: yuiseki/ctrees-agb-hokkaido-east-100m
description: CTrees の2010年・2025年の地上部バイオマス密度と不確実性を東北海道で切り出し、約1kmの角度格子へ集計した派生版。
url: https://huggingface.co/datasets/yuiseki/ctrees-agb-hokkaido-east-100m
license: CC BY 4.0。CTrees と元資料の著者を表示し、地域集計の派生物であることを示す
formats:
- GeoParquet 1.1
crs: EPSG:4326
spatial_coverage: 切り出し窓は東経143〜147度・北緯42〜46度。値のある出力面は北緯約44.67度まで
temporal_coverage: 2010年と2025年の年次モデル推定値。現地調査の同日観測ではない
as_of:
  checked: 2026-10-25
  hf_revision: e0edd7cd9812847d1740cf1b35ac84885cde3bef
contents:
- 10×10の元画素をまとめたAGB密度の平均・標準偏差と元画素の不確実性の平均
tables:
- name: agb_blocks
  read: https://huggingface.co/datasets/yuiseki/ctrees-agb-hokkaido-east-100m/resolve/e0edd7cd9812847d1740cf1b35ac84885cde3bef/data/parquet/ctrees_agb_hokkaido_east_2010_2025_1km.parquet
  grain: 元の100m角度格子を10×10画素ずつまとめた面。正確な1km正方形ではない
  rows: 43550
  id:
  - cell_row
  - cell_col
  columns:
  - name: agb_mean_2010_mg_ha
    type: DOUBLE
    meaning: 有効な元画素における2010年のモデル推定AGB密度の平均、Mg/ha
  - name: agb_mean_2025_mg_ha
    type: DOUBLE
    meaning: 有効な元画素における2025年のモデル推定AGB密度の平均、Mg/ha
  - name: uncertainty_mean_2025_mg_ha
    type: DOUBLE
    meaning: 元画素の推定残差の不確実性の平均。集計面の標準偏差ではない
  - name: valid_pixels_2025
    type: USMALLINT
    meaning: 2025年に有効だった元画素数
---

# 東北海道の CTrees AGB 集計版

2026-10-25 に上記 SHA の Parquet を `profile_layer.py` と DuckDB で実読した。43,550行、11列、面は全行で `POLYGON`、EPSG:4326、無効形状0件。`cell_row` と `cell_col` の組は43,550件すべて一意で、両年の `valid_pixels` が0の行は無かった。実データの面の範囲は東経約143〜147度・北緯42〜44.67度で、元の4度四方の切り出し窓全体を覆わない。GeoParquet は2,080,808バイト。

元データは [CTrees の公開 COG](https://registry.opendata.aws/ctrees-agb-100m-global/)で、AWS 登録は [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) を表示する。HF には地域の元 GeoTIFF 4枚と変換コード、ハッシュの記録もある。これはモデル推定値を10×10画素で集計した派生物であり、現地で測った森林蓄積量ではない。年差を実測変化と断定せず、推定の不確実性と時期の異なるモデル入力を考慮する。元の全球データは[CTrees のカード](../../ctrees-agb-100m.md)を参照する。
