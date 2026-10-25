---
kind: dataset
id: yuiseki/microsoft-building-footprints-kanto-2026-08-13
description: Microsoft が画像から推定した建物輪郭の関東周辺2タイルを GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/microsoft-building-footprints-kanto-2026-08-13
license: HF 表示は other、名称は CDLA Permissive 2.0。元データと帰属表示を確認する
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 関東周辺の2 quadkey タイル。行政界による関東地方の切り出しではない
temporal_coverage: 元索引は2026-08-13。画像の撮影時期は場所で異なり、この日付を建築時点にできない
as_of:
  checked: 2026-10-25
  hf_revision: 6d86dea6444c02b3304b58052c0e2109f85130e6
contents:
- 建物輪郭の面、推定高さ、信頼度
tables:
- name: buildings_133002112
  read: https://huggingface.co/datasets/yuiseki/microsoft-building-footprints-kanto-2026-08-13/resolve/6d86dea6444c02b3304b58052c0e2109f85130e6/parquet/buildings-quadkey-133002112.parquet
  grain: 画像から検出された建物輪郭1件
  rows: 4011210
  id: []
  columns:
  - name: quadkey
    type: VARCHAR
    meaning: 収録元タイル。建物の一意 ID ではない
  - name: height
    type: DOUBLE
    meaning: 推定高さ。欠測や推定誤差を確認する
- name: buildings_133002113
  read: https://huggingface.co/datasets/yuiseki/microsoft-building-footprints-kanto-2026-08-13/resolve/6d86dea6444c02b3304b58052c0e2109f85130e6/parquet/buildings-quadkey-133002113.parquet
  grain: 画像から検出された建物輪郭1件
  rows: 1770344
  id: []
  columns:
  - name: confidence
    type: DOUBLE
    meaning: 検出の信頼度。実測の建物存在確率とは限らない
---

# Microsoft 建物輪郭の関東周辺2タイル

2026-10-25 に両 Parquet のメタデータを実読し、4,011,210件と1,770,344件、計5,781,554件を確認した。列は `quadkey`、`height`、`confidence`、EPSG:4326 の面。建物を一意に識別する ID は見当たらない。境界での重複、見落とし、輪郭の位置ずれ、撮影年のばらつきを扱い、建物の実測台帳と同一視しない。[元データのカード](../../microsoft-building-footprints.md)を参照する。
