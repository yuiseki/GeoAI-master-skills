---
kind: dataset
id: yuiseki/osm-wikidata-brand-jp
description: "日本のOSMブランド名・タグ値と Wikidata を結ぶ entity-linking データ。"
url: https://huggingface.co/datasets/yuiseki/osm-wikidata-brand-jp
license: "ODbL 1.0 (OSM由来データ)。Wikidataの構造化情報はCC0。複合データベースにはODbLの帰属・ShareAlike条件"
formats:
- Parquet
crs: "null。店舗ブランドとタグ値の表で geometry なし"
spatial_coverage: "日本のOpenStreetMap地物とブランド"
temporal_coverage: "固定版。Hub commit SHA で固定"
as_of:
  checked: 2026-10-26
  hf_revision: e88d1fcb356554886cd797012ab61274f1814ce1
contents:
- OSMのブランドタグとWikidata項目の対応
tables:
- name: brands
  read: https://huggingface.co/datasets/yuiseki/osm-wikidata-brand-jp/resolve/e88d1fcb356554886cd797012ab61274f1814ce1/data/train-00000-of-00001.parquet
  grain: OSMブランド値または対応項目の行
  rows: 172852
  id: []
---

# OpenStreetMap Wikidata Brands Japan

1,859ブランド、172,852地物、221タグキーにまたがる65,026種類の値を記述する。geometry を含まないため OSM 地物IDやタグ値を地理データに結合して使う。OSM 由来のデータは ODbL 1.0、Wikidata の構造化情報は CC0。結合したデータベースを配布する場合は ODbL の帰属・ShareAlike 条件を適用し、© OpenStreetMap contributors を表示する。
