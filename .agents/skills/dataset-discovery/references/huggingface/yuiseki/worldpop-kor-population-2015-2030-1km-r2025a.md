---
kind: dataset
id: worldpop/korea-population-2015-2030-1km-r2025a
description: 韓国の2015〜2030年の年次人口推計、1 km格子16年分をGeoParquet化した凍結版。
url: https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a
license: GeoParquetデータベースはODbL-1.0 (保守的適用)。WorldPop Korea STACは元GeoTIFFをCC-BY-4.0と宣言
formats:
- GeoParquet
- GeoTIFF (原典URLのみ。再配布なし)
crs: EPSG:4326
spatial_coverage: 韓国 (124.608332E–130.941665E, 33.108334N–38.616667N)
temporal_coverage: 推計年2015〜2030、R2025A v1
as_of:
  release: R2025A
  version: v1
  checked: 2026-10-25
contents:
- 2015〜2030年の画素別総人口推計 (Float32)
- GeoParquet: 130,927画素、欠損は年列ごとにNULL
- 全年NoDataの371,433画素は省略
source:
  stac_collection: https://api.stac.worldpop.org/collections/KOR
  worldpop_terms: https://hub.worldpop.org/geodata/summary?id=80036
  release_statement: https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/Global2_2015_2030_R2025A_v1_Release_Statement.pdf
  converted_dataset: https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a
license_review:
  source_declaration: WorldPop KOR STAC collection declares CC-BY-4.0 for the source collection.
  exception: WorldPop says datasets derived from OpenStreetMap, Microsoft Building Footprints, or Microsoft Roads Detection are ODbL; adaptations must remain ODbL.
  treatment: Global2 release materials describe building-footprint inputs but do not identify the inputs used specifically for Korea. To honor a potentially applicable Share-Alike condition, the converted GeoParquet database is offered under ODbL-1.0. The source rasters are not redistributed.
  odbl: https://opendatacommons.org/licenses/odbl/1-0/
tables:
- name: population
  read: https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a/resolve/d22e0e74fed47919ca6f6f9aaa60febeaa3ae850/data/population.parquet
  grain: 1つのWorldPopソース格子画素
  rows: 130927
  id:
  - grid_row
  - grid_col
  columns:
  - name: geometry
    type: Polygon
    meaning: ソース画素の矩形フットプリント、EPSG:4326
  - name: grid_row
    type: integer
    meaning: 原典ラスタの行番号
  - name: grid_col
    type: integer
    meaning: 原典ラスタの列番号
  - name: population_2015 through population_2030
    type: float32, nullable
    meaning: 画素ごとの推計人数。原典NoDataはNULL、数値の0は維持
---

# WorldPop Korea: 1 km人口推計

## ライセンスと再配布

WorldPopのKorea STAC collectionは `CC-BY-4.0` と宣言し、元GeoTIFFの再配布を許可する表示です。一方、WorldPopの製品条件は、OpenStreetMap、Microsoft Building Footprints、Microsoft Roads Detection由来のデータをODbLとし、派生データの配布にもODbLを求めています。Global2の公表資料には建物フットプリントの利用が書かれていますが、韓国の推計に使った入力は特定できませんでした。

ライセンス遵守を優先し、GeoParquet化したデータベースにはODbL-1.0を適用しました。これは条件が及ぶ可能性を考慮した保守的な扱いです。原典GeoTIFFとこの変換物を同一ライセンスとは記載せず、原典ラスタはHugging Faceリポジトリに再配布していません。原典リンク・item ID・取得ファイルのチェックサムはHub内の `source/MANIFEST.json` に記録しています。変換物はWorldPop公式製品ではなく、WorldPopはこの変換を推奨・承認していません。

- [WorldPop Korea STAC collection](https://api.stac.worldpop.org/collections/KOR)
- [WorldPopの製品条件とODbL例外](https://hub.worldpop.org/geodata/summary?id=80036)
- [WorldPop Global2 R2025A v1リリース声明](https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/Global2_2015_2030_R2025A_v1_Release_Statement.pdf)
- [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [Hugging Face frozen GeoParquet](https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a)

WorldPop推奨引用: Bondarenko M. et al. (2025), *Constrained estimates of 2015–2030 total number of people per grid square at a resolution of 30 arc (approximately 1 km at the equator), R2025A version v1*, Global Demographic Data Project, WorldPop, University of Southampton, [doi:10.5258/SOTON/WP00840](https://doi.org/10.5258/SOTON/WP00840).

## 実測

- 原典item: `kor_pop_<year>_CN_1km_R2025A_UA_v1`、2015〜2030の16年分
- 各年760×661、EPSG:4326、0.0083333333度間隔、NoData `-99999`
- 各年を再投影・再標本化せず、画素ポリゴンと年列へ変換
- 130,927行、複合キー `(grid_row, grid_col)` は一意、無効ジオメトリ0
- 全年でNoDataの371,433セルは除外。年ごとのNoDataはNULL、実値の0は0
- 各年の有効セル数・合計値は原典GeoTIFFを再読して変換後と一致することを確認
- WorldPop製品はR2025A alpha版であり、今後更新される可能性がある
- WorldPopは、個人や脆弱な集団への差別、搾取、監視、その他の危害に人口データを使わないよう求めている
- 2025年以降の値は観測済み国勢調査値ではなく推計
