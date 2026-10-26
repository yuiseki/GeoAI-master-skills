---
kind: dataset
id: yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m
description: Global Pasture Watch v2-betaの草地卓越クラス2018〜2020年を、北海道東部の10×10画素格子に集約したGeoParquet。
url: https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m
card_revision: 92c36ce784db9c9e5bbd517349a3c2fe52ed3357
license: CC BY 4.0。Zenodo記録の許諾。出典・改変表示が必要
formats:
- GeoParquet 1.1.0
- Cropped GeoTIFF (原典30m値を維持)
crs: EPSG:4326
spatial_coverage: 北海道東部。東経141.9995〜144.002度、北緯41.998〜44.0005度
temporal_coverage: 2018・2019・2020年の分類図。各年の観測期はその年の1月1日〜12月31日
as_of:
  source_release: v2-beta
  zenodo_record: 15648551
  checked: 2026-10-25
  hub_revision: 92c36ce784db9c9e5bbd517349a3c2fe52ed3357
contents:
- 10×10の原典画素ブロックごとのクラス別画素数
- 年ごとの有効画素数と最多クラス
- 原典2018〜2020年タイルの対象地域クロップ3枚
- 元COGのZenodo URL、サイズ、MD5とクロップSHA-256
tables:
- name: grassland_class_2018_2020
  read: https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m/resolve/92c36ce784db9c9e5bbd517349a3c2fe52ed3357/data/grassland_class_2018_2020.parquet
  grain: 原典ラスタ10×10画素をまとめた約0.0025度角のセル (北海道東部で地上辺長は約200〜280m)
  rows: 313489
  id:
  - grid_x
  - grid_y
  columns:
  - name: grid_x
    type: INTEGER
    meaning: 原典全球格子の10画素ブロック列番号
  - name: grid_y
    type: INTEGER
    meaning: 原典全球格子の10画素ブロック行番号
  - name: valid_pixels_2018
    type: UTINYINT
    meaning: 2018年の100原典画素中の有効値数
  - name: pixels_other_2018
    type: UTINYINT
    meaning: 2018年のクラス0 (その他の土地被覆) 画素数
  - name: pixels_cultivated_2018
    type: UTINYINT
    meaning: 2018年のクラス1 (管理草地) 画素数
  - name: pixels_natural_2018
    type: UTINYINT
    meaning: 2018年のクラス2 (自然・半自然草地) 画素数
  - name: pixels_open_shrubland_2018
    type: UTINYINT
    meaning: 2018年のクラス3 (開放低木地) 画素数
  - name: dominant_class_2018
    type: UTINYINT, nullable
    meaning: 2018年の最多クラス。同率はコード最小。年内全画素NoDataならNULL
  - name: valid_pixels_2019
    type: UTINYINT
    meaning: 2019年の100原典画素中の有効値数
  - name: pixels_other_2019
    type: UTINYINT
    meaning: 2019年のクラス0 (その他の土地被覆) 画素数
  - name: pixels_cultivated_2019
    type: UTINYINT
    meaning: 2019年のクラス1 (管理草地) 画素数
  - name: pixels_natural_2019
    type: UTINYINT
    meaning: 2019年のクラス2 (自然・半自然草地) 画素数
  - name: pixels_open_shrubland_2019
    type: UTINYINT
    meaning: 2019年のクラス3 (開放低木地) 画素数
  - name: dominant_class_2019
    type: UTINYINT, nullable
    meaning: 2019年の最多クラス。同率はコード最小。年内全画素NoDataならNULL
  - name: valid_pixels_2020
    type: UTINYINT
    meaning: 2020年の100原典画素中の有効値数
  - name: pixels_other_2020
    type: UTINYINT
    meaning: 2020年のクラス0 (その他の土地被覆) 画素数
  - name: pixels_cultivated_2020
    type: UTINYINT
    meaning: 2020年のクラス1 (管理草地) 画素数
  - name: pixels_natural_2020
    type: UTINYINT
    meaning: 2020年のクラス2 (自然・半自然草地) 画素数
  - name: pixels_open_shrubland_2020
    type: UTINYINT
    meaning: 2020年のクラス3 (開放低木地) 画素数
  - name: dominant_class_2020
    type: UTINYINT, nullable
    meaning: 2020年の最多クラス。同率はコード最小。年内全画素NoDataならNULL
  - name: geometry
    type: GEOMETRY('EPSG:4326')
    meaning: 約0.0025度角の矩形セル
---

# Global Pasture Watch: 北海道東部の草地クラス 2018〜2020

## ライセンスと配布

入力は[Zenodo record 15648551](https://zenodo.org/records/15648551)の v2-beta dominant-class COG 2018〜2020年分です。Zenodo API の記録メタデータは `cc-by-4.0` を指定します。GFW Data API の `gpw_grasslands_2024` は別の流通経路・版であり、その API の `license: null` を Zenodo のライセンスで置き換えていません。

原典は各年約16 GBの全球 COG ですが、COG のHTTP範囲読みを利用して対象ウィンドウだけを取得しました。リポジトリには2018・2019・2020年の地域クロップGeoTIFFと派生GeoParquetを収録し、全球COGは再配布していません。原典の Zenodo ファイル名・MD5・全体容量、クロップのSHA-256、対象範囲、変換物のSHA-256はHub内マニフェストにあります。

帰属: Parente et al. (2025), Global Pasture Watch - Annual grassland class and extent maps at 30-m spatial resolution (2000-2024), v2-beta, [Zenodo DOI 10.5281/zenodo.15648551](https://doi.org/10.5281/zenodo.15648551)。この配布物は2018〜2020年のdominant-class sub-datasetから地域を切り出し、10×10画素に集約した改変物です。作者・Global Pasture Watchの承認を示唆しません。

## クラスと集約

Zenodoの仕様で、クラスコードは0=その他の土地被覆、1=管理草地、2=自然・半自然草地、3=開放低木地、255=NoDataです。各GeoParquet行は元ラスタの10×10画素を表し、各年のクラス別画素数、NoData以外の画素数、最多クラスを持ちます。最多クラスが同率の場合は数値コードの小さい方を採用し、そのルールは原典値にはないこの変換での決定規則です。NoDataはすべての年の統計から除き、数値クラス0とは区別しています。

約0.0025度の格子は地理座標で定義されています。東北海道では南北幅が約278m、東西幅が約204mです。正方形でも等面積でもなく、名称中の「約250m」は目安です。

## 実測 (2026-10-25)

- Zenodo global source grid: EPSG:4326、1,436,004×528,004画素、0.00025度、UInt8、NoData 255
- 読取範囲: 8,010×8,010画素、実範囲141.9995〜144.002°E、41.998〜44.0005°N
- 年別原典クロップ画素数: 2018年クラス0/1/2/3/NoDataは15,532,545 / 1,265,313 / 50,861 / 0 / 47,311,381。2019年は15,482,125 / 1,317,073 / 49,521 / 0 / 47,311,381。2020年は15,424,664 / 1,376,510 / 47,545 / 0 / 47,311,381
- GeoParquet: 313,489行、21列、EPSG:4326、Polygon 313,489件、無効ジオメトリ0
- ID `(grid_x, grid_y)` は全行で一意
- 原典クロップからすべての行・年のクラス別カウント、有効画素数、最多クラスを再計算して照合
- [固定版GeoParquetと原典クロップ](https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m/tree/92c36ce784db9c9e5bbd517349a3c2fe52ed3357)

分類は衛星画像・モデルによる推定で、現地確認ラベルではありません。2018〜2020年のクラス境界の変化をそのまま実際の草地転換とみなさず、予測の不確実性や分類整合性を確認してください。
