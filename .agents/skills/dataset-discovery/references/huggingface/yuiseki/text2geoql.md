---
kind: dataset
id: "yuiseki/text2geoql"
description: "場所と関心対象の指示から OpenStreetMap の Overpass QL を生成する学習データ。"
url: https://huggingface.co/datasets/yuiseki/text2geoql
license: "ODbL 1.0。OpenStreetMap由来のデータベースとして帰属表示とShareAlike条件を守る"
formats:
- "Parquet"
crs: null
spatial_coverage: "世界の地名を対象にする自然言語・Overpass QLペア"
temporal_coverage: "固定版。Hub commit SHAで固定"
as_of:
  checked: 2026-10-26
  hf_revision: 9f8b46bd82897b44222593040a923830fbc5b088
contents:
- "AreaWithConcern 指示と Overpass QL クエリの学習ペア"
tables:
- name: train_pairs
  read: https://huggingface.co/datasets/yuiseki/text2geoql/resolve/9f8b46bd82897b44222593040a923830fbc5b088/data/train-00000-of-00001.parquet
  grain: "自然言語指示とOverpass QLの対応1件"
  rows: null
  id: []
---

# Text to GeoQL

約4,900件の検証済み学習ペアを収録し、148種類のPOIカテゴリを扱う。クエリは公開 Overpass API で実行し、少なくとも1件の要素を返すことを確認したとREADMEに記載されている。地名解決・OSMタグ検証・クエリ生成を含むため ODbL 1.0 と © OpenStreetMap contributors の条件に従う。モデル評価の数値は作者の実験結果で、データ行そのものの保証ではない。
