---
kind: dataset
id: gfw-biomass-stock-2000
description: GFWの旧Woods Hole Research Center由来の2000年の木本地上部バイオマス密度。
url: https://data-api.globalforestwatch.org/dataset/whrc_aboveground_woody_biomass_stock_2000
license: 個別データのライセンスはAPIのメタデータでnull。再配布の可否は未確認
formats:
- GeoTIFF (API経由。元ファイルの形式は未確認)
crs: 未確認
spatial_coverage: 全球と紹介されるが、有効画素の範囲は未実読
temporal_coverage: 2000年のストック推定
as_of:
  checked: 2026-10-25
contents:
- 木本の地上部バイオマス密度 (Mg/ha) の推定
tables:
- name: stock_2000
  read: https://data-api.globalforestwatch.org/dataset/whrc_aboveground_woody_biomass_stock_2000/v1.4
  grain: 2000年のラスタ画素
  rows: null
  id: []
---

# GFW/WHRC 木本バイオマスストック 2000

## 料金、規模、取得経路

- [GFW Data API の目録](https://data-api.globalforestwatch.org/dataset/whrc_aboveground_woody_biomass_stock_2000)は公開で `is_downloadable=true`、版 `v1.4` を返した。APIを無償で閲覧できたが、ラスタ本体の容量とダウンロードに必要な認証は未確認。
- API の当該データセットの `license` は `null`。GFWの純フラックスとはデータ提供者も利用許諾も別であり、他の GFW データの CC BY 4.0 を継承したとみなさない。
- [GFW Data API](https://data-api.globalforestwatch.org/docs)で版を固定し、AOIの値やダウンロードを要求できる。APIキーの要否は実動作未確認。

## Hugging Face への凍結

再配布許可と実容量が分かるまで保留。必要なら元の提供者のライセンスを個別に確認する。

## 注意

こちらは2000年時点のストックで、上記の2001〜2025年の純フラックスとは別。AGB密度と炭素密度を同じ単位として扱わない。
