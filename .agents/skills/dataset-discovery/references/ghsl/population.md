---
kind: dataset
id: ghsl/population
description: GHSL R2023A の居住人口。各画素の推計人数であり、国勢調査の画素別実測ではない。
url: https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php
license: CC BY 4.0。GHSL R2023A の査読論文と GHS-POP 製品の引用が必要
formats:
- GeoTIFF を含む zip
crs: EPSG:4326（今回読んだ 30 秒角）。Mollweide 版も配布される
spatial_coverage: 全世界をタイルに分割。実読は日本の一部を含む R6_C32 のみ
temporal_coverage: 1975 年から 2020 年まで 5 年刻みの推計、2025 年と 2030 年は投影。実読は E2020 のみ
as_of:
  release: R2023A
  epoch: E2020
  version: V1_0
  checked: 2026-10-24
contents:
- 画素ごとの居住人口の推計人数
tables:
- name: raster
  read: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2020_GLOBE_R2023A_4326_30ss/V1-0/tiles/GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0_R6_C32.zip
  grain: 30 秒角の 1 画素。値は居住人口の推計人数
  rows: null
  id: []
  no_key:
  - name: KEY_CODE
    note: 日本の国勢調査メッシュコードは持たない。画素とメッシュの面を重ねて集計する
  columns:
  - name: value
    type: Float64
    meaning: 1 画素の居住人口の推計人数。足せる量
    missing: 公式の製品資料は NoData として -200 を記すが、今回のタイルには NoData メタデータがなく最小値は 0。0 を一律に欠損としない
---

# GHS-POP R2023A

[公式の製品ページ](https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php)によると、人口は CIESIN GPWv4.11 の国勢調査・行政区別人口を建物分布で細分した推計である。国勢調査の画素別の観測値ではない。2025年と2030年は投影なので、過去からの実測変化と混ぜない。

## 実読したタイル

2026-10-24 に frontmatter の E2020・EPSG:4326・30秒角・`R6_C32` の zip を取得し、GDAL 3.13.0dev の `gdalinfo -stats` で GeoTIFF を読んだ。

| 項目 | 結果 |
|---|---|
| 格子 | 1200×1200、Float64、1 バンド |
| 原点 | 東経 129.992082840857、北緯 39.099583378875 |
| 画素の幅 | 経度 0.008333333300327 度、緯度 -0.008333333299795 度 |
| 値 | 最小 0、最大 23096.502、画素平均 70.818。サンプルタイル内の有効率 100% |
| 範囲 | 東経およそ 129.992〜139.992、北緯およそ 29.100〜39.100 |

zip の SHA-256 は `37c6ddb59c7d8986a779a257b8fbbab398d2a4280a980dcaf1c9528de2467a98`。全世界のタイルや他の年で同じ欠損表現になるかは未確認。タイルの範囲外を人口0と扱わない。

日本の国勢調査メッシュと比べるなら、CRSと面を揃えて人口の量を再集計し、合計とメッシュの覆われ方を数える。人口の推計手順に建物分布が既に使われているため、建物面積との関係を完全に独立した二つの観測の一致として読まない。
