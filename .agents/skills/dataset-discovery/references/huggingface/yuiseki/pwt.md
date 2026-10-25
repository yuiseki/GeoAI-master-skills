---
kind: dataset
id: "yuiseki/pwt"
description: "Penn World Table 11.0 の国・年別マクロ経済指標。"
url: https://huggingface.co/datasets/yuiseki/pwt
license: "CC BY 4.0。Feenstra, Inklaar, Timmer (2015) と PWT 11.0 の DOI を引用"
formats:
- "Parquet"
crs: null
spatial_coverage: "国・地域。座標・geometryなし"
temporal_coverage: "1950〜2023年"
as_of:
  checked: 2026-10-26
  hf_revision: 77cf702fea3f5d3e83d1f514d4b6ebade7eefb45
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/pwt/resolve/77cf702fea3f5d3e83d1f514d4b6ebade7eefb45/parquet/11.0/pwt.parquet
  grain: "国・年1件"
  rows: null
  id: []
---

# pwt

185か国の生産、所得、価格、人口等の国別系列。国コードを境界データと結合する前にコード対応を検証する。PWT の改訂で価格基準等が変わるため異なる版を混ぜない。
