---
kind: dataset
id: ibtracs-v04r01
description: NOAA/NCEI が複数機関の熱帯低気圧の経路を統合した IBTrACS v04r01。観測点の表。
url: https://www.ncei.noaa.gov/products/international-best-track-archive
license: IBTrACS Terms of Use。full and open access と open distribution。商用利用は WMO Resolution 40 を指針とし、データセットの引用を求める。CC0 と断定しない
formats:
- CSV
- NetCDF
- Shapefile
crs: CSV の LAT と LON は北緯・東経の度。Shapefile の .prj はこの調査では未実読
spatial_coverage: 全球の熱帯低気圧。ただし観測密度と機関の分布は年代・海域で異なる
temporal_coverage: 1840年代以降の統合記録。実読した last3years CSV は 2023-01-04 から 2026-10-22
as_of:
  fetched: 2026-10-25
  version: v04r01
  sample_sha256: a05c71f5c3d431fb68f529796301640bc5e60ab8bef808d9877bbcb14fc79b0c
contents:
- storm ID、UTC 観測時刻、緯度経度、海域、風速、中心気圧、機関別の報告値
tables:
- name: last3years_observations
  read: https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.last3years.list.v04r01.csv
  grain: 1つの storm の1観測時刻。実読したファイルでは SID と ISO_TIME の組に重複なし
  rows: 24554
  id:
  - SID
  - ISO_TIME
  columns:
  - name: LAT
    type: VARCHAR
    meaning: 緯度の度。実読サンプルでは空欄なし
  - name: LON
    type: VARCHAR
    meaning: 経度の度。実読サンプルでは空欄なし
  - name: WMO_WIND
    type: VARCHAR
    meaning: WMO 機関の報告風速、ノット。実読サンプルでは15,486行が空欄
  - name: WMO_PRES
    type: VARCHAR
    meaning: WMO 機関の中心気圧、mb。実読サンプルでは14,469行が空欄
- name: since1980_observations
  read: https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.since1980.list.v04r01.csv
  grain: storm と観測時刻の組。全件の一意性は未実測
  rows: null
  id: []
---

# IBTrACS v04r01

[NOAA の公式ページ](https://www.ncei.noaa.gov/products/international-best-track-archive)から取得する。2026-10-25 に `last3years` CSV を実読した。11,637,676 バイト、174 列、24,554 データ行だった。CSV の先頭は列名行、その次は単位行であり、単位行を観測に数えない。`SID + ISO_TIME` の重複は0、LAT と LON の空欄は0、WMO_WIND の空欄は15,486、WMO_PRES の空欄は14,469。ISO_TIME の範囲は 2023-01-04 18:00:00 から 2026-10-22 00:00:00。`since1980` は HEAD で 145,156,717 バイトを確認したが中身は未実読。

風速の定義は機関ごとに違う。[列の公式説明](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf)によると観測間隔は多くが6時間で、一部機関は3時間の点も含む。添付レポートの「通常3時間間隔」は訂正する。CSV の欠損は空欄。NetCDF や Shapefile の `-9999.0` と混同しない。座標を点にするなら LON、LAT の順に扱い、時刻は UTC とする。古い年代の記録と近年の記録を、そのまま発生率の変化と読まない。

v04r01 の同じファイル名は週内にも更新され得る。上記 SHA-256 は取得した `last3years` の実バイト列で、`since1980` のハッシュではない。再現分析では取得日時、URL、ハッシュを記録し、スナップショットを固定する。[公式利用条件](https://www.ncei.noaa.gov/products/international-best-track-archive)は公開配布と引用を案内するが、単純な CC0 表記には置き換えない。
