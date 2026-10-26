---
kind: dataset
id: yuiseki/meta-move-dist
description: "Meta の Movement Distribution。行政地域ごとの日別移動距離区分の分布。"
url: https://huggingface.co/datasets/yuiseki/meta-move-dist
license: "CC BY 4.0。Data for Good at Meta と Humanitarian Data Exchange を出典表示"
formats:
- Parquet
crs: "null。行政地域IDで境界データと結合する"
spatial_coverage: "217か国の行政地域。geometry は含まない"
temporal_coverage: "2026-06-01〜2026-08-31。92日のうち76日"
as_of:
  checked: 2026-10-26
  hf_revision: a37d91796acf99641278cff788822166685053f0
contents:
- 行政地域ごとの日別・居住地からの距離帯別人口比
tables:
- name: movement_distribution_2026
  read: https://huggingface.co/datasets/yuiseki/meta-move-dist/resolve/a37d91796acf99641278cff788822166685053f0/movement-distribution/movement_distribution_2026.parquet
  grain: 行政地域・日付・距離区分の組
  rows: 11735260
  id: []
---

# Meta Movement Distribution 2026

217か国、38,943地域、11,735,260行。2026-06-01から08-31の92日のうち76日分を含み、欠測日があるため `ds` を確認する。`gadm_id`、`gadm_name`、日付 `ds` と、距離区分ごとの地域内シェアを持つ。位置は Facebook 利用者のうち位置共有を許可した人の集計値で、個人の軌跡ではない。境界 geometry は含まず、行政界データを別途適法に用意して結合する。CC BY 4.0。
