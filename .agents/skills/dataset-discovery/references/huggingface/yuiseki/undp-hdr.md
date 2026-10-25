---
kind: dataset
id: "yuiseki/undp-hdr"
description: "UNDP Human Development Report 2025 の複合指標と時系列。"
url: https://huggingface.co/datasets/yuiseki/undp-hdr
license: "CC BY 3.0 IGO。UNDP HDR 2025 を出典表示し IGO の条件に従う"
formats:
- "Parquet"
crs: null
spatial_coverage: "国・地域と集計地域。座標・geometryなし"
temporal_coverage: "1990〜2023年"
as_of:
  checked: 2026-10-26
  hf_revision: dfc80c7de776473bd140d87c690600686f30833a
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/undp-hdr/resolve/dfc80c7de776473bd140d87c690600686f30833a/parquet/hdr2025/composite_indices.parquet
  grain: "国・地域・年または指標1件"
  rows: null
  id: []
---

# undp-hdr

195か国・地域と11集計地域を含む。年次版で過去年の系列も再計算され得るため、異なる HDR 報告書間の値をそのまま接続しない。
