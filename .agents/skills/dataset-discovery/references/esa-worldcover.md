---
kind: dataset
id: esa/worldcover
description: ESA WorldCover。Sentinel-1 と Sentinel-2 から作った、全世界の陸域の 10 m の土地被覆の分類図 (11 クラス)。2020 年 (v100) と 2021 年 (v200) の 2 枚。3 度 × 3 度のタイルの COG (EPSG:4326) で、AWS の公開 S3 から認証なしで読める。
url: https://esa-worldcover.org
license: CC-BY-4.0。地図に載せるときの表示は「© ESA WorldCover project [年] / Contains modified Copernicus Sentinel data ([年]) processed by ESA WorldCover consortium」。出典は年ごとの Zenodo の DOI (2020 v100 は 10.5281/zenodo.5571936、2021 v200 は 10.5281/zenodo.7254221)
formats:
- Cloud Optimized GeoTIFF (uint8、1 band、色表つき)
crs: EPSG:4326
spatial_coverage: 全世界の陸域 (南極を除く、北緯 82.75 度まで)。外洋は NoData (0)。湾や湖の水面は恒久的な水域 (80)
temporal_coverage: 2020 年 (v100) と 2021 年 (v200) の 2 枚。版ごとにアルゴリズムが違う
as_of:
  fetched: 2026-10-16
  map_v200_created: 2022-10-21
contents:
- 土地被覆のクラス (10 樹林、20 低木、30 草地、40 農地、50 市街地、60 裸地・まばらな植生、70 雪と氷、80 恒久的な水域、90 草本の湿地、95 マングローブ、100 コケと地衣類)
- 入力の品質 (InputQuality): Sentinel-1 と Sentinel-2 の観測の数、捨てた Sentinel-2 の観測の割合 (3 band、約 60 m)
tables:
- name: map_v200
  read: https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif
  grain: 1 画素 (1/12000 度、赤道で約 10 m)。1 つのタイルは 3 度 × 3 度で 36,000 × 36,000 画素
  rows: null
  id: []
  columns:
  - name: value
    type: UTINYINT
    meaning: 土地被覆のクラスの番号 (contents の 11 クラス)。0 は NoData
- name: map_v100
  read: https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map/ESA_WorldCover_10m_2020_v100_{tile}_Map.tif
  grain: map_v200 と同じ格子
  rows: null
  id: []
- name: inputquality_v200
  read: https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/inputquality/ESA_WorldCover_10m_2021_v200_{tile}_InputQuality.tif
  grain: 1 画素 (1/2000 度、赤道で約 60 m)
  rows: null
  id: []
- name: grid
  read: https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/esa_worldcover_grid.geojson
  grain: 1 つのタイル (2,651 個)。ll_tile がタイルの名前 (南西の角、N33E135 など)
  rows: 2651
  id:
  - ll_tile
---

# ESA WorldCover (esa-worldcover)

欧州宇宙機関 (ESA) の WorldCover 計画が、Sentinel-1 (レーダー) と Sentinel-2 (光学) から作った、全世界の陸域の 10 m の土地被覆の分類図。2020 年 (アルゴリズム v100) と 2021 年 (v200) の 2 枚がある。分類済みの地図として使う。画素の値からクラスを推定し直すものではない。

## どこから読むか

AWS の公開 S3 (`esa-worldcover`、eu-central-1) から、認証なしで読める。COG なので、HTTP の Range で窓だけ読める (2026-10-16 に 206 が返った)。

```python
import rasterio
from rasterio.windows import from_bounds

u = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
     "v200/2021/map/ESA_WorldCover_10m_2021_v200_N33E135_Map.tif")
with rasterio.open(u) as ds:
    a = ds.read(1, window=from_bounds(135.80, 34.66, 135.85, 34.71, ds.transform))
```

- タイルの名前は南西の角 (`N33E135` は東経 135〜138 度、北緯 33〜36 度)。タイルの一覧は `esa_worldcover_grid.geojson` (2,651 タイル、v100 と v200 で同じ数)。
- 60 度 × 60 度にまとめた zip (`v200/2021/macrotiles/`) と、v100 の VRT (`v100/2020/ESA_WorldCover_10m_2020_v100_Map_AWS.vrt`) もある。
- 利用者マニュアル (PUM) は `v200/2021/docs/WorldCover_PUM_V2.0.pdf`、検証の報告は同じ場所の `WorldCover_PVR_V2.0.pdf`。
- Planetary Computer にも同じデータがある (`esa-worldcover` のコレクション。読み方は planetary-computer/README.md)。

