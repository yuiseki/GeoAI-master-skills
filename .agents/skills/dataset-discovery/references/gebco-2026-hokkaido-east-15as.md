---
kind: dataset
id: yuiseki/gebco-2026-hokkaido-east-15as
description: GEBCO 2026 地形格子の北海道東部 15 秒角範囲を、各画素の面と標高に変換した GeoParquet。
url: https://huggingface.co/datasets/yuiseki/gebco-2026-hokkaido-east-15as
license: CEDA 配布は Open Government Licence v3.0。GEBCO Grid 自体は public domain。どちらも出典表示が必要
formats:
  - GeoParquet 1.1.0
crs: EPSG:4326
spatial_coverage: 東北海道沖を含む経度 143–146°E、緯度 42–45°N の矩形。北海道東部全域を覆う境界ではない
temporal_coverage: GEBCO_2026 Grid。コンパイルの入力時点は場所とデータ源ごとに異なる
as_of:
  version: GEBCO_2026
  published: 2026-04-23
  deployed: 2026-10-25
  huggingface_commit: 5da32601a62457c36b001d8ab5524d905acb1cd7
contents:
  - 海底地形と陸域標高のモデル値 (m)
  - 元格子間隔 15 秒角。元測深データの精度や実測解像度を示すものではない
  - GEBCO Type Identifier (TID) は含めない
tables:
  - name: elevation
    read: https://huggingface.co/datasets/yuiseki/gebco-2026-hokkaido-east-15as/resolve/5da32601a62457c36b001d8ab5524d905acb1cd7/data/elevation.parquet
    grain: 15 秒角格子の 1 画素の矩形フットプリント。観測点ではない
    rows: 518400
    id: []
    columns:
      - name: elevation_m
        type: SMALLINT
        meaning: GEBCO の海面基準標高 (m)。海底は負、陸上は正
      - name: geometry
        type: geometry:EPSG:4326
        meaning: 元画素の経緯度矩形。GeoParquet の Polygon
---

# GEBCO 2026 北海道東部 GeoParquet

## 原典・ライセンス

対象の固定版は GEBCO_2026。配布は [GEBCO 公式ページ](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid)からリンクされる CEDA の GeoTIFF タイルを使った。原典は 15 秒角の全球格子で、2026-04-23 に公開された。

[CEDA のデータ目録](https://catalogue.ceda.ac.uk/uuid/fb236c93aa574cb9b5154db45dfdd784/)は公開データで登録不要、Open Government Licence v3.0 の適用、指定 DOI の引用を明記する。[GEBCO の利用規約](https://www.gebco.net/data-products/gridded-bathymetry/terms-of-use)は GEBCO Grid を public domain とし、複製・配布・改変・商用利用を認める。条件は出典表示、公式な地位や推奨を示唆しないこと、出典を偽らないこと。Hub のカードは CEDA 配布の OGL と GEBCO 規約の両方を表示し、ライセンス欄を `other` とした。

指定された引用表記:

> GEBCO Bathymetric Compilation Group 2026 (2026): The GEBCO_2026 Grid - a continuous terrain model for oceans and land at 15 arc-second intervals. NERC British Oceanographic Data Centre, 23 April 2026. doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa.

## 固定範囲の作成と実測

2026-10-25 に、CEDA の東経 90–180°・北緯 0–90°タイルから 143–146°E、42–45°N を GDAL `/vsicurl/` で切り出し、再標本化せずに各画素を WKB Polygon に変換した。出典は `source/MANIFEST.json` にタイル URL、HTTP ETag、更新日時、クリップの SHA-256 と共に記録した。元タイル全体は複製せず、公開領域の該当部分を直接読み取った。

GeoParquet は EPSG:4326 の 518,400 行。1 行は格子画素の矩形で、`elevation_m` は `SMALLINT`、範囲は -5,722〜1,869 m、NULL と NoData は 0 件、無効ジオメトリは 0 件だった。中心点の範囲は経度 143.002083–145.997917°、緯度 42.002083–44.997917°。実測は GeoAI-skills の `profile_layer.py` で行った。

## 読むときの注意

- 15 秒角は配布格子の間隔であって、元の測深・標高データの測定密度や精度ではない。観測・推定・補間を含む混成モデルである。
- 浅海域には平均海面以外の鉛直基準の入力値が含まれうる。
- 負の標高が水深を表す。これは測定地点ではなく格子画素のモデル値。
- TID Grid は含まない。各画素の由来が必要な分析では、原典の TID と同じ版を別に取得して照合する。
- 航海やその他の安全用途に使用しない。GEBCO の推奨を受けた公式データとして見せない。
