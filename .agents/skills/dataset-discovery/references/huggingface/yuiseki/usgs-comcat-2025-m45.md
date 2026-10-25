---
kind: dataset
id: yuiseki/usgs-comcat-2025-m45
description: USGS ComCat から2025年の M4.5 以上の地震を抽出した固定版 GeoParquet。
url: https://huggingface.co/datasets/yuiseki/usgs-comcat-2025-m45
license: HF 表示は other、名称は public-domain。USGS の出典表示と再利用条件を確認する
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全球。ただし USGS に登録された M4.5 以上のイベント
temporal_coverage: 2025年の発生時刻。取得後に USGS のイベント値は更新され得る
as_of:
  checked: 2026-10-25
  hf_revision: 028c1c866c0d49764ab19cdee86208577e088f20
contents:
- 地震イベントの点、規模、深さ、時刻、出典ネットワーク
tables:
- name: earthquakes
  read: https://huggingface.co/datasets/yuiseki/usgs-comcat-2025-m45/resolve/028c1c866c0d49764ab19cdee86208577e088f20/parquet/earthquakes.parquet
  grain: USGS ComCat の地震イベント1件
  rows: 8502
  id:
  - event_id
  columns:
  - name: mag
    type: DOUBLE
    meaning: 地震のマグニチュード。尺度の種類も別列で確認する
  - name: time
    type: BIGINT
    meaning: Unix epoch ミリ秒の発生時刻
  - name: depth_km
    type: DOUBLE
    meaning: 深さ、km
---

# USGS ComCat 2025年 M4.5以上

2026-10-25 に固定版の Parquet メタデータを実読し、8,502イベント、`event_id`・`mag`・`time`・`depth_km` と OGC:CRS84 の点を確認した。`time` は epoch ミリ秒であり秒ではない。USGS の[更新型 API](../../usgs-earthquake-catalog.md)を同条件で再照会しても、追加・改訂により同じ件数になる保証はない。イベント数を地域の地震リスクや観測努力を補正した発生率と同一視しない。
