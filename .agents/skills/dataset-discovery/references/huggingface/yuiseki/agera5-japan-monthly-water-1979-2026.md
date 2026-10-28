---
kind: dataset
id: yuiseki/agera5-japan-monthly-water-1979-2026
description: AgERA5 の月別降水量と FAO の月別基準蒸発散量 (AgERA5 から FAO-56 Penman-Monteith で計算) を、日本周辺の 0.1 度格子中心にした GeoParquet
url: https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-water-1979-2026
license: CC BY-SA 4.0。FAO の目録のメタデータが 2 つのコレクションとも CC-BY-SA-4.0 を宣言 (2026-10-28)。出典表示と改変表示を付けた
formats:
  - GeoParquet 1.1
crs: OGC:CRS84
spatial_coverage: 東経122〜154度、北緯20〜46度の矩形。値があるのは陸のセルだけ (海は NULL)。日本の行政境界では切っていない
temporal_coverage: 1979-01〜2026-07、月別571時点
as_of:
  source_snapshot: 2026-10-28
  huggingface_revision: b3d1a83d2961580129e6f0222868585dc008c229
contents:
  - 月の降水量の合計 (mm/月) と月の基準蒸発散量の合計 (mm/月)
  - 1か月 × 1格子中心で1行、83,200格子、47,507,200行
tables:
  - name: monthly_grid
    read: hf://datasets/yuiseki/agera5-japan-monthly-water-1979-2026@b3d1a83d2961580129e6f0222868585dc008c229/data/year=*/part-0.parquet
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
        joins:
          - agera5-japan-monthly-temperature-1979-2026:monthly_grid.month
      - column: source_grid_row
        type: INTEGER
        meaning: 原典全球格子のゼロ始まり行番号。気温の版と同じ格子
        unique: false
        joins:
          - agera5-japan-monthly-temperature-1979-2026:monthly_grid.source_grid_row
      - column: source_grid_col
        type: INTEGER
        meaning: 原典全球格子のゼロ始まり列番号。気温の版と同じ格子
        unique: false
        joins:
          - agera5-japan-monthly-temperature-1979-2026:monthly_grid.source_grid_col
    columns:
      - name: year
        type: BIGINT
        meaning: Hiveパーティションの年。monthと同じ年を示す
      - name: precip_mm
        type: FLOAT
        meaning: AgERA5 の降水 (precipitation flux) の月合計、mm/月
        missing: NULL。原典の-9999 NoData (陸でないセル)
      - name: et0_mm
        type: FLOAT
        meaning: FAO の基準蒸発散量 (FAO-56 Penman-Monteith、AgERA5 から) の月合計、mm/月
        missing: NULL。原典の-9999 NoData。precip_mm と同じセルで NULL
      - name: geometry
        type: BLOB
        meaning: 0.1度格子セルの中心点を表すWKB Point。CRS84
---

# AgERA5 日本周辺の月別降水量と基準蒸発散量 GeoParquet

## 出典とライセンス

出典は Copernicus Climate Change Service (C3S) / ECMWF の AgERA5 version 2.0 の降水 (`AGERA5-PF-M`) と、FAO が AgERA5 から FAO-56 の Penman-Monteith の式で計算した基準蒸発散量 (`AGERA5-ET0-M`)。FAO の公開ストレージの Cloud Optimized GeoTIFF を、気温の版 ([agera5-japan-monthly-temperature-1979-2026](agera5-japan-monthly-temperature-1979-2026.md)) と同じ窓で読んだ。

ライセンスは、FAO の目録 ([fao-ferspas](../../../references/fao-ferspas/README.md) の `collections.parquet`) の `license` 列が、2 つのコレクションとも CC-BY-SA-4.0 (2026-10-28 に読んだ)。FAO の GISMGR の API (`data.apps.fao.org/gismgr/api/v2/catalog/workspaces/C3S/mapsets/...`) の記録には、ライセンスの欄が無い。気温の月別 (CC-BY-4.0) と違い、継承 (SA) の条件が付くので、使った成果物を配るときは同じライセンスにする。

## 内容と検証 (2026-10-28)

| 項目 | 値 |
|---|---|
| 行 | 47,507,200 (571 か月 × 83,200 格子)、年ごとのファイル 48 |
| 値のある行 | 各列 9,993,071 (2 つの列で同じセル)、NULL 37,514,129 |
| 範囲 | precip_mm 0.0〜1,293.35、et0_mm 2.753〜219.328 |
| 照合 | 全ての月と列で、出力の Float32 の値の SHA-256 が、原典の窓を読み直した値の SHA-256 と一致 (`source/VERIFICATION.json`)。Hugging Face に上げた 48 ファイルの sha256 が手元の作成物と一致 |

- 気温の版と、`month`、`source_grid_row`、`source_grid_col` の 3 つで結べる。格子は同じ。
- 再解析とモデルから作った格子の値で、観測所の実測ではない。基準蒸発散量は、草地を想定した参照の値で、林の実際の蒸発散ではない。
- 日射の月別のコレクションは目録に無い (日別の `AGERA5-SRF` だけ)。基準蒸発散量は日射を入力に含む。

## 作り方

`scripts/build.py` (気温の版の build.py を、GDAL の Python 束縛から rasterio に替えたもの) と `scripts/publish.py` が Hugging Face にある。原典の全球のラスタは複製していない。
