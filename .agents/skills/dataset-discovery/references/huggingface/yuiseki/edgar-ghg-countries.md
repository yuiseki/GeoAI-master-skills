---
kind: dataset
id: "yuiseki/edgar-ghg-countries"
description: "EDGAR 2026 の国別・部門別温室効果ガス排出量ファイル。"
url: https://huggingface.co/datasets/yuiseki/edgar-ghg-countries
license: "CC BY 4.0 対象ガスのみ。化石起源 CO2（NC-ND）は含めず、出典と対象範囲を明記"
formats:
- "ZIP (XLSX)"
crs: null
spatial_coverage: "国・IPCC部門単位。座標・geometryなし"
temporal_coverage: "1970〜2025年"
as_of:
  checked: 2026-10-26
  hf_revision: 46b7502adf44fc9e419fc9c701abbcc058de0b06
contents:
- "固定版データ。利用条件と解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/edgar-ghg-countries/resolve/46b7502adf44fc9e419fc9c701abbcc058de0b06/raw/ghg2026/CH4/EDGAR_CH4_1970_2025.zip
  grain: "国・部門・年・ガスの値"
  rows: null
  id: []
---

# edgar-ghg-countries

CH4、N2O、F-gases、biogenic CO2 の CC BY 4.0 対象分を収録。化石起源 CO2 の NC-ND 条件データは除外。配布ファイルは XLSX を含む ZIP で、国と IPCC 部門の集計表として利用する。
