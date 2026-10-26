---
kind: dataset
id: "yuiseki/moni1000-reports"
description: "環境省モニタリングサイト1000の公開調査報告テキスト。"
url: https://huggingface.co/datasets/yuiseki/moni1000-reports
license: "政府標準利用規約（第1.0版）。出典表示と第三者権利の条件を守る"
formats:
- "JSON Lines"
crs: null
spatial_coverage: "日本の高山・森林草原・里山等の調査地。ページ本文に地理情報を含む場合がある"
temporal_coverage: "報告書発行年による"
as_of:
  checked: 2026-10-26
  hf_revision: 05fd96210b17890f16f4bddef745cb502752d9be
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/moni1000-reports/resolve/05fd96210b17890f16f4bddef745cb502752d9be/moni1000.jsonl
  grain: "報告ページ1件"
  rows: null
  id: []
---

# moni1000-reports

73報告、12,148ページの既存テキスト層を抽出。OCRを実施していないため画像のみの文字は含まれない。公開条件を確認できない資料は除外し、報告書に記載された調査地情報は元資料で確認する。
