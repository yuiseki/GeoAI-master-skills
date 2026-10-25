---
kind: dataset
id: "yuiseki/gsj-reports"
description: "産業技術総合研究所 地質調査総合センターの公開報告ページ抽出テキスト。"
url: https://huggingface.co/datasets/yuiseki/gsj-reports
license: "CC BY 4.0。第三者資料の引用表示を本文から保持"
formats:
- "JSON Lines"
crs: null
spatial_coverage: "日本の地質関連文書。座標・geometryなし"
temporal_coverage: "1950〜2026年に発行された文書"
as_of:
  checked: 2026-10-26
  hf_revision: d3128d862dbfb5feb9c026ece81ab3e66f21462a
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/gsj-reports/resolve/d3128d862dbfb5feb9c026ece81ab3e66f21462a/report.jsonl
  grain: "報告ページ1件"
  rows: null
  id: []
---

# gsj-reports

報告ページと月報の抽出テキスト。PDF・図・画像自体は含まない。49,065ページ、4,166 PDF由来のテキストで、公式 GSJ 製品ではない。地名・地質語の検索や文書分析向け。
