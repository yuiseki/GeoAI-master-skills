---
kind: dataset
id: yuiseki/wikipedia-geotagged
description: "座標タグのある Wikipedia 記事と本文、Wikidata ID、タグの種類を含む多言語 Parquet。"
url: https://huggingface.co/datasets/yuiseki/wikipedia-geotagged
license: "CC BY-SA 4.0。Wikipedia本文の帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "lat/lon 列。地球以外の天体を示すタグも含む"
spatial_coverage: "世界。英語版・日本語版 Wikipedia の座標つき記事"
temporal_coverage: "2026-09-01 のダンプ"
as_of:
  checked: 2026-10-26
  hf_revision: 24e53f69ef27eb099801ecef1bcca501fcd44a07
contents:
- 記事本文、座標、Wikidata ID、地理タグ
tables:
- name: english_shard_0
  read: https://huggingface.co/datasets/yuiseki/wikipedia-geotagged/resolve/24e53f69ef27eb099801ecef1bcca501fcd44a07/20260901.en/train-00000-of-00005.parquet
  grain: 座標つき英語 Wikipedia 記事1件
  rows: 115000
  id:
  - id
---

# Geotagged Wikipedia

Hub README の総数は英語1,374,056記事、日本語218,496記事。英語・日本語の Parquet shard を収録し、各表のキーは `id`。座標は `lat`、`lon`、種別・天体は `gt_type`、`gt_globe`、`gt_dim`、Wikidata 項目は `qid`。個々の shard は別ファイルで、例の英語 shard は115,000行。座標の付いた記事を全て地名記事とみなさず `gt_type` と `qid` で確認する。本文の再配布・改変には CC BY-SA 4.0 の帰属・ShareAlike 条件が適用される。
