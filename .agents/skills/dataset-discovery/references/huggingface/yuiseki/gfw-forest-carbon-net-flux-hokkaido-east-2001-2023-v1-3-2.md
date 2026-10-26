---
kind: dataset
id: yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2
description: GFW Forest Flux Model v1.3.2の2001〜2023年累積純フラックスを東北海道の約30m格子中心点にしたGeoParquet
url: https://huggingface.co/datasets/yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2
license: CC0-1.0。元Dataverseリリースのdataset metadataがCC0 1.0を宣言
formats:
  - GeoParquet 1.1
crs: OGC:CRS84
spatial_coverage: 東経143〜146度、北緯42〜45度の矩形。値がある森林画素中心のみ。NoDataは行にしない
temporal_coverage: 2001〜2023年の累積純フラックス1時点。年次値ではない
as_of:
  source_release: Dataverse version 1, model v1.3.2, source tile date 2024-04-02
  huggingface_revision: 74d3167e20455e9956bc3d1ccd09d2f40babef4b
contents:
  - 34,516,630個の非NoData画素の累積純フラックス値
  - 原典GeoTIFFタイルと検証マニフェスト
tables:
  - name: net_flux
    read: hf://datasets/yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2@74d3167e20455e9956bc3d1ccd09d2f40babef4b/data/net_flux.parquet
    grain: source 0.00025度格子の非NoDataセル1個
    rows: 34516630
    id:
      - source_grid_row
      - source_grid_col
    join_keys:
      - column: source_grid_row
        type: INTEGER
        meaning: 10度原典タイルのゼロ始まり行番号
        unique: false
        joins: []
      - column: source_grid_col
        type: INTEGER
        meaning: 10度原典タイルのゼロ始まり列番号
        unique: false
        joins: []
    columns:
      - name: net_flux_mg_co2e_ha_2001_2023
        type: FLOAT
        meaning: 2001〜2023年の累積純フラックス、Mg CO2e per hectare。負はsink、正はsource
      - name: geometry
        type: BLOB
        meaning: 原典セルの中心を表すWKB Point。CRS84
---

# GFW Forest Carbon Net Flux v1.3.2 - 東北海道の切り出し

## 出典と版の区別

この切り出しの原典は [GFW Forest Flux Model Dataverse](https://doi.org/10.7910/DVN/TVZVBI) の2024-10-07公開版1、model v1.3.2 (データtileは2024-04-02)。元Dataverse APIのlicense metadataは CC0 1.0 を宣言する。この許諾を確認してからデータを再配布した。科学的な出典は Gibbs et al. (2025), [ESSD論文](https://doi.org/10.5194/essd-17-1217-2025) である。

これは、Global Forest Watch APIの現行版 `v20260327` (2001〜2025年) とは異なる旧版である。API現行版のCC BY 4.0宣言を、このDataverse版の許諾に流用していない。旧版と現行版の値や期間を同一視しない。

## 内容と検証

原典 `50N_140E_net_flux_Mg_CO2e_ha_biomass_soil_forest_extent_2001_23.tif` を[Harvard Dataverse API](https://dataverse.harvard.edu/api/datasets/:persistentId/versions?persistentId=doi%3A10.7910%2FDVN%2FTVZVBI)から取得した。ファイルサイズ90,223,212 bytes、MD5 `e7dc703a183b99b58a0ae953ddefaf8b` はDataverseの公開ファイルmetadataと一致。CRS84、40,000×40,000 Float32、解像度0.00025度、NoDataは0.0。

原典の東経143〜146度・北緯42〜45度を切り出し、34,516,630個の非NoData画素をPoint GeoParquetにした。geometryはセル面ではなくセル中心。値は23年間の累積値であり、年ごとのフラックスとして解釈しない。

出力の各row groupで、原典から再読した全値・行番号・列番号を照合した。出力は34,516,630行、Float32値の範囲は−185.5334〜1,023.3246 Mg CO2e/ha、GeoParquet 1.1、無効ジオメトリ0。公開revisionはfrontmatterに固定した。原典・出力のSHA-256と検証記録はHub上の `source/MANIFEST.json` と `source/VERIFICATION.json` にある。

Hugging Face公開版には原典タイルを同梱した。current GFW API版の取得には引き続きAPIキーが必要で、こちらは別タスクとして扱う。
