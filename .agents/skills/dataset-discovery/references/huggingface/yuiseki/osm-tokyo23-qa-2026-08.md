---
kind: dataset
id: yuiseki/osm-tokyo23-qa-2026-08
description: "東京23区のOSM空間質問に対する複数エンジンの回答比較。"
url: https://huggingface.co/datasets/yuiseki/osm-tokyo23-qa-2026-08
license: "ODbL 1.0。OpenStreetMap 由来データの帰属表示と ShareAlike 条件を守る"
formats:
- Parquet
crs: "null。質問と回答の評価コーパスで geometry なし"
spatial_coverage: "東京都23区のOpenStreetMap"
temporal_coverage: "2026-08 の固定 OSM スナップショットに対する回答"
as_of:
  checked: 2026-10-26
  hf_revision: d44f06a8e04a016fdf2030b86e0a04ae0bbadaf0
contents:
- 質問と複数方式の回答、曖昧さ・確認応答
tables:
- name: qa
  read: https://huggingface.co/datasets/yuiseki/osm-tokyo23-qa-2026-08/resolve/d44f06a8e04a016fdf2030b86e0a04ae0bbadaf0/data/train-00000-of-00001.parquet
  grain: 質問と回答方式の評価レコード
  rows: null
  id: []
---

# OpenStreetMap Tokyo 23 Q&A 2026-08

215問の質問コーパスに対し、PostGIS、Overpass 等の方式による回答、曖昧な質問や追加確認が必要な例をまとめる。質問数は215だが、1問が複数方式・状態の行になるため行数と質問数を同一視しない。geometry は含まず、空間QAモデルの評価・失敗分析に使う。OSM由来データの再配布では ODbL 1.0 と © OpenStreetMap contributors の帰属・ShareAlike 条件を守る。
