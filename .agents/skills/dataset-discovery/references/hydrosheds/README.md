---
kind: catalog
id: hydrosheds
description: HydroSHEDS の流域・河川網などの目録。v1 と v2、製品別の許諾を分けて扱う。
url: https://www.hydrosheds.org/
access: 製品ページで地域と level を選び、必要な ZIP を公式配布元から取得する
license: 製品ごとに異なる。HydroBASINS・HydroRIVERS v1 は HydroSHEDS v1 License Agreement。原データを stand-alone で再配布しない
crs: 製品ごと。実読した v1 の Greenland Shapefile は WGS84 経緯度
spatial_coverage: 世界の河川・陸域。小流域・小河川には抽出閾値がある
temporal_coverage: 製品版ごと。v1 と v2 を同じ版として混ぜない
as_of:
  checked: 2026-10-25
contents:
- HydroBASINS v1 の階層的な流域面
- HydroRIVERS v1 の河川区間と下流への接続
---

# HydroSHEDS

まず [HydroBASINS](hydrobasins-v1.md) と [HydroRIVERS](hydrorivers-v1.md) を個別に読む。両製品の v1 は河川区間と流域を共有 ID で結べるが、実読した河川の `HYBAS_L12` はレベル12の `HYBAS_ID` を指す。レベル6へ同じ整数で直接結ばない。

[公式 FAQ](https://www.hydrosheds.org/faq)は製品ごとにライセンスが異なると明記する。v1 の利用は科学・教育・商用で無償でも、[v1 License Agreement](https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf)には原データの stand-alone 再配布に制約がある。ここでは地物の GeoParquet 変換版を Hugging Face に置かない。v2 を使う際は版・範囲・利用条件を改めて調べる。
