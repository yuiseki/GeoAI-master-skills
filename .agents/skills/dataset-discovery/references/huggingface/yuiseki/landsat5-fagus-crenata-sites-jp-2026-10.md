---
kind: dataset
id: yuiseki/landsat5-fagus-crenata-sites-jp-2026-10
description: Landsat 5 TM Collection 2 Level-2 の地表面反射率と QA を、Dryad のブナの豊凶の 102 地点から 300 m 以内で撮影ごとに抜き出した表。1989〜2008 年の 4〜5 月と 7〜8 月。豊凶の値は含まない
url: https://huggingface.co/datasets/yuiseki/landsat5-fagus-crenata-sites-jp-2026-10
license: 画像は USGS の public domain (Landsat data courtesy of the U.S. Geological Survey)。地点の位置は Dryad の CC0 1.0。カードの表示は license other
formats:
- Parquet
crs: 位置は経緯度 (sites)。画素の dx、dy は各撮影の UTM の m
spatial_coverage: 東北 98 地点と北海道 渡島半島 4 地点の周り 300 m
temporal_coverage: 1989-04-06〜2008-08-27 の撮影 (4〜5 月と 7〜8 月だけ)
as_of:
  source_snapshot: 2026-10-28
  huggingface_revision: 939ee55fa7ed45afc7b0a6cec83387c645622d3a
contents:
- 地点 × 撮影の QA の画素数、有効な画素の反射率の中央値、NDVI と NDMI の中央値 (23,455 行)
- 地点 × 撮影 × 画素の生の DN と QA (7,365,354 行)
- STAC の item の一覧 (1,394 件、T1 915、T2 479)
tables:
- name: site_acquisitions
  read: hf://datasets/yuiseki/landsat5-fagus-crenata-sites-jp-2026-10@939ee55fa7ed45afc7b0a6cec83387c645622d3a/data/site_acquisitions.parquet
  grain: 1 地点 × 1 撮影 (STAC の item)
  rows: 23455
  id:
  - ID
  - item_id
  join_keys:
  - column: ID
    type: BIGINT
    meaning: Dryad の地点の ID
    unique: false
    joins:
    - fagus-crenata-masting-jp-2026-06:study_sites.ID
- name: pixels
  read: hf://datasets/yuiseki/landsat5-fagus-crenata-sites-jp-2026-10@939ee55fa7ed45afc7b0a6cec83387c645622d3a/data/pixels.parquet
  grain: 1 地点 × 1 撮影 × 中心が地点から 300 m 以内の 1 画素
  rows: 7365354
  id:
  - item_id
  - ID
  - dx
  - dy
---

# Landsat 5 TM のブナの 102 地点の周りの抽出表

[beech-masting-satellite-proxy](https://github.com/yuiseki/GeoAI-master-skills/tree/main/projects/beech-masting-satellite-proxy) のために作った。豊凶の値 (目的変数) を含まない衛星の観測の表で、[fagus-crenata-masting-jp-2026-06](fagus-crenata-masting-jp-2026-06.md) の `ID` で結ぶ。原典は [Planetary Computer の Landsat C2 L2](../../../references/planetary-computer/landsat-c2-l2.md)。

## 作り方 (2026-10-28)

- 102 地点に重なる Landsat 5 の item を、1989〜2008 年の 4〜5 月 (681 件) と 7〜8 月 (713 件) で全て読んだ。雲の割合で item を捨てていない。T2 も含め、`tier` 列で分かる。
- 撮影の UTM の格子で、中心が地点から 300 m 以内の画素 (310〜318、平均 314) の red、nir08、swir16、qa_pixel、qa_radsat を保存した。
- 除いた画素: qa_pixel の fill、dilated cloud、cloud、cloud shadow、snow。qa_radsat の帯 3〜5 の飽和と dropped pixel。3 つの帯のどれかの DN が 7273〜43636 の外。水は数えるが除かない。理由ごとの数は重なる。
- NDVI と NDMI は画素ごとに計算して、有効な画素の中央値。有効な画素が 0 なら NULL (0 にしない)。
- 隣の row の重なりで同じ地点 × 日が 2 回あるときは、`kept_for_site_date` が有効な画素の多い方 (同数なら item の ID の小さい方) に立つ。20,673 行が残る。
- `PROCESSING.json` に定数、QA の規則、ソフトウェアの版 (rasterio 1.5.2、GDAL 3.12.2)、データのファイルの sha256 がある。抽出のコード `scripts/landsat.py` も置いてある。

## 検証

- 上げた版を読み直し、全てのファイルの sha256 が手元と一致した。上げた画素から 23,455 行の値を計算し直し、全ての列が一致した。
- 23,455 行のうち 75.4% は有効な画素が 0 (雲か雪)。有効な画素が 157 以上の 4,160 行の NDVI の中央値は 0.794。

## 注意

- 300 m の円は森林の範囲ではない。道、伐採地、ほかの樹種が入りうる。
- Landsat 5 だけ。Landsat 7 と混ぜるにはセンサーの調和が要る。
