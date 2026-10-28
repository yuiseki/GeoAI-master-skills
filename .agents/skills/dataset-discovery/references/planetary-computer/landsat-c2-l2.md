---
kind: dataset
id: planetary-computer-landsat-c2-l2
description: USGS Landsat Collection 2 Level-2 (Landsat 4、5、7、8、9) の地表面反射率と地表面温度の 30 m の COG。Planetary Computer の STAC から撮影ごとの item を探し、匿名の SAS 署名で窓を読む。
url: https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2
license: Public Domain (USGS。collection の license の link が https://www.usgs.gov/core-science-systems/hdds/data-policy)。出典の表示は求められていないが、「Landsat data courtesy of the U.S. Geological Survey」と書く
formats:
- Cloud Optimized GeoTIFF (帯ごとに 1 ファイル、内部タイル 256 × 256、overview 2〜64)
- MTL (txt、xml、json)
crs: 撮影ごとの UTM (item の proj:epsg。東北は EPSG:32654 など)
spatial_coverage: 全世界 (WRS-2 の path/row)
temporal_coverage: 1982-08-22〜 (Landsat 5 TM は 1984〜2011 年)
as_of:
  checked: 2026-10-28
contents:
- 地表面反射率 (Landsat 4〜5 TM は blue、green、red、nir08、swir16、swir22)
- 地表面温度 (lwir) とその途中の値
- 画素の品質 qa_pixel、飽和と欠落 qa_radsat
tables:
- name: item
  read: POST https://planetarycomputer.microsoft.com/api/stac/v1/search (collections = landsat-c2-l2、query platform = landsat-5 など)
  grain: 1 撮影 (WRS-2 の path/row × 日時) × Tier
  rows: null
  id:
  - id
---

# Landsat Collection 2 Level-2 (Planetary Computer)

USGS の Landsat Collection 2 Level-2 の、Planetary Computer の複製。撮影ごとに 1 つの STAC item があり、帯ごとの COG を Range で読む。署名の仕方は [README](README.md) にある (コレクション名のトークン `https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2` で 206)。トークンの期限は約 1 時間なので、長い抽出では取り直す。

## 探し方

```sh
curl -X POST https://planetarycomputer.microsoft.com/api/stac/v1/search -H 'Content-Type: application/json' -d '{
  "collections": ["landsat-c2-l2"],
  "intersects": {"type": "Point", "coordinates": [140.5, 39.7]},
  "datetime": "1999-04-01/1999-08-31",
  "query": {"platform": {"eq": "landsat-5"}}, "limit": 100}'
```

- item の ID は USGS の product ID (`LT05_L2SP_107032_19990810_02_T1` = Landsat 5 TM、L2SP、path 107、row 032、撮影日、Collection 02、Tier 1)。
- `landsat:collection_category` が T1 か T2。T2 は幾何の精度が T1 の基準に届かない撮影。USGS は時系列に T1 を勧める。
- `eo:cloud_cover` と `landsat:cloud_cover_land` は scene 全体の雲の割合。地点の周りが晴れているかは qa_pixel で見る。

2026-10-28 に、東北と北海道 渡島半島のブナの 102 地点 (Dryad、北緯 37.8〜42.7 度、東経 139.7〜142.0 度) に重なる Landsat 5 の item を数えた: 1989〜2008 年の 4〜5 月と 7〜8 月で 1,394 件 (T1 915、T2 479)、path/row は 106/032〜109/031 の 13 通り。秋田付近の 1 点では、1 年の 4〜8 月に 26〜27 件 (隣の path と row の重なりを含む)。

## 地表面反射率の尺度と QA (Landsat 4〜7)

- 反射率 = DN × 0.0000275 − 0.2。fill は DN 0。有効範囲は DN 7273〜43636 (USGS の FAQ「How do I use a scale factor with Landsat Level-2 science products?」と、item の `raster:bands`)。
- qa_pixel のビット (item の `classification:bitfields` と同じ): 0 fill、1 dilated cloud、3 cloud、4 cloud shadow、5 snow、6 clear (cloud と dilated cloud が立っていない)、7 water、8〜9 cloud の確信度、10〜11 shadow の確信度、12〜13 snow の確信度。bit 2 (cirrus) と 14〜15 は Landsat 8〜9 だけ。qa_pixel の nodata は 1。
- qa_radsat: bit 0〜6 が帯 1〜7 の飽和、bit 9 が dropped pixel。
- 晴れた森林の画素の qa_pixel は 5440 (clear と、3 つの確信度が low) になる。

## Hugging Face への凍結

- `yuiseki/` に、地点の周りの抽出表として凍結する (撮影の画像そのものは複製しない)。凍結した版は huggingface/yuiseki/ の reference を見る。

## 注意

- 隣り合う row の scene は同じ日に重なるので、地点 × 撮影日で重複する。どちらを使うか決めておく。
- Landsat 5 と Landsat 7 の反射率は、センサーの違いを調和しないと混ぜられない。
- `platform` で絞ると、Landsat 4 TM (1982〜1993 年) は入らない。
