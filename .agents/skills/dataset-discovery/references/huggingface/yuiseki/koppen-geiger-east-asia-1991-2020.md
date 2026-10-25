---
kind: dataset
id: yuiseki/koppen-geiger-east-asia-1991-2020
description: Köppen-Geiger の1991〜2020年の気候区分を東アジアで面に変換した版。
url: https://huggingface.co/datasets/yuiseki/koppen-geiger-east-asia-1991-2020
license: HF 表示は CC BY 4.0。元の Figshare の対象版も確認する
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 概ね東経122〜154度・北緯20〜48度の矩形内の有効な分類セル
temporal_coverage: 1991〜2020年の気候基準期間。単年の気象値ではない
as_of:
  checked: 2026-10-25
  hf_revision: 0eaf52184f5051e56f78737d4f66be8af257cb58
contents:
- 気候区分コードと記号のポリゴン
tables:
- name: climate_regions
  read: https://huggingface.co/datasets/yuiseki/koppen-geiger-east-asia-1991-2020/resolve/0eaf52184f5051e56f78737d4f66be8af257cb58/parquet/koppen_geiger_east_asia_1991_2020.parquet
  grain: 同じ気候区分の連結セルから作った面
  rows: 13480
  id:
  - fid
  columns:
  - name: class_code
    type: INTEGER
    meaning: 気候区分の数値コード
  - name: class_symbol
    type: VARCHAR
    meaning: 気候区分の記号
---

# 東アジアの気候区分

2026-10-25 に SHA 固定の Parquet メタデータを実読し、13,480面、`class_code`・`class_symbol`・`class_description` と EPSG:4326 を確認した。面の数は元のセル数ではない。NoData の海域等を未分類地として扱わず、1991〜2020年平均の気候を2020年の実況や単年の変化と取り違えない。[全球版の元データ](../../koppen-geiger-2023.md)とは版と対象期間を照合してから併用する。
