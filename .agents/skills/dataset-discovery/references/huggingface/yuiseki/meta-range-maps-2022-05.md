---
kind: dataset
id: yuiseki/meta-range-maps-2022-05
description: "COVID-19期のMeta Movement Range Maps、行政地域別の日次移動指標。"
url: https://huggingface.co/datasets/yuiseki/meta-range-maps-2022-05
license: "CC BY 4.0。Data for Good at Meta と Humanitarian Data Exchange を出典表示"
formats:
- Parquet
crs: "null。地域IDで境界データと結合する"
spatial_coverage: "153か国の行政地域。geometry は含まない"
temporal_coverage: "2020-03-01〜2022-05-22"
as_of:
  checked: 2026-10-26
  hf_revision: c3450b44d6ab9c5ebc2b438d1ffa43f4bee37eae
contents:
- COVID-19期の日別相対移動量と地域内滞在率
tables:
- name: movement_range_2020
  read: https://huggingface.co/datasets/yuiseki/meta-range-maps-2022-05/resolve/c3450b44d6ab9c5ebc2b438d1ffa43f4bee37eae/movement-range-maps/movement_range_2020.parquet
  grain: 行政地域・日付の組
  rows: 5229342
  id: []
---

# Meta Movement Range Maps 2020-2022

19,142地域、153か国の日次表。3ファイル計12,179,540行で、2020年5,229,342行、2021年5,287,242行、2022年1,662,956行。2020-03-01から2022-05-22まで。`polygon_id`、`polygon_name`、`ds`、2020年2月曜日別基準と比べた相対移動量、単一タイル内にとどまった利用者比を持つ。geometry は含まず、米国の FIPS と他地域の GADM ID が混在するので `polygon_source` も確認する。地域集計値で、個人の位置履歴ではない。CC BY 4.0。
