---
kind: dataset
id: kontur-population-20231101
description: Kontur の全球 H3 人口推計。HDX の2023-11-01版を参照し、22km版の GeoPackage を実読した。
url: https://data.humdata.org/dataset/kontur-population-dataset
license: HDX の当該データセットの表示は CC BY。正確な版と再配布条件は配布元で再確認する
formats:
- GeoPackage gzip
crs: EPSG:3857 (22km版の GeoPackage を実読)
spatial_coverage: 全球。分解能・海域などの収録は版による
temporal_coverage: 2023-11-01版の推計。観測したその日の人口ではない
as_of:
  checked: 2026-10-25
contents:
- H3 セルの推計人口
tables:
- name: population_22km
  read: https://data.humdata.org/dataset/kontur-population-dataset-22km
  grain: H3 resolution 4 のセル。22kmは公称の分解能
  rows: 71283
  id:
  - h3
  columns:
  - name: population
    type: REAL
    meaning: 推計人数。年齢内訳なし
- name: population_3km
  read: https://data.humdata.org/dataset/kontur-population-dataset-3km
  grain: H3 resolution 6 のセル。行数と座標は未実読
  rows: null
  id:
  - h3
- name: population_400m
  read: https://data.humdata.org/dataset/kontur-population-dataset
  grain: 公称400mのセル。行数と座標は未実読
  rows: null
  id:
  - h3
---

# Kontur Population 2023-11-01

[HDX の400m版](https://data.humdata.org/dataset/kontur-population-dataset)、[3km版](https://data.humdata.org/dataset/kontur-population-dataset-3km)、[22km版](https://data.humdata.org/dataset/kontur-population-dataset-22km)を区別する。HDX API の `package_show` で 2023-11-01 の配布ファイルを確認した。圧縮サイズは400m版 2,436,991,241バイト、3km版 185,340,844バイト、22km版 6,659,105バイト。400m版と3km版の中身は未読。

2026-10-25 に22km版の `kontur_population_20231101_r4.gpkg.gz` を実読した。解凍後18,182,144バイト、表 `population` は71,283行で H3 は全行で一意。`fid`、`geom`、`h3`、`population` があり、人口合計は約80.32億、最小1、最大22,732,635、NULLなし。CRS は EPSG:3857。推計値であり国勢調査の実測人数、昼間人口、年齢別人口の代わりにはしない。

[Kontur の説明](https://www.kontur.io/datasets/population-dataset/)には無料公開ファイルとは別の有料 API の案内がある。HDX に無料ファイルがあることは API の無料利用を意味しない。HDX メタデータの `cc-by` から CC BY 4.0 とまでは特定できないため、再配布、とくに Hugging Face への凍結前に対象ファイルのライセンス原文を確認する。
