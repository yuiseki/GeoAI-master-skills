---
kind: dataset
id: koppen-geiger-2023
description: 全球の Köppen-Geiger 気候区分図と気候変数。Figshare DOI 10.6084/m9.figshare.21789074 の v2 を固定して参照する。
url: https://doi.org/10.6084/m9.figshare.21789074.v2
license: CC BY 4.0 (Figshare v2 のメタデータで確認)
formats:
- GeoTIFF ZIP
- NetCDF ZIP
crs: 配布ファイルの中身は未実読。実ファイルの CRS を確認する
spatial_coverage: 全球の陸域
temporal_coverage: 気候の基準期間と将来シナリオはファイルごと。2023 は論文・製品の名称で、単年観測ではない
as_of:
  checked: 2026-10-25
  version: v2
contents:
- Köppen-Geiger 気候分類
- 基準期間と将来シナリオ別の地図および関連気候変数
tables:
- name: classification_tif
  read: https://doi.org/10.6084/m9.figshare.21789074.v2
  grain: 地図の1画素。解像度とクラス符号はファイル未実読
  rows: null
  id: []
---

# Köppen-Geiger 気候区分

[Figshare API の記事 21789074](https://api.figshare.com/v2/articles/21789074)は、2026-10-25 の照会で DOI `10.6084/m9.figshare.21789074.v2`、CC BY 4.0 と応答した。`koppen_geiger_tif.zip` は130,618,411バイト、`koppen_geiger_nc.zip` は755,276,285バイト。これらは圧縮ファイルのメタデータ値で、展開後の容量ではない。ZIP の取得は途中でタイムアウトしたため、画素値・座標・クラス対応表は未実読。

[製作者の案内](https://www.gloh2o.org/koppen/)は現行版を V3 と呼ぶ。ここで固定した Figshare v2 と混同しない。気候区分は期間平均やモデルから作る分類で、単年の実際の天候でも観測点の気温でもない。比較するときは同じ版・基準期間・シナリオをそろえる。
