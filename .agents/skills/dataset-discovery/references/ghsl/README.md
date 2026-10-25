---
kind: catalog
id: ghsl
description: 欧州委員会 JRC の人口、建物面積などを表す Global Human Settlement Layer。製品・年・座標系・解像度ごとに配布される。
url: https://human-settlement.emergency.copernicus.eu/datasets.php
access: JRC の製品別ページと公開 HTTP ディレクトリから、製品、年、CRS、解像度、V1-0、タイル番号を選ぶ。認証なしで小さい zip タイルを取得できた
license: CC BY 4.0。最新リリースの査読論文と、該当製品の引用を求める
crs: 製品と配布形態による。今回読んだ 30 秒角は EPSG:4326
spatial_coverage: 全世界の陸域を含む製品群。タイルごとに範囲が違う
temporal_coverage: 製品と版による。ここでは R2023A の 1975 年から 2030 年までを扱う。2025 年と 2030 年は将来の投影
as_of:
  release: R2023A
  checked: 2026-10-24
contents:
- 居住人口の推計格子
- 建物面積の推計格子
children:
- population.md
- built-surface.md
---

# GHSL R2023A

この目録では、実際に小さいタイルを読んだ [人口](population.md) と [建物面積](built-surface.md) だけを詳しく記す。高さ、体積、都市化度なども別製品としてあるが、まだ実読していない。

## 入口と固定のしかた

[公式の製品一覧](https://human-settlement.emergency.copernicus.eu/datasets.php)で製品と版を選び、[JRC の公開ディレクトリ](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/)の製品名、対象年、座標系・解像度、`V1-0/tiles/` をたどる。2026-10-24 に人口と建物面積の2020年・30秒角・`R6_C32` の zip を認証なしで取得し、GeoTIFF を GDAL 3.13.0dev で読めた。全世界を含む単一 zip は大きいので、最初は対象範囲のタイルだけを取る。

同じ R2023A でも製品と対象年を省略しない。URL、zip の名前、取得日を記録する。人口は2020年まで推計、2025・2030年は投影。建物面積も時系列の推定・補間・外挿を含むので、過去の年をすべて衛星による直接観測と呼ばない。

2026-10-25 に人口と建物面積の E2020・30秒角を、日本周辺の5タイルずつ選んで GeoParquet 化し、[Hugging Face](https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec) に公開した。各タイルは1,440,000セル、画素値を変えずにセル範囲 Polygon へ変換している。対象は R5_C32、R5_C33、R6_C31、R6_C32、R6_C33。データセットは隣接国・海域を含む地域タイルであり、日本の行政界で切り抜いたものではない。二製品のグリッド原点は異なるので、画素行・列だけで結合しない。

## 利用条件

[公式の利用条件](https://human-settlement.emergency.copernicus.eu/GHSLhowToCite.php)は CC BY 4.0 と明記し、適切な出典表示には最新リリースの査読論文が必要だとしている。製品別ページの引用も確認する。GHSL のウェブサイトだけを記すのでは足りない。

## 結合時の注意

今回読んだ人口と建物面積の `R6_C32` タイルはどちらも EPSG:4326、1200×1200、30秒角だが、左端の経度が人口 `129.992082840857`、建物面積 `129.990416174197` で異なる。同じ行列添字を同じ場所として結ばない。共通の分析単位を決め、量の合計と境界画素を照合して再集計する。度単位の画素面積は緯度で変わる。
