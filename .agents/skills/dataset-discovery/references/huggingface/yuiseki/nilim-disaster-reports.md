---
kind: dataset
id: "yuiseki/nilim-disaster-reports"
description: "国土技術政策総合研究所の災害調査報告から権利確認できた本文。"
url: https://huggingface.co/datasets/yuiseki/nilim-disaster-reports
license: "CC BY 4.0。本文中の第三者図表・引用の表示も維持"
formats:
- "JSON Lines"
crs: null
spatial_coverage: "日本の災害報告。座標・geometryなし"
temporal_coverage: "収録報告の発行年による"
as_of:
  checked: 2026-10-26
  hf_revision: c615f04667eb0102793a0015f980a9c2b5fbddac
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/nilim-disaster-reports/resolve/c615f04667eb0102793a0015f980a9c2b5fbddac/flash.jsonl
  grain: "報告・ページ1件"
  rows: null
  id: []
---

# nilim-disaster-reports

権利区分 a・b のみ収録した rights-screened subset。共同著作・第三者権利・条件不明の資料は除外。26報告、65 PDF、883ページ。位置を含む記述の抽出と文書分析向け。
