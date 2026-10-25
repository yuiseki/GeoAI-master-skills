---
kind: dataset
id: yuiseki/koppen-geiger-east-asia-1991-2020
description: Köppen-Geiger 1991-2020年の約1km全球分類図から東アジア範囲を切り出し、同じクラスの連結領域を GeoParquet にした。
url: https://huggingface.co/datasets/yuiseki/koppen-geiger-east-asia-1991-2020
source_url: https://doi.org/10.6084/m9.figshare.21789074.v2
license: CC BY 4.0 (Figshare v2 のメタデータで確認)
formats:
- GeoTIFF ZIP
- GeoParquet
- NetCDF ZIP
crs: EPSG:4326
spatial_coverage: 東経122〜154度、北緯20〜48度の範囲。日本を中心に東アジアの一部
temporal_coverage: 気候の基準期間と将来シナリオはファイルごと。2023 は論文・製品の名称で、単年観測ではない
as_of:
  checked: 2026-10-25
  version: v2
  source_raster: 1991_2020/koppen_geiger_0p00833333.tif
  raster_resolution_degrees: 0.008333333333333
contents:
- Köppen-Geiger 気候分類
- 基準期間と将来シナリオ別の地図および関連気候変数
tables:
- name: east_asia_polygons
  read: hf://datasets/yuiseki/koppen-geiger-east-asia-1991-2020/parquet/koppen_geiger_east_asia_1991_2020.parquet
  grain: 4近傍で連結した同じ気候区分のラスタセル領域。13,480ポリゴンが2,255,263分類セルを表す
  rows: 13480
  id: []
  no_key:
  - name: fid
    note: 出力時に採番した地物番号で、別のポリゴン化処理との間で安定するIDではない
  columns:
  - name: class_code
    type: INTEGER
    meaning: 原典凡例の1〜30の気候区分コード
  - name: class_symbol
    type: VARCHAR
    meaning: Köppen-Geiger記号 (例 Cfa)
  - name: geometry
    type: geometry:EPSG:4326
    meaning: 同じクラスの隣接ラスタセルを連結した面
---

# Köppen-Geiger 気候区分

[Figshare API の記事 21789074](https://api.figshare.com/v2/articles/21789074)は、2026-10-25 の照会で DOI `10.6084/m9.figshare.21789074.v2`、CC BY 4.0 と応答した。`koppen_geiger_tif.zip` は130,618,411バイト、MD5は `7fc2f5a15d4f5fe0ce59c9a9b502aa09`。アーカイブは2026年1月の計算誤差修正を含む。内部には1901〜2099年の期間や将来シナリオ別 GeoTIFF が73ファイルある。別の `koppen_geiger_nc.zip` と気候変数アーカイブは未実読。

## GeoParquet 派生配布

[Hugging Face](https://huggingface.co/datasets/yuiseki/koppen-geiger-east-asia-1991-2020)に1991〜2020年の約1km分類図から切り出した東アジア範囲を公開した。範囲は東経122〜154度、北緯20〜48度で、日本に加えて近隣の中国・朝鮮半島・ロシアの一部を含む。元ラスタは43,200×21,600画素、0.00833333度、EPSG:4326、0をNoDataとしている。範囲内は切り出し実測3,840×3,360画素で、2,255,263分類セル、10,647,137 NoDataセル、15種類の区分だった。

GDAL で同じ区分の4近傍セルを連結して13,480ポリゴンにした。EPSG:4326のGeoParquetは無効・nullジオメトリ0件。生成ポリゴンをラスタへ戻すと、元の切り出しとの画素差は0。クラスコードと名称は原典の `legend.txt` に従う。分類図は1991〜2020年の気候区分で、2023年は公開版の名称であり、2023年の気象観測ではない。

[製作者の案内](https://www.gloh2o.org/koppen/)は現行版を V3 と呼ぶ。ここで固定した Figshare v2 と混同しない。気候区分は期間平均やモデルから作る分類で、単年の実際の天候でも観測点の気温でもない。比較するときは同じ版・基準期間・シナリオをそろえる。
