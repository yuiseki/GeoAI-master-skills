---
kind: dataset
id: nasa-gedi-l4b-v2-1
description: GEDI L4B v2.1 の全球1kmセルの平均地上部バイオマス密度推定値。
url: https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2299
license: NASA Earthdata の無制限公開。出典と DOI を表示する
formats:
- GeoTIFF
crs: EASE-Grid 2.0 (EPSGコードと画素はファイル未実読)
spatial_coverage: おおむね南緯52度〜北緯52度。観測と品質で有効セルが欠ける
temporal_coverage: 2019-04-18〜2023-03-16をまとめた1時点推定。年次地図ではない
as_of:
  checked: 2026-10-25
contents:
- セルの平均AGB密度、標準誤差、標本数、品質フラグなど
tables:
- name: gridded
  read: https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2299
  grain: 約1kmの格子セル。複数の指標が別のGeoTIFF
  rows: null
  id: []
  columns:
  - name: MU
    type: Float32
    meaning: 森林・非森林を含むセル全体の平均AGB密度推定値 (Mg/ha)
  - name: SE
    type: Float32
    meaning: 平均AGB密度の標準誤差 (Mg/ha)
---

# NASA GEDI L4B v2.1

## 料金、規模、取得経路

- [ORNL DAAC のGEDI一覧](https://daac.ornl.gov/cgi-bin/dataset_lister.pl?p=40%2F)に約2.2 GBとある。データは無料で無制限公開、取得には Earthdata Login が必要。画素は未実読。
- 2026-10-26にDOIからCMR collection concept ID `C2792577683-ORNL_CLOUD` を特定した。匿名のCMR検索では10個のTIFF granuleがあり、日本周辺bbox `122,20,154,46` でも10個すべてと交差する。データTIFFのprotected URLは匿名HEADで403。CMRのpublic `.sha256` sidecarは匿名取得でき、例としてSE rasterのSHA-256を取得できた。データ本体の取得はEarthdata Login後に行う。
- [旧v2製品ガイド](https://daac.ornl.gov/GEDI/guides/GEDI_L4B_Gridded_Biomass.html)に GeoTIFF の指標、欠損、品質フラグを記載。ただし、このガイドの対象期間は2021年までで、ここで採用するv2.1の期間は[製品ページ](https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2299)に従う。L4A の予測をセルで統計的に推定したものである。[CMR API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html)でメタデータ・ファイルを検索できる。API取得の実動作は未確認。
- [製品ページ](https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2299)の DOI は `10.3334/ORNLDAAC/2299`。凍結時にはファイル名とチェックサムも保存する。

## Hugging Face への凍結

全製品が約2.2 GBなので、数GB級に該当する有力候補。ただし先に Earthdata Login で取得して全ファイルの実容量とチェックサムを測り、再配布時はデータ出典と DOI、版、期間、元ファイルと改変の有無を明記する。[Hugging Face の公開ストレージ](https://huggingface.co/docs/hub/en/storage-limits)は無料枠でも大容量は best-effort で、容量の保証はない。まだ取得・公開していない。

## 注意

年次時系列ではない。MU は森林だけでなく非森林を含むセル全体の平均で、森林部分だけの平均と取り違えない。品質フラグと SE、観測の無いセルを同時に見る。
