---
kind: dataset
id: yuiseki/timezone-boundary-builder-2026d
description: Timezone Boundary Builder 2026d の3種類の境界面を検証し、GeoParquet と原典 ZIP を Hugging Face に固定。
url: https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d
source_url: https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2026d
license: 境界データと派生 GeoParquet は ODbL 1.0。再配布時にライセンス表示と share-alike 条件を維持する。コードの MIT と混同しない
formats:
- GeoParquet
- GeoJSON ZIP
crs: EPSG:4326 (longitude, latitude)
spatial_coverage: 全球。境界の一部は近似で、海上境界や無人島の扱いに注意
temporal_coverage: 2026d の境界スナップショット。歴史的な時差・夏時間ルールは含まない
as_of:
  checked: 2026-10-25
  source_release: 2026d
  hub_revision: cc26444397089df7b2e8bc02d40f4ed9d9936aae
  raw_manifest: raw/2026-10-25/MANIFEST.json
contents:
- tzid とポリゴンまたはマルチポリゴン境界
- timezone-names JSON に統合境界の説明
- 元 GeoJSON ZIP と SHA-256 マニフェスト
tables:
- name: timezones
  read: hf://datasets/yuiseki/timezone-boundary-builder-2026d@cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones.parquet
  grain: 包括的なタイムゾーン境界。1 tzid あたり1 feature
  rows: 419
  id:
  - tzid
- name: timezones_1970
  read: hf://datasets/yuiseki/timezone-boundary-builder-2026d@cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones-1970.parquet
  grain: 1970年以降同じ時刻を保つゾーンを統合
  rows: 301
  id: []
- name: timezones_now
  read: hf://datasets/yuiseki/timezone-boundary-builder-2026d@cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones-now.parquet
  grain: 現時点で同じ時刻のゾーンを統合。全 IANA tzid の一覧ではない
  rows: 65
  id: []
---

# Timezone Boundary Builder 2026d

[2026d リリース](https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2026d)の3種類の GeoJSON ZIP を取得し、DuckDB Spatial で GeoParquet に変換して[公開](https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d)した。リリース資産、SHA-256、GeoParquet の行数・geometry の検証結果は Hub の `raw/2026-10-25/MANIFEST.json` と `parquet/index.json` にある。公開時の Hub revision は `cc26444397089df7b2e8bc02d40f4ed9d9936aae`。

| 構成 | 行数 | 内容 |
|---|---:|---|
| `all-zones` | 419 | 包括的な境界 |
| `same-since-1970` | 301 | 1970年以降同じ時刻を保つゾーンを統合 |
| `same-since-now` | 65 | 現時点で同じ時刻のゾーンを統合 |

すべて EPSG:4326、`tzid` は構成内で一意、geometry は null でなく DuckDB Spatial の妥当性検査を通過した。原典 ZIP と変換済み GeoParquet を同じデータセットに含める。

境界と時刻変換は別問題です。時差・夏時間・歴史上の変更には IANA tzdb を用いてください。点を境界に結ぶ際は、海上・国境・無所属の点の扱いを決める必要があります。上流データの一部の境界は近似で、海上境界を推定し、一部の無人島を省略します。

データ用ライセンスは[ODbL 1.0](https://github.com/evansiroky/timezone-boundary-builder/blob/2026d/DATA_LICENSE)です。派生データベースの公開にはライセンス表示と share-alike 条件が適用されます。OpenStreetMap contributors と IANA time-zone data を含む旨をデータカードに記載し、ライセンス本文も `LICENSE` として配布しています。
