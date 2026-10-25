---
kind: dataset
id: yuiseki/forest-typology-validation-2020
description: Global Validation of Forest Types 2020 v0.6 の層別検証点を GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/forest-typology-validation-2020
license: HF と Figshare の表示は CC BY 4.0。原著者と変換元を表示する
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全球から層別に選んだ検証点。森林全体の悉皆調査ではない
temporal_coverage: ForTy 2020 を検証する標本。標本ごとの画像・判読時点は別途確認する
as_of:
  checked: 2026-10-25
  hf_revision: b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c
contents:
- 全検証点と専門家の合意済み点
tables:
- name: all_sites
  read: https://huggingface.co/datasets/yuiseki/forest-typology-validation-2020/resolve/b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c/parquet/all-sites.parquet
  grain: 層別抽出された検証地点1件
  rows: 9100
  id:
  - sampleid
  columns:
  - name: strata
    type: BIGINT
    meaning: 抽出の層。母集団の面積比ではない
  - name: unresolved
    type: BOOLEAN
    meaning: 判読の合意が未確定かどうか
- name: resolved_sites
  read: https://huggingface.co/datasets/yuiseki/forest-typology-validation-2020/resolve/b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c/parquet/resolved-sites.parquet
  grain: 専門家の合意がある検証地点1件
  rows: 8190
  id:
  - sampleid
---

# ForTy の検証点

2026-10-25 に両 Parquet のメタデータを実読し、全点9,100件と合意済み8,190件、`sampleid`・`strata`・`unsure`・`unresolved` と OGC:CRS84 の点を確認した。Hub カードによると7層を各1,300点抽出している。これは面積比例の無作為標本ではないので、単純な平均正解率を全球の面積加重正解率とは呼べない。`unresolved` や `unsure` のある点を無条件に真値にしない。親索引にある ForTy 本体のカードと[北海道の分類面](forty-hokkaido-east-2020.md)を区別する。
