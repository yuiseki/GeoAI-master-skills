---
kind: dataset
id: canada-scanfi-v2
description: カナダの森林構造・樹種・地上部乾燥バイオマスの30m地図、1985〜2025年の5年刻み。
url: https://open.canada.ca/data/en/dataset/07653869-f303-46c2-a04e-9ab479b73cbf
license: Open Government Licence - Canada。出典表示の条件で再配布可
formats:
- GeoTIFF
crs: 未確認 (ファイル自体は未実読)
spatial_coverage: カナダの陸域。北極域の一部では学習資料が乏しい
temporal_coverage: 1985〜2025年の5年刻み。v2
as_of:
  checked: 2026-10-25
contents:
- 樹木の生きた地上部乾燥バイオマス、樹高、樹冠、樹種など
tables:
- name: biomass_2020
  read: https://download-telecharger.services.geo.ca/pub/nrcan_rncan/Forests_Foret/SCANFI/v2/SCANFI_att_biomass_2020_v2_20260119.tif
  grain: 2020年 × 30m画素
  rows: null
  id: []
---

# カナダ SCANFI v2

## 料金、規模、取得経路

- [カナダ政府の目録](https://open.canada.ca/data/en/dataset/07653869-f303-46c2-a04e-9ab479b73cbf)で無料公開。v1ではなくv2を選ぶ。ファイルは政府のHTTPSディレクトリから取得する。政府のオープンデータAPIでは目録検索もできるが、この製品本体は静的なGeoTIFF配布。
- [配布一覧](https://download-telecharger.services.geo.ca/pub/nrcan_rncan/Forests_Foret/SCANFI/v2/)を2026-10-25に確認。AGBの2020年ファイルは6.67 GB、2025年は6.82 GBと表示される。全属性・全年をまとめた容量ではない。画素は未実読。
- 個別ページは [Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada)を指定する。同ライセンスは複製・改変・公開・配布を許し、出典表示を求める。

## Hugging Face への凍結

2020年のバイオマス層1ファイルが約6.67 GBなので候補。複数年・全属性を無計画に複製せず、まず版 `v2`、対象年、元ファイル名・バイト数・チェックサム、政府指定の出典表示とライセンスリンクを揃える。[Hugging Face の公開ストレージ](https://huggingface.co/docs/hub/en/storage-limits)は無料枠でも大容量は best-effort で、容量の保証はない。まだ取得・公開していない。

## 注意

カナダの5年刻みの推定地図であり、5年間に実際に成長した量を同じ画素で直接観測したものではない。配布元は画素ごとの時間の不整合を認め、細かな林分での変化分析には適さないと述べている。広域集計と局所変化を混同しない。
