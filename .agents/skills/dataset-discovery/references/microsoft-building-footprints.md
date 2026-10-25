---
kind: dataset
id: microsoft/global-ml-building-footprints
description: Microsoft が衛星・航空画像から機械学習で抽出した建物輪郭のポリゴン。実在建物の完全な台帳ではない。
url: https://github.com/microsoft/GlobalMLBuildingFootprints
license: CDLA Permissive 2.0。データを共有する場合はライセンス本文を添える
formats:
- GeoJSON Lines を gzip 圧縮した .csv.gz
crs: EPSG:4326
spatial_coverage: 全世界の収録地域。日本の収録あり。画像や検出確率による欠落がある
temporal_coverage: 画像の撮影時期は地域で異なる。配布索引は 2026-08-13 のスナップショットであり、建物の観測日ではない
as_of:
  index_snapshot: 2026-08-13
  checked: 2026-10-24
contents:
- 推定した建物輪郭
- 一部の輪郭の推定高さと検出信頼度
tables:
- name: buildings
  read: https://bfppub.blob.core.windows.net/$web/2026-08-13/dataset-links.csv
  grain: GeoJSON Lines の 1 Feature が推定建物輪郭 1 件。索引の Location と QuadKey で配布ファイルを選ぶ
  rows: null
  id: []
  no_key:
  - name: building_id
    note: サンプルの Feature に永続的な建物 ID は無い。別版の同一建物を ID で追えない
  - name: code5
    note: 日本の市区町村コードは無い。行政界へ空間結合する
  columns:
  - name: geometry
    type: geometry:EPSG:4326
    meaning: 推定した建物の輪郭。日本の試読タイルでは Polygon
  - name: height
    type: DOUBLE
    meaning: 推定高さ。単位はメートル
    missing: -1 は高さの推定値が無いこと。試読した日本タイルと東京東部・関東の2タイルでは全件が -1
  - name: confidence
    type: DOUBLE
    meaning: 検出信頼度の指標。建物の高さの確信度ではない
    missing: -1 は未提供。試読した日本タイルと東京東部・関東の2タイルでは全件が -1
---

# Microsoft Global ML Building Footprints

[公式の README](https://github.com/microsoft/GlobalMLBuildingFootprints)は、画像から建物らしい画素を分類し、輪郭へ変換したデータと説明する。建物台帳ではなく、撮影時点も場所ごとに異なる。浸水想定区域と重ねて建物らしい輪郭の数や面積を測る用途はあるが、建物の現存、用途、住民数や実際の被害額まで分かるわけではない。

## 選び方と読み方

2026-08-13 の固定[索引CSV](https://bfppub.blob.core.windows.net/$web/2026-08-13/dataset-links.csv)は `Location,QuadKey,Url,Size,UploadDate` を持つ。2026-10-24 に全索引を取得して数えると 30,340 行、日本は 203 行だった。全ての日本タイルを一度に取得せず、必要な範囲の QuadKey と `Location=Japan` に対応する URL を索引から選ぶ。`.csv.gz` だが中身は CSV ではなく 1 行 1 Feature の GeoJSON Lines。`ogrinfo -if GeoJSONSeq` で gzip のまま読めた。

実読したのは索引中の `Japan,131221222` の[約137 kBのタイル](https://bfppub.z5.web.core.windows.net/2026-08-13/global-buildings.geojsonl/RegionName=Japan/quadkey=131221222/part-00189-110f5303-ff85-4c71-a2bf-c6070024fec8.c000.csv.gz)。GDAL 3.13.0dev で 1804 Feature、Polygon、EPSG:4326、範囲は東経141.152344〜141.303891・北緯45.213022〜45.258895と測った。`height` と `confidence` はこのタイルの全件が `-1.0` で、未提供を表す。[公式 README の FAQ](https://github.com/microsoft/GlobalMLBuildingFootprints#how-do-we-estimate-building-height)も `-1` の意味を説明する。他の日本タイル、とくに東京で高さがあるかは未確認。

索引 CSV の SHA-256 は `de61b569b0c23c364d61173632d8c5487ea30bf20912c55b9fa1ab4a89d01148`、試読タイルは `a9f69c11497ac1164e6e7424c07fc4612fb645e26e8e551c5c4f602eaa03c10e`。再現時は索引の日付だけでなく、使用タイルの URL と取得日も残す。配布の更新日を画像の撮影日や建物の新築日と見なさない。

## 欠落・重複・利用条件

公式 README は、古い画像や検出確率の低い画像を処理対象から外しており、四角い欠落域が生じると記す。輪郭の数を建物の真の棟数や人口曝露の確定値とせず、地元の台帳や別データとの重なり、空白、重複をサンプルで確かめる。日本の全タイルの精度や建物 ID の安定性は未確認。

[Microsoft の公式 README](https://github.com/microsoft/GlobalMLBuildingFootprints#license)は CDLA Permissive 2.0 と明記する。[ライセンス本文](https://cdla.dev/permissive-2-0/)は、データを共有する場合にライセンス本文を添える条件を置く。分析結果と元データの再配布を区別し、二次情報の別ライセンス表記をそのまま採らない。

## GeoParquet 派生配布

[東京東部・関東の2タイル](https://huggingface.co/datasets/yuiseki/microsoft-building-footprints-kanto-2026-08-13)を 2026-08-13 索引から固定し、原典 GeoJSON Lines gzip と GeoParquet を公開した。対象 QuadKey は `133002112` と `133002113`。実測値は合計 5,781,554 件（4,011,210 件、1,770,344 件）、全件 Polygon、null geometry は 0 件。`ST_IsValid` が false の形状は 68 件あり、原典を変えずに保持した。高さと confidence は全件 `-1`。ファイル別の境界、件数、SHA-256 は Hugging Face の `parquet/profile.json` と `raw/2026-08-13/MANIFEST.json` にある。CDLA-Permissive-2.0 の本文もリポジトリの `LICENSE` に同梱した。
