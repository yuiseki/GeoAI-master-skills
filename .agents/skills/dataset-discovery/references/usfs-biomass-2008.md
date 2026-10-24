---
kind: dataset
id: usfs-biomass-2008
description: USDA Forest Serviceが公開する2008年の米国森林バイオマス推定地図。
url: https://data.fs.usda.gov/geodata/rastergateway/biomass/
license: 配布ページに個別の明示ライセンスが見つからない。再配布判断は保留
formats:
- ZIP内のラスタとメタデータ (ラスタ形式は未実読)
crs: 未確認
spatial_coverage: 米国本土48州、アラスカ、プエルトリコ。ハワイは無い
temporal_coverage: 2008年版。年次系列ではない
as_of:
  checked: 2026-10-25
contents:
- 森林バイオマス、誤差、森林・非森林の推定
tables:
- name: conus_biomass
  read: https://data.fs.usda.gov/geodata/rastergateway/biomass/conus_forest_biomass.zip
  grain: 250m画素 (配布ページのモデル解像度)
  rows: null
  id: []
---

# USDA Forest Service 2008年森林バイオマス

## 料金、規模、取得経路

- [公式配布ページ](https://data.fs.usda.gov/geodata/rastergateway/biomass/)からZIPを無料でダウンロードできる。専用APIは見つからず、静的なHTTP配布。実ダウンロード・ラスタ実読はしていない。
- 配布ページにはCONUSのバイオマスZIPが142 MB、誤差が90 MB、相対誤差が153 MB、アラスカのバイオマスが12 MBとある。ページ上の丸めた表示で、実バイト数は未確認。モデルの空間解像度は250m。
- 同じページに2018年の別製品 [FIA BIGMAP](https://data.fs.usda.gov/geodata/rastergateway/bigmap/)へのリンクもある。こちらは米国本土の30m、総量と327樹種の推定であり、2008年地図と同じ時系列の次年版としてつながない。
- この製品の個別ライセンス・再配布規定は公式配布ページで確認できていない。米国政府機関の公開物というだけで他由来の内容も含めて無条件に再配布可能とは断定しない。

## Hugging Face への凍結

CONUSのAGB本体は約142 MBで、数GB級には当たらない。許諾の個別確認も残るため、現時点では凍結を提案しない。

## 注意

古い、粗い地図である。2018年 BIGMAP と比較するなら、入力資料・モデル・格子が異なることを先に検討する。
