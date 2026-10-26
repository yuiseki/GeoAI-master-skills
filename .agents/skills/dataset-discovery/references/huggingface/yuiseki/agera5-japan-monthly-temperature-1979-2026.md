---
kind: dataset
id: yuiseki/agera5-japan-monthly-temperature-1979-2026
description: AgERA5 version 2.0 の月別平均最高・最低気温を日本周辺の0.1度格子中心にしたGeoParquet
url: https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026
license: CC BY 4.0。C3Sの二つの月別コレクションがCC-BY-4.0を宣言。出典表示と改変表示を付けた
formats:
  - GeoParquet 1.1
crs: OGC:CRS84
spatial_coverage: 東経122〜154度、北緯20〜46度の矩形。海域と近隣国を含む。日本の行政境界では切っていない
temporal_coverage: 1979-01〜2026-07、月別571時点
as_of:
  source_snapshot: 2026-10-26
  huggingface_revision: 348e4599bffe05bc48a7033021b7e212b0f00aad
contents:
  - 月別平均最高気温と月別平均最低気温。単位はK
  - 1か月 × 1格子中心で1行、83,200格子、47,507,200行
tables:
  - name: monthly_grid
    read: hf://datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026@348e4599bffe05bc48a7033021b7e212b0f00aad/data/year=*/part-0.parquet
    grain: 1つの0.1度格子中心 × 1か月
    rows: 47507200
    id:
      - month
      - source_grid_row
      - source_grid_col
    join_keys:
      - column: month
        type: DATE
        meaning: 月の初日
        unique: false
        joins: []
      - column: source_grid_row
        type: INTEGER
        meaning: 原典全球格子のゼロ始まり行番号
        unique: false
        joins: []
      - column: source_grid_col
        type: INTEGER
        meaning: 原典全球格子のゼロ始まり列番号
        unique: false
        joins: []
    columns:
      - name: year
        type: BIGINT
        meaning: Hiveパーティションの年。monthと同じ年を示す
      - name: tmax_mean_k
        type: FLOAT
        meaning: AgERA5の日別最高気温の月平均、K
        missing: NULL。原典の-9999 NoData
      - name: tmin_mean_k
        type: FLOAT
        meaning: AgERA5の日別最低気温の月平均、K
        missing: NULL。原典の-9999 NoData
      - name: geometry
        type: BLOB
        meaning: 0.1度格子セルの中心点を表すWKB Point。CRS84
---

# AgERA5 日本周辺月別気温 GeoParquet

## 出典とライセンス

出典は Copernicus Climate Change Service (C3S) / ECMWF の AgERA5 version 2.0。FAO GIS の公開ストレージにある Cloud Optimized GeoTIFF を、地域の窓読みで取得した。対象 collection `AGERA5-TMAX-AVG-M` と `AGERA5-TMIN-AVG-M` は、目録の metadata でそれぞれ CC-BY-4.0 と記録されている。Copernicus Climate Data Store の AgERA5 ページも CC-BY licence を表示している。再配布版にはライセンス、推奨クレジット、抽出範囲と加工内容を記し、C3S・ECMWF・FAO の推奨や承認を示唆しない。

- [公式 C3S AgERA5 データページ](https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators-timeseries)
- [FAO GIS AgERA5 collection metadata](https://stac.yuiseki.net/fao-ferspas/collections.parquet)
- [Hugging Face dataset card](https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026)

## 内容と検証

2026-10-26に固定した月別571時点 (1979-01〜2026-07) を含む。各月に東経122〜154度、北緯20〜46度の矩形にある0.1度格子中心83,200点を出力し、各行に最高気温・最低気温を保持する。矩形には海域と近隣国を含む。日本の行政境界による切り抜きではない。気温値はKのままで、補間や単位変換を行っていない。元ラスターのNoData -9999はNULLにし、格子位置は保持した。

総行数は47,507,200、年別48ファイル、GeoParquet 1.1、CRS84 Point。各気温列は9,993,071値が非NULLで37,514,129値がNULL。出力GeoParquetの各月・両気温列のFloat32値を原典から再読した窓のFloat32 SHA-256と照合し、571か月すべて一致した。原典COGのMD5、サイズ、ETag、出力ファイルSHA-256、検証結果はHub上の `source/MANIFEST.json` と `source/VERIFICATION.json` にある。公開revisionは frontmatter に固定した。

このデータは再解析・モデル由来の格子値で、気象観測所の実測値ではない。geometry はセル面でなく中心点なので、空間集計でセル面積を扱う場合は元の0.1度格子と緯度による面積差を考慮する。
