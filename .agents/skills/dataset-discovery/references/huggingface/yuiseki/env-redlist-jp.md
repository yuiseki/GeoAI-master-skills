---
kind: dataset
id: "yuiseki/env-redlist-jp"
description: "環境省 第5次レッドリストの公開済み分類群と絶滅リスク区分。"
url: https://huggingface.co/datasets/yuiseki/env-redlist-jp
license: "CC BY 4.0。環境省・いきものログの出典を表示する"
formats:
- "Parquet"
crs: null
spatial_coverage: "日本の野生生物種。分布座標は含まない"
temporal_coverage: "第5次レッドリストの公開済み分類群。2025〜2026年公開分"
as_of:
  checked: 2026-10-26
  hf_revision: 02f964fefb98b5b2e28a68e23d09cb2b06032b33
contents:
- "分類群別の種名と絶滅危惧カテゴリー"
tables:
- name: birds
  read: https://huggingface.co/datasets/yuiseki/env-redlist-jp/resolve/02f964fefb98b5b2e28a68e23d09cb2b06032b33/parquet/5th/birds.parquet
  grain: "鳥類の種・分類群1件"
  rows: null
  id: []
---

# Japan Red List 5th edition

公開された植物・菌類、鳥類、爬虫類、両生類などの分類群別CSVとParquetを収録する。未公表分類群や、出典ページに許諾表示のない以前のリストは含まない。種の分布位置を持たず、地理分析では別の適法な観察記録と種名を照合する。CC BY 4.0。