## 測ったこと

2026-10-16 に、v200 のタイル N33E135 を読んだ。

| 項目 | 値 |
|---|---|
| 大きさ | 36,000 × 36,000 画素、uint8、1 band。ブロックは 1,024 × 1,024、overview は 2、4、8、16、32、64 |
| 範囲 | 東経 135〜138 度、北緯 33〜36 度 |
| NoData | 0 (タグの NoData の値) |
| タグ | `legend` (11 クラスの番号と名前)、`license` (CC-BY 4.0)、`product_version` V2.0.0、`time_start` 2021-01-01、`time_end` 2021-12-31、`creation_time` 2022-10-21 |
| 色表 | あり |
| ファイルの大きさ | 36,677,894 バイト |

窓ごとのクラスの数:

| 窓 | 画素 | クラスごとの数 |
|---|---:|---|
| 奈良市の付近 (東経 135.80〜135.85 度、北緯 34.66〜34.71 度) | 600 × 600 | 50 市街地 216,332、10 樹林 98,931、40 農地 23,179、30 草地 13,385、80 水域 4,162、60 裸地 4,011 |
| 大阪湾の岸 (東経 135.30〜135.40 度、北緯 34.45〜34.55 度) | 1,200 × 1,200 | 80 水域 1,088,560、50 市街地 290,133、60 裸地 26,234、30 草地 22,077、10 樹林 10,695、40 農地 2,203、90 湿地 98 |
| 外洋 (東経 137.80〜137.85 度、北緯 33.10〜33.15 度) | 600 × 600 | 0 (NoData) 360,000 |

湾の中の海面は 80 (恒久的な水域) で、外洋は 0 (NoData)。海を同じものとして扱いたいなら、0 と 80 の両方を見る。

## 精度 (PUM V2.0 から、実測ではない)

- 全世界の全体の精度は、2020 v100 が 74.4%、2021 v200 が 76.7 ± 0.5%。
- 大陸ごとの v200 の全体の精度は 72.5% (オセアニア、ユーラシア) から 82.1% (アジア)。
- v100 から v200 で、草地、農地、裸地、恒久的な水域の精度はわずかに上がり、市街地、草本の湿地、コケと地衣類は大きく上がった、と PUM は書いている。クラスごとの値は PUM と検証の報告 (PVR) の表で確かめる (このカードには写していない)。

## 気をつけること

- 経緯度の格子 (EPSG:4326)。画素は赤道で約 10 m 四方だが、緯度が上がるほど東西に縮む (北緯 35 度で東西約 7.6 m)。距離や面積を測るなら、メートルの投影に移す。クラスの地図なので、移すときは最近傍か最頻値で行う (双一次や平均は存在しないクラスを作る)。
- 2020 v100 と 2021 v200 はアルゴリズムが違う。PUM は、2 枚の差の多くは実際の変化ではなくアルゴリズムの違いによる、と書いている。2 枚の差を土地被覆の変化として読まない。
- NoData (0) は外洋など、地図の外。陸の中に 0 があるかは、読んだ窓では見ていない (未確認)。
- クラスの定義は、PUM の表 (LCCS のコードつき) を見る。たとえば 50 市街地は建物と道路などの人工物で、行政の都市の範囲とは別のもの。
- 版は 2 つで、上書きはされない。使ったタイルの名前と版を書く。

## 公開した派生データ

- Hugging Face: [ESA WorldCover Tokyo 2021 100 m class composition](https://huggingface.co/datasets/yuiseki/esa-worldcover-tokyo-2021-100m)。CC BY 4.0 の元データを、同じライセンス表示と必須クレジットを付けて公開。
- v200 のタイル `N33E138` から、東経 139.5〜140.0 度・北緯 35.5〜36.0 度の矩形を切り出し、10 × 10 画素単位の 360,000 ポリゴンに集約。行政界では切り抜いていない。
- 各セルに 11 クラスそれぞれの画素数、NoData 数、最多クラスを格納。EPSG:4326 の経緯度格子なので、セルは北緯 35 度付近で南北約 93 m、東西約 76 m。
- 元タイルと切り出し TIFF、SHA-256 マニフェスト、属性・変換・検証スクリプトも Hub に同梱。変換後の全クラス列を元画像から再計算して照合した。
- 公開時点: 2026-10-25。
