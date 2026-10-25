---
kind: dataset
id: yuiseki/timezone-boundary-builder-2026d
description: Timezone Boundary Builder 2026d の三種類のタイムゾーン境界を GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d
license: HF 表示は ODbL。元の ODbL に伴う表示・共有条件を確認する
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 全球。ただし境界の収録状況と有効域は元資料に依存
temporal_coverage: 2026d版の境界。歴史的な UTC オフセットの時系列ではない
as_of:
  checked: 2026-10-25
  hf_revision: cc26444397089df7b2e8bc02d40f4ed9d9936aae
contents:
- full、1970、now の三種類のタイムゾーン境界
tables:
- name: timezones
  read: https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d/resolve/cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones.parquet
  grain: タイムゾーン ID の面
  rows: 419
  id:
  - tzid
- name: timezones_1970
  read: https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d/resolve/cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones-1970.parquet
  grain: 1970年以降を同一視するタイムゾーン ID の面
  rows: 301
  id:
  - tzid
- name: timezones_now
  read: https://huggingface.co/datasets/yuiseki/timezone-boundary-builder-2026d/resolve/cc26444397089df7b2e8bc02d40f4ed9d9936aae/parquet/timezones-now.parquet
  grain: 現在の規則で同一視するタイムゾーン ID の面
  rows: 65
  id:
  - tzid
---

# タイムゾーン境界 2026d

2026-10-25 に固定版の三つの Parquet メタデータを実読し、full 419面、1970版301面、now版65面、`tzid` と EPSG:4326 を確認した。`now` は国境ではなく現在のタイムゾーンの同等性による統合版で、過去の時刻変換に使う資料ではない。境界面だけから任意の日時の UTC オフセットを計算せず、別に IANA tzdb の規則を使う。[元データのカード](../../timezone-boundary-builder.md)を参照する。
