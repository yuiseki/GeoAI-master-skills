---
kind: dataset
id: yuiseki/un-wpp
description: "国連 World Population Prospects 2024 の各国人口推計、人口構成、出生・死亡等の表。"
url: https://huggingface.co/datasets/yuiseki/un-wpp
license: "CC BY 3.0 IGO。国連 World Population Prospects 2024 を出典表示"
formats:
- Parquet
crs: null
spatial_coverage: "国・地域単位と地域集計。geometry なし"
temporal_coverage: "WPP2024: 推計1950〜2023年、投影2024〜2100年。2026-01-19更新表も含む"
as_of:
  checked: 2026-10-26
  hf_revision: c403d785094f63881424a7911d861ef97eab82a7
contents:
- 国・地域別人口、年齢・性別、出生、死亡、人口学的指標
tables:
- name: population_by_age_sex_1950_2023
  read: https://huggingface.co/datasets/yuiseki/un-wpp/resolve/c403d785094f63881424a7911d861ef97eab82a7/parquet/wpp2024/populationbysingleagesex_medium_1950_2023.parquet
  grain: 国・地域、年齢、性別、年の組
  rows: null
  id: []
---

# United Nations World Population Prospects

国連人口部の各種人口推計・投影表を収録する。WPP2024 は53表、全体で200,840,623行。例のファイルは人口の単歳・性別推計 1950〜2023 年。2024〜2100 年の中位投影は別ファイルで、2026-01-19更新の表も分かれている。人口推計、投影、更新系列を混ぜず、ファイル名とシナリオを確認する。

geometry はなく、国や地域コード・年齢・性別・年で集計する。国境面を含まず、空間分析には別の境界データとコード体系の対応確認が必要。HF の `license: other` は `CC BY 3.0 IGO` を示す。国連 WPP2024 を出典表示し、ライセンスの IGO 条件を適用する。
