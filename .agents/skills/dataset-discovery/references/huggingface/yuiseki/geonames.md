---
kind: dataset
id: yuiseki/geonames
description: "GeoNames の世界地名辞書。座標つき地物、別名、行政階層を日付で固定した Parquet。"
url: https://huggingface.co/datasets/yuiseki/geonames
license: "CC BY 4.0。GeoNames の帰属表示が必要"
formats:
- Parquet
- GeoParquet 1.0
crs: OGC:CRS84
spatial_coverage: "世界の地名。GeoNames に登録された地物"
temporal_coverage: "2026-10-01 の配布元スナップショット"
as_of:
  checked: 2026-10-26
  hf_revision: f11302971633d42c2f9d806862f62b299e92852b
contents:
- 座標つき地名、別名、行政階層、行政コード
tables:
- name: geoname
  read: https://huggingface.co/datasets/yuiseki/geonames/resolve/f11302971633d42c2f9d806862f62b299e92852b/parquet/20261001/geoname/part-00.parquet
  grain: GeoNames の地名1件
  rows: 3936115
  id:
  - geonameid
  columns:
  - name: geometry
    type: GEOMETRY(Point)
    meaning: OGC:CRS84 の地名座標
- name: alternate_names
  read: https://huggingface.co/datasets/yuiseki/geonames/resolve/f11302971633d42c2f9d806862f62b299e92852b/parquet/20261001/alternate_names.parquet
  grain: 地名の別名1件
  rows: 19219062
  id:
  - alternate_name_id
---
# GeoNames 2026-10-01

`geoname` は 13,472,217 行、別名表は 19,219,062 行。GeoNames は同じ URL の日次ダンプを上書きするため、このリポジトリは取得日付きの入力を固定し、元ファイルの SHA-256 を MANIFEST に残している。[GeoNames の利用条件](https://www.geonames.org/export/)に従い GeoNames を出典表示する。

| 表 | 行数 | 固定ファイル |
|---|---:|---|
| geoname | 13,472,217 | [`part-00.parquet`](https://huggingface.co/datasets/yuiseki/geonames/resolve/{sha}/parquet/20261001/geoname/part-00.parquet) ほか4分割 |
| alternate_names | 19,219,062 | [Parquet](https://huggingface.co/datasets/yuiseki/geonames/resolve/{sha}/parquet/20261001/alternate_names.parquet) |
| hierarchy | 519,183 | [Parquet](https://huggingface.co/datasets/yuiseki/geonames/resolve/{sha}/parquet/20261001/hierarchy.parquet) |

地名表の `geonameid` が別名表の結合キー。行政コードは主に GeoNames 側の形式で、日本の JIS コードと同一ではない。別名の `isolanguage=wkdt` は Wikidata ID として使われる行がある。これは住所の網羅的な住所録でも、地物の境界データでもない。
