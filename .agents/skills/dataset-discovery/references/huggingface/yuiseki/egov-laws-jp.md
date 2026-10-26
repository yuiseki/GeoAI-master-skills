---
kind: dataset
id: "yuiseki/egov-laws-jp"
description: "e-Gov 法令検索の法令改正履歴と XML・テキストを収録する日本語コーパス。"
url: https://huggingface.co/datasets/yuiseki/egov-laws-jp
license: "CC BY 4.0。法律本文は著作権法第13条により著作物でなく、デジタル庁の付加情報は PDL 1.0"
formats:
- Parquet
crs: null
spatial_coverage: "日本の法令。地理形状・座標なし"
temporal_coverage: "各法令改正・施行時点"
as_of:
  checked: 2026-10-26
  hf_revision: d2c2899645ac45cf2e6f8ac84ec48010d6df47ae
contents:
- "固定版データ。ライセンスと解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/egov-laws-jp/resolve/d2c2899645ac45cf2e6f8ac84ec48010d6df47ae/parquet/laws.parquet
  grain: "法令改正1件"
  rows: 10679
  id: []
---

# egov-laws-jp

10,679件の法令改正を1行ずつ収録する。都市計画・河川・土地利用など空間に関係する法令を検索・根拠確認する日本語資料として使えるが、法令本文が現行であるか、施行済みであるかは `is_unenforced` と施行日を別途確認する。e-Gov の一括ダウンロード由来。
