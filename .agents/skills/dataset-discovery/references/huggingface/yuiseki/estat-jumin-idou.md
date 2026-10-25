---
kind: dataset
id: "yuiseki/estat-jumin-idou"
description: "e-Stat 住民基本台帳人口移動報告の統計表スナップショット。"
url: https://huggingface.co/datasets/yuiseki/estat-jumin-idou
license: "政府標準利用規約（第1.0版）に適合。e-Stat API取得時に必要な出典表示を維持"
formats:
- "Parquet"
crs: null
spatial_coverage: "日本の都道府県・市区町村間の人口移動。表により範囲が異なる"
temporal_coverage: "各統計表の調査年による"
as_of:
  checked: 2026-10-26
  hf_revision: 6490dc3478d587da8c175aef11e1ecb001ad228c
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/estat-jumin-idou/resolve/6490dc3478d587da8c175aef11e1ecb001ad228c/parquet/observations/0000180001.parquet
  grain: "統計表の観測値1件"
  rows: null
  id: []
---

# estat-jumin-idou

2026-10-05時点の471表・214,274,401統計値。ファイルは固定取得版であり、更新時は全体を置き換える。地域コードや集計単位を表ごとに確認する。
