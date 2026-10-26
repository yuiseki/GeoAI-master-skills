---
kind: dataset
id: yuiseki/forty-hokkaido-east-2020
description: ForTy v1 の2020年森林タイプ分類から東北海道の区域を切り出し面に変換した版。
url: https://huggingface.co/datasets/yuiseki/forty-hokkaido-east-2020
license: HF 表示は CC BY 4.0。利用前に元の ForTy の配布条件も確認する
formats:
- GeoParquet
crs: EPSG:32655
spatial_coverage: 東北海道の切り出し範囲。北海道全域ではない
temporal_coverage: ForTy v1 の2020年基準分類。各地点の実地調査日ではない
as_of:
  checked: 2026-10-25
  hf_revision: 7247d816be42065330e34909dd9ffcb66d8876bb
contents:
- 森林タイプ分類の面とクラスコード
tables:
- name: forest_types
  read: https://huggingface.co/datasets/yuiseki/forty-hokkaido-east-2020/resolve/7247d816be42065330e34909dd9ffcb66d8876bb/data/parquet/forty_east_hokkaido_2020.parquet
  grain: 同じクラスの連結画素から作った面
  rows: 63630
  id:
  - fid
  columns:
  - name: class_code
    type: INTEGER
    meaning: ForTy の森林タイプの分類コード
  - name: class_name
    type: VARCHAR
    meaning: 分類名
---

# 東北海道の森林タイプ

2026-10-25 に SHA 固定の Parquet メタデータを実読し、63,630面、`fid`・`class_code`・`class_name` と EPSG:32655 を確認した。面は分類画素をポリゴン化したもので、独立した森林調査区ではない。分類誤差を評価する場合は親索引にある ForTy の元資料や[検証標本](forest-typology-validation-2020.md)を参照し、検証点との時点・範囲の一致を確認する。
