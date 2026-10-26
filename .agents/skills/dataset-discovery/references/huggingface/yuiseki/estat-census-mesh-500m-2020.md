---
kind: dataset
id: yuiseki/estat-census-mesh-500m-2020
description: "令和2年国勢調査の500m地域メッシュ12表を47都道府県分まとめた Parquet。"
url: https://huggingface.co/datasets/yuiseki/estat-census-mesh-500m-2020
license: "CC BY 4.0。総務省統計局/e-Stat の出典を表示し、加工を明記する"
formats:
- Parquet
crs: "null"
spatial_coverage: "日本の500m 2分の1地域メッシュ。メッシュコードで位置を特定"
temporal_coverage: "2020-10-01 国勢調査"
as_of:
  checked: 2026-10-26
  hf_revision: 6dc3df6c26e96cd8399968a260fd54c4aa55fbe1
contents:
- 人口、世帯、年齢、就業、住宅等12表
tables:
- name: T001101
  read: https://huggingface.co/datasets/yuiseki/estat-census-mesh-500m-2020/resolve/6dc3df6c26e96cd8399968a260fd54c4aa55fbe1/parquet/T001101.parquet
  grain: 500m地域メッシュの統計1項目
  rows: 467053
  id:
  - KEY_CODE
---

# 2020年国勢調査 500mメッシュ

12表を47都道府県分、564原資料から表別 Parquet にまとめたもの。全表合計5,604,594行。例は[人口総数表 T001101](https://huggingface.co/datasets/yuiseki/estat-census-mesh-500m-2020/resolve/6dc3df6c26e96cd8399968a260fd54c4aa55fbe1/parquet/T001101.parquet)。geometry はなく、メッシュコードで位置を特定する。同じメッシュコードでも JGD2000 と JGD2011 の区域割当が異なる表があるため、表ごとの datum を確認して混在させない。秘匿値 `*` と行の無いメッシュをゼロと読み替えない。CC BY 4.0。
