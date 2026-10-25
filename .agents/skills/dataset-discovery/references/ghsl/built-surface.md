---
kind: dataset
id: ghsl/built-surface
description: GHSL R2023A の建物が占める地表面積の推計。画素ごとに平方メートルで表す。日本周辺5タイルの GeoParquet 派生版を公開。
url: https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php
license: CC BY 4.0。GHSL R2023A の査読論文と GHS-BUILT-S 製品の引用が必要
formats:
- GeoParquet
- GeoTIFF を含む zip
crs: EPSG:4326（今回読んだ 30 秒角）。Mollweide 版も配布される
spatial_coverage: 全世界をタイルに分割。公開した派生版は日本周辺の R5_C32, R5_C33, R6_C31, R6_C32, R6_C33 の5タイル
temporal_coverage: 1975 年から 2030 年まで 5 年刻みの推計・補間・外挿。実読は E2020 のみ
as_of:
  release: R2023A
  epoch: E2020
  version: V1_0
  checked: 2026-10-25
  hub_revision: 4ee767429ee03ea47a9003c547f92c320474e350
contents:
- 画素ごとの建物面積の推計値
tables:
- name: raster
  read: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss/V1-0/tiles/GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0_R6_C32.zip
  grain: 30 秒角の 1 画素。値はその画素で建物が占める推計面積
  rows: null
  id: []
  no_key:
  - name: KEY_CODE
    note: 国勢調査メッシュコードは持たない。画素とメッシュの面を重ねて集計する
  columns:
  - name: value
    type: UInt32
    meaning: 1 画素の建物面積の推計値。単位は平方メートルで足せる量
    missing: 今回のタイルには NoData メタデータがなく最小値は 0。他のタイルの欠損表現は未確認
---

# GHS-BUILT-S R2023A

## GeoParquet 派生版

[Hugging Face](https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec) に2020年 E2020、30秒角の5タイルを公開した。各タイルの全1,440,000画素を、値を変えずに画素範囲の EPSG:4326 Polygon として格納し、5ファイル合計は7,200,000地物。0を含め全セルを残し、原典ラスタの画素値 SHA-256 と GeoParquet の値列 SHA-256 が各タイルですべて一致した。

列は `tile_code`、ゼロ始まり `cell_row`・`cell_col`、`built_surface_m2` (square metres per cell)、`geometry`。5タイルは日本周辺を含む10度角の原典タイル全体で、隣接国・海域も含み、日本全域は覆わない。原典 ZIP、マニフェスト、CC BY 4.0 の帰属と製品 DOI も同じ Hub データセットに含む。公開 revision: `4ee767429ee03ea47a9003c547f92c320474e350`。

[公式の製品ページ](https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php)は建物面積を画素ごとの平方メートルと説明する。総面積と非住宅用の別製品があり、この reference が実読したのは総面積の E2020 だけである。1975〜2030年の値には時空間的な補間・外挿があり、建物台帳の実測面積ではない。地価や災害への曝露と組む場合も、この値から建物の棟数、用途、居住人数を直接は言えない。

## 実読したタイル

2026-10-24 に frontmatter の E2020・EPSG:4326・30秒角・`R6_C32` の zip を取得し、GDAL 3.13.0dev の `gdalinfo -stats` で GeoTIFF を読んだ。

| 項目 | 結果 |
|---|---|
| 格子 | 1200×1200、UInt32、1 バンド |
| 原点 | 東経 129.990416174197、北緯 39.099583378875 |
| 画素の幅 | 経度 0.008333333300327 度、緯度 -0.008333333299795 度 |
| 値 | 最小 0、最大 525963 平方メートル、画素平均 6732.876 平方メートル。有効率 100% |
| 範囲 | 東経およそ 129.990〜139.990、北緯およそ 29.100〜39.100 |

zip の SHA-256 は `9b3f66aef51beac5ca9b992722353e143b3bb0322a6a8c1ab399dada178deebb`。人口製品と列の原点が約0.00167度異なる。同じ画素番号を結合キーにしない。数値を別の格子に移すときは、面積の量を保存する集計を選び、境界の覆われ方を確かめる。
