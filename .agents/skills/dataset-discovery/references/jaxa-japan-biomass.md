---
kind: dataset
id: jaxa-japan-biomass
description: JAXAが公開する日本全国の森林地上部バイオマス、炭素蓄積、材積、樹高の約10m地図。
url: https://www.eorc.jaxa.jp/ALOS/jp/dataset/biomassmap/japan_biomassmap_j.htm
license: JAXAの個別利用条件。登録後に無償利用可。商用は問い合わせ。再配布は未確認
formats:
- GeoTIFF
crs: WGS84の経緯度 (配布元の記載。ファイル自体は未実読)
spatial_coverage: 日本全国の森林。非森林部分の値の表現は未実読
temporal_coverage: 入力観測の対象期間は2016〜2022年。1枚の地図であり年次系列ではない
as_of:
  checked: 2026-10-25
contents:
- AGB、材積、広葉樹・針葉樹の炭素密度、樹高
tables:
- name: agb_tiles
  read: https://www.eorc.jaxa.jp/ALOS/jp/dataset/biomassmap/data/index_j.htm
  grain: 約10m画素。1度×1度のタイルを90枚
  rows: null
  id: []
  columns:
  - name: AGB
    type: Int16
    meaning: 地上部バイオマス密度 (Mg/ha)
---

# JAXA 日本の森林地上部バイオマス地図

## 料金、規模、取得経路

- [JAXA製品ページ](https://www.eorc.jaxa.jp/ALOS/jp/dataset/biomassmap/japan_biomassmap_j.htm)は利用条件への同意の上で無償とする。ダウンロードにはメールアドレス等による登録が必要。商用利用は窓口への問い合わせを求める。
- 1プロダクト90タイル。1タイルは12,000×12,000画素。AGB は Int16 なので、単純計算した非圧縮の画素本体は1タイル288,000,000バイト、90枚で25.92 GB。これは実配布ファイルの容量ではない。圧縮後のファイルサイズはログインを要するため未確認。AGB以外にも4種ある。
- ウェブのタイル一覧から取得する方式。公表された検索APIや匿名の大量取得APIは未確認。
- [利用条件へのリンク](https://earth.jaxa.jp/policy/ja.html)は製品ページにあるが、原本の再配布許可を確認できていない。登録が必要なデータを同意なく第三者向けに複製しない。

## Hugging Face への凍結

再配布許可を確認するまで対象外。元URL、必要タイル、登録と取得の日、版を研究の来歴として記録する。

## 注意

2016〜2022年は入力データの対象期間で、毎年のバイオマス地図がある意味ではない。AGBは乾燥重量、Carbon_Stock_BF/NFは炭素密度で単位も対象も違う。画像・航空機ライダーなどから学習したモデル推定値である。
