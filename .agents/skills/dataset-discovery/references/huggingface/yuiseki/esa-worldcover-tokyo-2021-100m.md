---
kind: dataset
id: yuiseki/esa-worldcover-tokyo-2021-100m
description: ESA WorldCover 2021 v200 の10 m土地被覆を東京周辺の100 mセルに集計した GeoParquet。
url: https://huggingface.co/datasets/yuiseki/esa-worldcover-tokyo-2021-100m
license: HF 表示は CC BY 4.0。元の ESA WorldCover の表示も確認して利用する
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 東京周辺の矩形、東経139.5〜140.0度・北緯35.5〜36.0度。東京都境界での切り出しではない
temporal_coverage: 2021年の土地被覆分類 v200。気温の観測時点ではない
as_of:
  checked: 2026-10-25
  hf_revision: 6f006f64483b65b20f06c775b87db7a8d57a6fda
contents:
- 100 mセルごとの土地被覆クラス別10 m画素数、優占クラス、形状
tables:
- name: worldcover_100m
  read: https://huggingface.co/datasets/yuiseki/esa-worldcover-tokyo-2021-100m/resolve/6f006f64483b65b20f06c775b87db7a8d57a6fda/data/parquet/esa_worldcover_tokyo_2021_v200_100m.parquet
  grain: 100 mセル。元の10 m画素を最大100個集計
  rows: 360000
  id:
  - tile_code
  - cell_row
  - cell_col
  columns:
  - name: pixels_10
    type: USMALLINT
    meaning: 樹木被覆に分類された10 m画素の数。面積率には valid_pixels で割る
  - name: valid_pixels
    type: USMALLINT
    meaning: 有効な10 m画素の数
  - name: dominant_class
    type: UTINYINT
    meaning: セル内の優占土地被覆クラス
---

# 東京周辺の WorldCover 100 m 集計

2026-10-25 に SHA 固定の Parquet メタデータを実読し、360,000 行と `tile_code`、`cell_row`、`cell_col`、`valid_pixels`、`nodata_pixels`、`pixels_10` など、EPSG:4326 の面を確認した。`data/parquet/profile.json` は元の10 m画素3,600万件・NoData 0 と報告するが、画素を全数照合したわけではない。樹林率を使うなら `pixels_10 / valid_pixels` と定義し、クラス20の低木を含めるかは別に決める。樹冠の日陰、気温、個人の暑熱曝露は直接測っていない。[元データのカード](../../esa-worldcover.md)も参照する。
