---
kind: dataset
id: "yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m"
description: "Global Pasture Watch 草地分類の東北海道 2018〜2020年版。"
url: https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m
license: "CC BY 4.0。Parente et al. と Zenodo の元データを出典表示"
formats:
- GeoParquet
crs: "EPSG:4326"
spatial_coverage: "東北海道 (東経142〜144度、北緯42〜44度)。EPSG:4326"
temporal_coverage: "2018〜2020年の約250 mセル分類"
as_of:
  checked: 2026-10-26
  hf_revision: 92c36ce784db9c9e5bbd517349a3c2fe52ed3357
contents:
- "固定版データ。詳細な派生・利用条件は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m/resolve/92c36ce784db9c9e5bbd517349a3c2fe52ed3357/data/grassland_class_2018_2020.parquet
  grain: "約250 mセル1件"
  rows: null
  id: []
---

# gpw-grasslands-hokkaido-east-2018-2020-250m

30 m分類画素を10×10で集約した地域派生版。分類クラスはモデル推定であり、現地検証済みの土地利用真値を意味しない。CC BY 4.0 の表示と元論文・Zenodo の引用を維持する。
