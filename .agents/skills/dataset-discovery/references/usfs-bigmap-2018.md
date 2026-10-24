---
kind: dataset
id: usfs-bigmap-2018
description: USDA Forest Service FIA BIGMAPの2018年の米国本土30m地上部バイオマス地図。総量と327樹種を区別する。
url: https://data.fs.usda.gov/geodata/rastergateway/bigmap/
license: 配布ページに個別の明示ライセンスが見つからない。再配布判断は保留
formats:
- ZIP内のGeoTIFFとメタデータ
crs: 未確認
spatial_coverage: 米国本土48州
temporal_coverage: 2014〜2018年の衛星画像と調査地から作成した2018年版
as_of:
  checked: 2026-10-25
contents:
- 樹木地上部バイオマスの総量と327樹種別の推定値
tables:
- name: total_agb
  read: https://data.fs.usda.gov/geodata/rastergateway/bigmap/
  grain: 2018年版の30m画素。配布ページのTotalを選ぶ
  rows: null
  id: []
---

# USDA Forest Service FIA BIGMAP 2018

## 料金、規模、取得経路

- [公式ページ](https://data.fs.usda.gov/geodata/rastergateway/bigmap/)で無料ダウンロード。ZIP内のGeoTIFF、ワールドファイル、メタデータ、検証ファイルを配る。総量と327樹種の個別ファイルがある。
- 2014〜2018年の Landsat 8 画像と212,978箇所の FIA 調査地を用いて30m画素に推定した製品。総量ファイル・全製品の配布容量はページ上では確認できず、未実測。静的なHTTP配布で、専用APIは見つからない。
- 個別の明示ライセンスや再配布条件は公式配布ページに見つからなかった。配布が無料であることと、HFへの再配布許可を区別する。

## Hugging Face への凍結

総量ファイルの容量と再配布条件を確認するまで保留。元製品には SHA-256 チェックサム案内があるので、取得した場合はそれと照合する。

## 注意

2008年の250m製品とは、解像度だけでなく入力年・モデルも違う。2枚を単純に引いて2008〜2018年の変化としない。値の単位は配布ページでは tons/acre とされ、Mg/ha と混ぜない。
