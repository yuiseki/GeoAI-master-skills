---
kind: dataset
id: "yuiseki/ilostat"
description: "ILOSTAT の労働市場・雇用統計の指標ファイルと辞書。"
url: https://huggingface.co/datasets/yuiseki/ilostat
license: "CC BY 4.0。ILOSTAT を出典表示し、指標定義・分類辞書を併用"
formats:
- "CSV"
crs: null
spatial_coverage: "国・地域単位。座標・geometryなし"
temporal_coverage: "指標ごとに異なる"
as_of:
  checked: 2026-10-26
  hf_revision: 6f6d8ac78d395c1ac0043b288ceaf87745176732
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/ilostat/resolve/6f6d8ac78d395c1ac0043b288ceaf87745176732/raw/2026-10-04/indicator/CLD_TPOP_SEX_AGE_GEO_NB_A.csv.gz
  grain: "国・年齢・性別・年等の統計値1件"
  rows: null
  id: []
---

# ilostat

1,963指標ファイルと244コード辞書の固定版。国別の雇用・人口統計で、ファイル一覧の行数は個別ファイルの実測値ではない。コード辞書と単位、推計・観測の区分を確認する。
