---
kind: dataset
id: "yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2"
description: "GFW Forest Flux Model v1.3.2 の東北海道 2001〜2023年累積純炭素フラックス。"
url: https://huggingface.co/datasets/yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2
license: "CC0 1.0。無帰属でも再利用可能だが、Gibbs et al. と Dataverse DOI の引用を推奨"
formats:
- GeoParquet
crs: "OGC:CRS84"
spatial_coverage: "東北海道 143〜146°E、42〜45°N。WGS 84 / CRS84"
temporal_coverage: "2001〜2023年の累積値。年別値ではない"
as_of:
  checked: 2026-10-26
  hf_revision: 74d3167e20455e9956bc3d1ccd09d2f40babef4b
contents:
- "固定版データ。ライセンスと解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2/resolve/74d3167e20455e9956bc3d1ccd09d2f40babef4b/data/net_flux.parquet
  grain: "約30 mセル中心1件"
  rows: 34516630
  id: []
---

# gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2

34,516,630行のGeoParquet 1.1。元の Harvard Dataverse v1.3.2 タイルから作られた CC0 の地域切り出しで、現行GFW API v20260327（2001〜2025年）とは異なる旧モデル版。値は23年間の累積推定量であり、年次観測と解釈しない。セル中心点で、画素フットプリントではない。NoData/0セルは省略。出典 DOI と論文を引用する。
