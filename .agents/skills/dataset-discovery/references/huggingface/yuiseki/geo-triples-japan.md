---
kind: dataset
id: yuiseki/geo-triples-japan
description: "日本の地理関係 triple と文章・評価質問を含む GeoAI ベンチマーク。"
url: https://huggingface.co/datasets/yuiseki/geo-triples-japan
license: "ODbL 1.0。OpenStreetMap 由来データの帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "null。評価用の空間関係と言語データで geometry なし"
spatial_coverage: "日本。OpenStreetMap と Natural Earth から作成した課題"
temporal_coverage: "データの固定版。Hub commit SHA で固定"
as_of:
  checked: 2026-10-26
  hf_revision: bb99cebbc984047bf34bcc0412c29ea51a452499
contents:
- 地理関係 triple、文章化データ、評価質問
tables:
- name: triples
  read: https://huggingface.co/datasets/yuiseki/geo-triples-japan/resolve/bb99cebbc984047bf34bcc0412c29ea51a452499/data/triples.parquet
  grain: 空間関係 triple 1件
  rows: 510616
  id: []
---

# Geo Triples Japan

空間関係 triple 510,616件、文章データ483,922行、評価質問8,890件。Hugging Face 固定版の Parquet 群を提供する。地物 geometry ではなく、地理エンティティ間の関係を自然言語・構造化表現で扱う評価資料。OSM 由来データを含むため ODbL 1.0 の帰属表示と ShareAlike 条件を守り、データベース派生物を再配布するときもライセンスを引き継ぐ。出典には © OpenStreetMap contributors を明記する。
