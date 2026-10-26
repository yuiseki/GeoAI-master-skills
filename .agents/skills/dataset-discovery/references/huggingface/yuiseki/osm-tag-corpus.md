---
kind: dataset
id: yuiseki/osm-tag-corpus
description: "多言語の OpenStreetMap タグ説明・関連語をまとめた GeoAI 用テキストコーパス。"
url: https://huggingface.co/datasets/yuiseki/osm-tag-corpus
license: "ODbL 1.0。OpenStreetMap 由来データの帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "null。タグ説明テキストで geometry なし"
spatial_coverage: "OpenStreetMap の多言語タグ語彙"
temporal_coverage: "固定版。Hub commit SHA で固定"
as_of:
  checked: 2026-10-26
  hf_revision: 1e9549778e59cc08f398b2de9cbde090e128a931
contents:
- OSMタグ説明、関連語、件数などの多言語コーパス
tables:
- name: train
  read: https://huggingface.co/datasets/yuiseki/osm-tag-corpus/resolve/1e9549778e59cc08f398b2de9cbde090e128a931/data/train-00000-of-00001.parquet
  grain: OSMタグ記述または関連語レコード
  rows: 31913
  id: []
---

# OpenStreetMap Tag Corpus

31,913行、9,803種のタグ、70言語、48,852文を収録する。geometry ではなく、OSM タグの意味検索、埋め込み、分類やタグ推薦に使うテキスト資料。OSM Wiki 等に由来する記述を含むため、再配布時は ODbL 1.0 の帰属表示と ShareAlike 条件を守り、© OpenStreetMap contributors を明記する。
