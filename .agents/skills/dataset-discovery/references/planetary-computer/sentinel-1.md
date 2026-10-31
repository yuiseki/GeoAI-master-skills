---
kind: dataset
id: planetary-computer-sentinel-1
description: Sentinel-1 の C バンド SAR の、Planetary Computer の 2 つのコレクション。sentinel-1-grd はレーダーの座標のままの強度 (uint16) と注記、sentinel-1-rtc は地形補正した γ0 (UTM、10 m)。撮影ごとの item を探し、匿名の SAS 署名で窓を読む。
url: https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-grd
license: sentinel-1-grd は collection の license が proprietary で、link は Sentinel Data Legal Notice (無償で利用と再配布ができ、「Contains modified Copernicus Sentinel data <年>」の表示を求める)。sentinel-1-rtc は CC BY 4.0
formats:
- Cloud Optimized GeoTIFF (GRD は偏波ごとに uint16、レーダーの行と列、GCP 210 点。RTC は偏波ごとに float32 の線形 γ0)
- XML (GRD の製品の注記、校正の表、熱雑音の表、RFI)
crs: GRD は地図の座標を持たない (GCP が EPSG:4326)。RTC は撮影ごとの UTM (千葉は EPSG:32654)
spatial_coverage: 全世界 (撮影の計画による)
temporal_coverage: 撮影ごと。日本の関東では、同じ軌道で 12 日おき、3 つの軌道を合わせて 5〜6 日おき (2026 年 9〜10 月)
as_of:
  checked: 2026-10-31
contents:
- IW モードの GRD (VV と VH)
- RTC (地形補正と、地形による明るさの補正をした γ0)
tables:
- name: item
  read: POST https://planetarycomputer.microsoft.com/api/stac/v1/search (collections = sentinel-1-grd か sentinel-1-rtc)
  grain: 1 撮影 (衛星 × 軌道 × スライス)
  rows: null
  id:
  - id
---

# Sentinel-1 GRD と RTC (Planetary Computer)

Sentinel-1 の IW モードの GRD と、それを地形補正した RTC の、Planetary Computer の複製。2026-10-31 に、千葉県の北印旛沼の周り (経度 140.10〜140.42、緯度 35.72〜35.89) の 2026 年 9〜10 月の撮影で確かめた。

## 探し方と署名

```sh
curl -X POST https://planetarycomputer.microsoft.com/api/stac/v1/search -H 'Content-Type: application/json' -d '{
  "collections": ["sentinel-1-grd"], "bbox": [140.22, 35.76, 140.28, 35.83],
  "datetime": "2026-09-01T00:00:00Z/2026-10-31T00:00:00Z", "limit": 50}'
```

署名は置き場所のトークンで通る。GRD は `https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel1euwest/s1-grd`、RTC は `https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel1euwestrtc/sentinel1-grd-rtc`。

上の範囲で 2026-09-06〜10-30 の item は、GRD 15、RTC 14 だった。軌道は 39 (上り、08:41 UTC)、141 (上り、08:33 UTC)、46 (下り、20:42 UTC)。RTC には GRD にある 2026-10-06 (軌道 39) が無かった。GRD があっても RTC があるとは限らない。

## GRD のファイル

- item の id は製品名から末尾の 4 文字 (例 `_D023`) を除いたもので、asset の URL のディレクトリは末尾まで付いた名前。
- ファイル名は SAFE の元の名前から付け替えられている。`measurement/iw-vv.tiff`、`annotation/calibration/calibration-iw-vv.xml`、`annotation/calibration/noise-iw-vv.xml`。元の名前は `manifest.safe` にある。
- 製品の注記 (対応表、入射角、画素の間隔を含む) は `annotation/iw-vv.xml` にあるが、asset には無い。asset の `schema-product-vv` は、名前と違って `annotation/rfi/rfi-iw-vv.xml` (RFI の注記) を指している。
- 対応表 (geolocationGridPoint) は 210 点 (行 10 × 列 21)。点ごとに緯度、経度、高さ、入射角を持つ。measurement の GCP も同じ 210 点。
- 熱雑音の表は、距離方向のベクトル 27 本と、副走査幅 (IW1〜IW3) ごとの方位方向のブロック 3 つ (2026-10-06 の VV)。

対応表の高さを楕円体高とみなし、DEM5A にジオイド高 (EGM96、この範囲で 34.589〜37.004 m) を足して位置を合わせると、5 枚の GRD (軌道 39 の 3 枚、軌道 141 の 2 枚) の VV は、WorldCover 2021 の水域に対して行も列も 0.55 画素以内でそろった。ジオイド高を足さない場合は試していない。

## RTC の位置のずれ

上の範囲の RTC 4 枚は、WorldCover 2021 の水域に対して 2 画素 (約 20 m) ほどずれていた。

| 軌道 | 日付 | 行 | 列 |
|---|---|---:|---:|
| 39 | 2026-09-12 | −1.743 | 1.717 |
| 39 | 2026-09-24 | −1.826 | 2.5 |
| 141 | 2026-09-19 | −2.16 | −0.84 |
| 141 | 2026-10-01 | −2.21 | −0.73 |

ずれは相互相関で測り、`a[i] ≈ b[i + s]` の s (a が WorldCover、b が画像)。行は南が正。同じ範囲で自分で処理した GRD は 0.55 画素以内なので、ずれは RTC の側と判断した。他の場所と日付では確かめていない。境界の細かい比較 (浸水の範囲の一致など) に RTC を使うなら、先に位置を確かめる。

RTC の値は線形の γ0 で、NoData は −32768。格子の原点は 10 m の倍数で、軌道 39 と 141 の格子はそろっていた。
