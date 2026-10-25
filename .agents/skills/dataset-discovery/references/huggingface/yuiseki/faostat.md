---
kind: dataset
id: "yuiseki/faostat"
description: "FAOSTAT の農業・食料・土地利用・気候等の統計スナップショット。"
url: https://huggingface.co/datasets/yuiseki/faostat
license: "CC BY 4.0。FAO を出典表示し、個別ドメインの注記も保持"
formats:
- "ZIP (XLSX)"
crs: null
spatial_coverage: "国・地域・項目単位。座標・geometryなし"
temporal_coverage: "ドメイン・指標ごとに異なる"
as_of:
  checked: 2026-10-26
  hf_revision: 1908be260630c5b5156a1a694aaa6570b4086318
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/faostat/resolve/1908be260630c5b5156a1a694aaa6570b4086318/raw/2026-10-04/Land_Use_E_All_Data_(Normalized).zip
  grain: "国・項目・年の観測値1件"
  rows: null
  id: []
---

# faostat

66ドメイン、約1.52 GBの固定取得版から土地利用正規化表を例示。地域コード・単位・集計定義はドメインごとに確認する。固定マニフェストとチェックサムを使い、FAOの元 URL 変更後も取得版を特定する。
