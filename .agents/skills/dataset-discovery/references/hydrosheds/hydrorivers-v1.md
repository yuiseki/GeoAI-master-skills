---
kind: dataset
id: hydrorivers-v1
description: HydroRIVERS v1.0 の河川区間と下流への接続。Greenland の Shapefile を実読。
url: https://www.hydrosheds.org/products/hydrorivers
license: HydroSHEDS v1 License Agreement。科学・教育・商用利用は無償。原データの stand-alone 再配布は不可、出典表示と派生物の条件あり
formats:
- Shapefile ZIP
crs: WGS84 経緯度。実読した .prj は GCS_WGS_1984
spatial_coverage: 全球の抽出対象河川。実読した範囲は Greenland のみ
temporal_coverage: v1.0 の河川網。日々の流量観測ではない
as_of:
  fetched: 2026-10-25
contents:
- 河川区間、下流への接続、推定流量、流域レベル12との共有 ID
tables:
- name: greenland_reaches
  read: https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_gr_shp.zip
  grain: 1つの河川区間の線
  rows: 137088
  id:
  - HYRIV_ID
  join_keys:
  - column: HYBAS_L12
    type: BIGINT
    meaning: HydroBASINS レベル12の流域 ID
    unique: false
    joins:
    - hydrobasins-v1:greenland_level12.HYBAS_ID
  columns:
  - name: NEXT_DOWN
    type: BIGINT
    meaning: 下流側の河川区間 ID。0 は接続なしの例がある
  - name: DIS_AV_CMS
    type: DOUBLE
    meaning: 長期平均流量の推定値。実測流量ではない
---

# HydroRIVERS v1.0

2026-10-25 に Greenland の公式 ZIP を実読した。9,377,170バイト、137,088 Polyline、bbox は経度 -72.665〜-12.302、緯度59.802〜83.590。ZIP SHA-256 は `436bd112718f14ada7d7cda0182426b14f2561328f772b5e7398ecac1cb96dbc`。`.prj` は `GCS_WGS_1984`。DBF の列は `HYRIV_ID`、`NEXT_DOWN`、`MAIN_RIV`、`LENGTH_KM`、`DIST_DN_KM`、`DIST_UP_KM`、`CATCH_SKM`、`UPLAND_SKM`、`ENDORHEIC`、`DIS_AV_CMS`、`ORD_STRA`、`ORD_CLAS`、`ORD_FLOW`、`HYBAS_L12`。

`HYBAS_L12` は16,722種類で0は無く、137,088行すべてが同じ Greenland の HydroBASINS レベル12 `HYBAS_ID` に一致した。複数区間が同じ流域に入るため一意な結合ではない。`HYRIV_ID` は137,088件で一意。`NEXT_DOWN` は6,201行が0、残り130,887行は同じファイル内の `HYRIV_ID` に一致した。全列の欠損・無効ジオメトリは未検査であり、解析時に確認する。河川の抽出閾値と推定流量は[製品ページ](https://www.hydrosheds.org/products/hydrorivers)に従う。原データの再配布は[ライセンス](https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf)の条件で制限される。
