---
kind: dataset
id: "yuiseki/osm-wiki"
description: "OpenStreetMap Wiki の8言語ページを抽出した地理タグ・地物知識テキスト。"
url: https://huggingface.co/datasets/yuiseki/osm-wiki
license: "CC BY-SA 2.0。OSM Wiki 著者を出典表示し、Share-Alike を維持"
formats:
- Parquet
crs: null
spatial_coverage: "OpenStreetMap のタグ・地物・地域記述。テキストのみでgeometryなし"
temporal_coverage: "2026-01-30 full-history dump から 2026-09-17 抽出"
as_of:
  checked: 2026-10-26
  hf_revision: ada3a2dcc675b6a9ab34328c41566cbe9f490e4b
contents:
- "固定版データ。ライセンスと解釈上の注意は本文を参照"
tables:
- name: data
  read: https://huggingface.co/datasets/yuiseki/osm-wiki/resolve/ada3a2dcc675b6a9ab34328c41566cbe9f490e4b/data/train-00000-of-00001.parquet
  grain: "Wikiページ1件"
  rows: 78178
  id: []
---

# osm-wiki

78,178ページ、8言語の抽出テキスト。各行にタイトル、言語、namespace、本文、元の `licence` を含む。全言語を網羅するわけではなく、wikitext を平文にしたもので、画像やテンプレート展開結果は含まれない。OSMタグの意味やローカル知識の検索・RAG向け。出典と CC BY-SA 2.0 を守る。
