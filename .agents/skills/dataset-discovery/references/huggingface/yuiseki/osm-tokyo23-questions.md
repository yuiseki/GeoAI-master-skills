---
kind: dataset
id: yuiseki/osm-tokyo23-questions
description: "東京23区の OpenStreetMap に対する空間質問の評価用コーパス。"
url: https://huggingface.co/datasets/yuiseki/osm-tokyo23-questions
license: "ODbL 1.0。OpenStreetMap 由来データの帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "null。質問テキストで geometry なし"
spatial_coverage: "東京都23区のOpenStreetMap"
temporal_coverage: "2026-08 の固定 OSM スナップショットに基づく課題"
as_of:
  checked: 2026-10-26
  hf_revision: 75b757e21704fd84c5fb4ea9b37783da109f8653
contents:
- OSM空間質問とタグ根拠
tables:
- name: questions
  read: https://huggingface.co/datasets/yuiseki/osm-tokyo23-questions/resolve/75b757e21704fd84c5fb4ea9b37783da109f8653/data/train-00000-of-00001.parquet
  grain: 地理質問1件
  rows: 215
  id: []
---

# OpenStreetMap Tokyo 23 Wards Questions

215問、123種類のタグに基づく、回答前の質問データ。固定した OSM データを根拠にするため、質問応答・検索・空間推論モデルの評価に使える。geometry はなく、質問文とタグ条件を扱う。OSM 由来の内容を再配布・派生利用する場合は ODbL 1.0 と © OpenStreetMap contributors の表示に従う。
