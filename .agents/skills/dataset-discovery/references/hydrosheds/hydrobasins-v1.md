---
kind: dataset
id: hydrobasins-v1
description: HydroBASINS v1.c の階層的な流域面。Greenland のレベル6と12を実読。
url: https://www.hydrosheds.org/products/hydrobasins
license: HydroSHEDS v1 License Agreement。科学・教育・商用利用は無償。原データの stand-alone 再配布は不可、出典表示と派生物の条件あり
formats:
- Shapefile ZIP
crs: WGS84 経緯度。実読した .prj は GCS_WGS_1984
spatial_coverage: 世界の陸域。実読した範囲は Greenland のみ
temporal_coverage: v1.c の流域境界。年次変化の観測ではない
as_of:
  fetched: 2026-10-25
contents:
- 流域面、Pfafstetter code、下流流域 ID、上流面積など
tables:
- name: greenland_level12
  read: https://data.hydrosheds.org/file/hydrobasins/standard/hybas_gr_lev12_v1c.zip
  grain: レベル12の1流域面
  rows: 16990
  id:
  - HYBAS_ID
  columns:
  - name: NEXT_DOWN
    type: BIGINT
    meaning: 下流側の流域 ID。0 は下流の流域 ID が無い例がある
- name: greenland_level06
  read: https://data.hydrosheds.org/file/hydrobasins/standard/hybas_gr_lev06_v1c.zip
  grain: レベル6の1流域面
  rows: 302
  id:
  - HYBAS_ID
---

# HydroBASINS v1.c

2026-10-25 に公式 ZIP を実読した。Greenland レベル6は1,690,787バイト、302 Polygon、bbox は経度 -73.001〜-11.349、緯度59.742〜83.626。ZIP SHA-256 は `4c8119b4a1135df6f9a4a7bfe2a569497c249cb51fd3bec256105b7114f53f34`。レベル12は9,219,124バイト、16,990 Polygon、ZIP SHA-256 は `9c4d1c06e6ad39da6462f7a610de569e5112018c9a3b7fbb3598bfabeb87abd7`。両方の Shapefile に `.prj` があり `GCS_WGS_1984` だった。

確認した DBF 列は `HYBAS_ID`、`NEXT_DOWN`、`NEXT_SINK`、`MAIN_BAS`、`DIST_SINK`、`DIST_MAIN`、`SUB_AREA`、`UP_AREA`、`PFAF_ID`、`ENDO`、`COAST`、`ORDER`、`SORT`。レベル12では `HYBAS_ID` が16,990件で一意。河川網との結合はレベル12で行う。面の妥当性と全列の欠損は未検査であり、分析時に確認する。[製品ページ](https://www.hydrosheds.org/products/hydrobasins)と[ライセンス原文](https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf)を参照し、元の地物を再ホストしない。
