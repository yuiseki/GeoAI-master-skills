---
kind: dataset
id: yuiseki/worldpop-idn-population-2015-2030-1km-r2025a
description: インドネシアの WorldPop R2025A v1 年次人口推計16年分を、1 kmソース格子のGeoParquetにした固定版。
url: https://huggingface.co/datasets/yuiseki/worldpop-idn-population-2015-2030-1km-r2025a
license: GeoParquetデータベースはODbL-1.0 (保守的適用)。WorldPop IDN STAC collectionは原典GeoTIFFをCC-BY-4.0と宣言
formats:
- GeoParquet 1.1
- GeoTIFF (原典URLとSHA-256のみ。Hubでは再配布しない)
crs: EPSG:4326
spatial_coverage: インドネシアの有効なソース画素。東経95.0333322〜141.0166654度、南緯10.9916663度〜北緯6.0833336度
temporal_coverage: 2015〜2025年のモデル推計、2026〜2030年の予測。R2025A v1
as_of:
  release: R2025A
  version: v1
  checked: 2026-10-25
contents:
- 2015〜2030年の1 kmソース画素ごとの推計人口 (Float32)
- 948,911行。原典GeoTIFF 16枚から変換したGeoParquet
source:
  stac_collection: https://api.stac.worldpop.org/collections/IDN
  worldpop_terms: https://hub.worldpop.org/geodata/summary?id=80036
  doi: https://doi.org/10.5258/SOTON/WP00845
  converted_dataset: https://huggingface.co/datasets/yuiseki/worldpop-idn-population-2015-2030-1km-r2025a
license_review:
  source_declaration: WorldPop IDN STAC collection declares CC-BY-4.0 for its source rasters.
  exception: WorldPop says data derived from OpenStreetMap, Microsoft Building Footprints, or Microsoft Roads Detection are ODbL and adaptations must remain ODbL.
  treatment: Release materials describe building-footprint inputs but do not identify Indonesia-specific inputs. To respect a potentially applicable share-alike condition, the converted GeoParquet database is released under ODbL-1.0. Source GeoTIFFs are not mirrored. Their URLs, ETags and SHA-256 values are retained in the Hub manifest.
  odbl: https://opendatacommons.org/licenses/odbl/1-0/
tables:
- name: population
  read: hf://datasets/yuiseki/worldpop-idn-population-2015-2030-1km-r2025a@b70415daf2035015bbc72ffb5f89baf47ba4d08d/data/population.parquet
  grain: 1つのWorldPopソース格子画素
  rows: 948911
  id:
  - grid_row
  - grid_col
  columns:
  - name: geometry
    type: geometry:EPSG:4326
    meaning: ソース画素の矩形フットプリント
  - name: grid_row
    type: INTEGER
    meaning: 原典ラスタの行番号
  - name: grid_col
    type: INTEGER
    meaning: 原典ラスタの列番号
  - name: population_2015
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2016
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2017
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2018
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2019
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2020
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2021
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2022
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2023
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2024
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2025
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2026
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2027
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2028
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2029
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
  - name: population_2030
    type: FLOAT
    meaning: 画素ごとの推計人口。原典NoDataはNULL、原典の数値0は0を維持
---

# WorldPop Indonesia: 1 km人口推計

[WorldPop IDN STAC collection](https://api.stac.worldpop.org/collections/IDN)は `CC-BY-4.0` を宣言する。collection と R2025A v1 の16 itemを照合し、全GeoTIFFを取得してSTAC記載の寸法・CRS・NoDataと突合した。16原典の合計は88,711,091バイト。原典名、取得URL、サイズ、ETag、SHA-256とメタデータはHubの `source/MANIFEST.json` に記録した。配布元はRange要求を無視して全体を返す。原典は検証のためにローカル取得したが、Hubでは再配布していない。

WorldPopの[Population Counts製品条件](https://hub.worldpop.org/geodata/summary?id=80036)は通常のデータをCC BY 4.0とする一方、OpenStreetMap、Microsoft Building Footprints、Microsoft Roads Detection由来の製品はODbLとし、改変物もODbLにするよう定める。R2025Aの説明には建物フットプリント入力の使用があるが、インドネシア個別の入力由来は特定できなかった。ライセンス遵守を優先し、派生GeoParquetにはODbL 1.0を適用した。これは不確かな入力由来を考慮した保守的な扱いであり、STAC collectionが原典に宣言するCC BY 4.0を変更するものではない。

推奨引用: Bondarenko M. et al. (2025), *The spatial distribution of population in 2015-2030 at a resolution of 30 arc (approximately 1km at the equator) R2025A version v1*, Global Demographic Data Project, WorldPop, University of Southampton, [doi:10.5258/SOTON/WP00845](https://doi.org/10.5258/SOTON/WP00845)。

## 実測

原典は全て5,525×2,051、EPSG:4326、Float32、0.0083333333度格子、NoData `-99999`。元の画素値と画素ポリゴンを変換し、再投影・再標本化はしていない。GeoParquetは948,911行・19列で、`(grid_row, grid_col)` は一意、無効ジオメトリは0件。全期間を通じてNoDataだった10,382,864画素は除き、年ごとの欠損はNULLにした。16年各列の有効セル件数、NULL件数、人口合計、最小値、最大値は、原典GeoTIFFからの再計算と全て一致した。検証結果はHubの `source/VERIFICATION.json` にある。

| 年 | 有効画素 | 人口推計合計 |
|---:|---:|---:|
| 2015 | 946,352 | 260,363,854 |
| 2020 | 947,160 | 273,748,193 |
| 2025 | 947,990 | 284,622,217 |
| 2030 | 948,911 | 294,942,394 |

画素の幅と高さは度で定義されるため、等面積ではない。人口密度や距離を計算する場合は画素面積と緯度を考慮する。2015〜2025年もモデル推計で、2026〜2030年は予測である。年の差を直接観測された人口変化と見なさず、版変更による過去年値の改訂可能性も考慮する。WorldPopは差別、搾取、監視など、個人や脆弱な集団への危害を目的とした利用を認めない。このGeoParquetは独立に変換したものでWorldPopの推奨・承認を示さない。
