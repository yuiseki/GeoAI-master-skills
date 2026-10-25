---
kind: dataset
id: yuiseki/kontur-population-2023-11-01-22km
description: Kontur の全球 H3 人口推計。HDX の2023-11-01版22kmレイヤーを GeoPackage から GeoParquet に変換した。
url: https://huggingface.co/datasets/yuiseki/kontur-population-2023-11-01-22km
license: Creative Commons Attribution International (HDX license id cc-by)。Kontur の公式案内は CC BY で商用利用も可とする。HDX metadata では版番号を特定していない
formats:
- GeoPackage gzip
- GeoParquet
crs: EPSG:3857 (22km版の GeoPackage を実読)
spatial_coverage: 全球。分解能・海域などの収録は版による
temporal_coverage: 2023-11-01版の推計。観測したその日の人口ではない
as_of:
  checked: 2026-10-25
contents:
- H3 セルの推計人口
tables:
- name: population_22km
  read: hf://datasets/yuiseki/kontur-population-2023-11-01-22km/parquet/kontur_population_20231101_r4.parquet
  grain: H3 resolution 4 のセル。22kmは公称の分解能
  rows: 71283
  id:
  - h3
  columns:
  - name: population
    type: DOUBLE
    meaning: 推計人数。年齢内訳なし
  - name: geometry
    type: geometry:EPSG:3857
    meaning: H3 セルの面。原典 GeoPackage の形状を保持
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

[Kontur の説明](https://www.kontur.io/datasets/population-dataset/)は Kontur Population を CC BY とし、商用を含む利用を認めている。HDX API のパッケージ `kontur-population-dataset-22km` は `license_id=cc-by`、`license_title=Creative Commons Attribution International (CC BY)` を返す。表示された版番号は特定されていないため、配布カードでは CC BY と記し、CC BY 4.0 と断定しない。

## GeoParquet 派生配布

[Hugging Face の公開リポジトリ](https://huggingface.co/datasets/yuiseki/kontur-population-2023-11-01-22km)に2023-11-01の22km版 (H3 resolution 4) を固定した。原典 `kontur_population_20231101_r4.gpkg.gz` は6,659,105バイトで、HDXのMD5 `421948ce3d82a6d20d83969f8bd541ff` と一致。GeoParquet は71,283セル、H3キーは全件一意、推計人口の合計は8,031,924,024。CRSはEPSG:3857、PolygonとMultiPolygonがあり、nullと無効ジオメトリはいずれも0。原典との行・属性・形状の双方向差分は0件。GeoParquetのCRSメタデータ、元ファイルと出力のSHA-256はリポジトリの `parquet/profile.json`、`raw/MANIFEST.json` に記録した。

出典は Kontur Population dataset © Kontur, release 2023-11-01。GeoPackageからGeoParquetへの形式変換を行い、行と形状は変更していない。H3 resolution 4 の22km版は概観・広域集計用であり、400m版相当の局所分析には使えない。推計人口を国勢調査の実測値と扱わない。
