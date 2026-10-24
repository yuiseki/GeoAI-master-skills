---
kind: dataset
id: nasa-gedi-l4a-v3
description: GEDI L4A v3 のレーザーフットプリントごとの地上部バイオマス密度推定値。
url: https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2508
license: NASA Earthdata の無制限公開。出典と DOI を表示する
formats:
- HDF5
crs: WGS84の経緯度 (フットプリント位置。ファイル自体は未実読)
spatial_coverage: 南緯約51.6度〜北緯約51.6度の軌道上。面を隙間なく覆わない
temporal_coverage: 2019-04-04から。2023-03〜2024-04は観測停止。2026-10-25時点の目録は2025-07-10まで
as_of:
  checked: 2026-10-25
contents:
- 約25mフットプリントのAGB密度予測、予測標準誤差、品質フラグ、位置
tables:
- name: shots
  read: https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2508
  grain: 1つのレーザー照射フットプリント
  rows: null
  id:
  - shot_number
  columns:
  - name: agbd
    type: 浮動小数点
    meaning: 現地実測ではなく波形からの地上部バイオマス密度予測 (Mg/ha)
---

# NASA GEDI L4A v3

## 料金、規模、取得経路

- [ORNL DAAC の製品ページ](https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2508)は無制限のオープン共有と表示し、ダウンロードには Earthdata Login が必要。データ使用料はない。
- [製品ガイド](https://daac.ornl.gov/GEDI/guides/GEDI_L4A_AGB_Density_V3.html)によると、軌道ごとのHDF5を大量に配る。v3の合計バイト数は未確認。参考として、別版の v2.1 は研究チームが約14 TBを取得したと[ORNL DAAC の資料](https://daac.ornl.gov/VEGETATION/guides/GEDI_HighQuality_Shots_Rasters.html)にあるが、v3の容量として転記しない。
- 検索・範囲指定は [NASA CMR Search API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html) の granules でできる。ファイル本体は ORNL DAAC 経由。API 検索と認証付きダウンロードの実動作は未確認。

## Hugging Face への凍結

全球の軌道ファイル一式は対象外。地域と期間を限定し、品質フラグ・元のgranule ID・取得日を保持した派生物なら検討できる。どのフットプリントが入ったかと欠けたかを測る。元データは無制限公開だが、再配布時にも DOI と NASA/ORNL DAAC を明記する。地域抽出後の容量は未実測。

## 注意

LiDARが直接量ったのは波形であり、L4A の AGBD はモデルによる予測値。現地実測の正解ラベルとして扱わない。軌道・品質による標本選択、予測誤差、他製品の学習にGEDIが使われている可能性を確認する。
