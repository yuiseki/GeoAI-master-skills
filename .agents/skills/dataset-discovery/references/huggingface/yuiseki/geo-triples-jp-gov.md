---
kind: dataset
id: yuiseki/geo-triples-jp-gov
description: "日本の政府・自治体公開資料に基づく空間関係と質問応答評価データ。"
url: https://huggingface.co/datasets/yuiseki/geo-triples-jp-gov
license: "CC BY 4.0。出典の表示と加工明記"
formats:
- Parquet
crs: "null。評価用の空間関係と言語データで geometry なし"
spatial_coverage: "日本の47都道府県と1,909市区町村"
temporal_coverage: "固定された自治体公開資料の版"
as_of:
  checked: 2026-10-26
  hf_revision: df079b50cee486517095bf3be178347a6e0690d0
contents:
- 空間関係 triple、文章化データ、評価質問
tables:
- name: triples
  read: https://huggingface.co/datasets/yuiseki/geo-triples-jp-gov/resolve/df079b50cee486517095bf3be178347a6e0690d0/data/triples.parquet
  grain: 空間関係 triple 1件
  rows: 162810
  id: []
---

# Geo Triples Japan Government

47都道府県と1,909市区町村について、空間関係 triple 162,810件、文章データ165,670行、評価質問1,807件。公開行政資料から生成した benchmark であり、モデル推論の結果ではなく、手続き的な oracle の評価資料。行政区域名や住所の正規化を伴うため、観察値と正規化・導出した関係を区別する。CC BY 4.0 の出典表示・加工明記に従う。
