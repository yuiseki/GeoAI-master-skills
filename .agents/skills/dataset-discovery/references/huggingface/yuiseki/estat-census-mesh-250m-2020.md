---
kind: dataset
id: yuiseki/estat-census-mesh-250m-2020
description: "令和2年国勢調査の250m地域メッシュ12表を47都道府県分まとめた Parquet。"
url: https://huggingface.co/datasets/yuiseki/estat-census-mesh-250m-2020
license: "CC BY 4.0。総務省統計局/e-Stat の出典を表示し、加工を明記する"
formats:
- Parquet
crs: "null"
spatial_coverage: "日本の250m 4分の1地域メッシュ。メッシュコードで位置を特定"
temporal_coverage: "2020-10-01 国勢調査"
as_of:
  checked: 2026-10-26
  hf_revision: a119d1c805740636d606c6268db5ef5f23dcfaa9
contents:
- 人口、世帯、年齢、就業、住宅等12表
tables:
- name: T001102
  read: https://huggingface.co/datasets/yuiseki/estat-census-mesh-250m-2020/resolve/a119d1c805740636d606c6268db5ef5f23dcfaa9/parquet/T001102.parquet
  grain: 250m地域メッシュの統計1項目
  rows: 1164622
  id:
  - KEY_CODE
---

# 2020年国勢調査 250mメッシュ

12表を47都道府県分、564原資料から表別 Parquet にまとめたもの。全表合計13,975,584行。例は[人口総数表 T001102](https://huggingface.co/datasets/yuiseki/estat-census-mesh-250m-2020/resolve/a119d1c805740636d606c6268db5ef5f23dcfaa9/parquet/T001102.parquet)。geometry はなく、メッシュコードで位置を特定する。同じメッシュコードでも JGD2000 と JGD2011 の区域割当が異なる表があるため、表ごとの datum を確認して混在させない。秘匿値 `*` と行の無いメッシュをゼロと読み替えない。CC BY 4.0。
