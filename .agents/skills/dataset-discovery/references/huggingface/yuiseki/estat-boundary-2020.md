---
kind: dataset
id: yuiseki/estat-boundary-2020
description: "2020年国勢調査の町丁・字等ポリゴンと人口・世帯。"
url: https://huggingface.co/datasets/yuiseki/estat-boundary-2020
license: "CC BY 4.0。e-Stat と令和2年国勢調査を出典表示し、加工を明記する"
formats:
- GeoParquet
crs: "JGD2000 経度・緯度 (EPSG:4612)。GeoParquet CRS metadata 未確認"
spatial_coverage: "日本全国の2020年国勢調査小地域ポリゴン"
temporal_coverage: "2020-10-01 国勢調査。元資料は2022年公開"
as_of:
  checked: 2026-10-26
  hf_revision: 823195c40e1055e2c1b3c0a635369f8c82b6c3fb
contents:
- 町丁・字ポリゴン、人口、世帯数
tables:
- name: r2ka01
  read: https://huggingface.co/datasets/yuiseki/estat-boundary-2020/resolve/823195c40e1055e2c1b3c0a635369f8c82b6c3fb/parquet/r2ka01.parquet
  grain: 国勢調査の町丁・字小地域1件
  rows: 22967
  id:
  - KEY_CODE
---

# 2020年国勢調査 小地域境界

232,019ポリゴン、47都道府県別の Parquet。人口・世帯数、町丁字名、代表点、面積等を含む。座標値は JGD2000 の経度・緯度だが、GeoParquet CRS metadata は未確認のため変換前に元 CRS を明示する。`KEY_CODE` は文字列キー。`PREF` と `CITY` で自治体コードの先頭部分を構成する。住所ベースレジストリと小地域名を結ぶには正規化が要り、完全な共通キーではない。属性は文字列型で秘匿記号もある。CC BY 4.0 の出典と加工を明記する。
