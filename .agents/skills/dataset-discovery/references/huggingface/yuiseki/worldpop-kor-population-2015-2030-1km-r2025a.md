---
kind: dataset
id: yuiseki/worldpop-kor-population-2015-2030-1km-r2025a
description: WorldPop R2025A v1 の韓国向け年次人口推計16枚を、元の30秒角セルごとの GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a
license: HF の派生版は ODbL 1.0。WorldPop の韓国コレクションは CC BY 4.0 表示だが、入力由来によって ODbL 条件があり得る
formats:
- GeoParquet 1.1
crs: EPSG:4326
spatial_coverage: 韓国向け元格子の範囲、東経約124.61〜130.94度・北緯約33.11〜38.62度
temporal_coverage: 2015〜2030年の年次人口推計。R2025A v1 のうち将来年は予測で、現地観測ではない
as_of:
  checked: 2026-10-25
  hf_revision: d22e0e74fed47919ca6f6f9aaa60febeaa3ae850
contents:
- 年別のセル人口推計と元画素の面。全期間 NoData のセルは省略
tables:
- name: population
  read: https://huggingface.co/datasets/yuiseki/worldpop-kor-population-2015-2030-1km-r2025a/resolve/d22e0e74fed47919ca6f6f9aaa60febeaa3ae850/data/population.parquet
  grain: 30秒角の元ラスタ格子1セル。1kmは赤道付近の公称値
  rows: 130927
  id:
  - grid_row
  - grid_col
  columns:
  - name: population_2020
    type: FLOAT
    meaning: 2020年のセル人口推計。NULL は NoData、0は有効値
    missing: NULL 470行
  - name: population_2030
    type: FLOAT
    meaning: 2030年のセル人口予測。人口の現地実測ではない
    missing: NULL 0行
---

# WorldPop 韓国の年次人口格子

2026-10-25 に上記 SHA の Parquet を実読した。130,927行、19列、EPSG:4326 の有効な `POLYGON` が130,927件。`grid_row` と `grid_col` の組は全行で一意。2020年の NULL は470行、有効な0は250行。2030年の NULL は0行。GeoParquet は12,909,344バイト。年別列の NULL 件数は同年の NoData で異なるため、年をまたぐ比較では対象セルを揃える。

出典は [WorldPop の韓国向け STAC コレクション](https://api.stac.worldpop.org/collections/KOR)の R2025A v1。元 GeoTIFF は HF に再配布されず、出典 URL とハッシュを記した manifest がある。WorldPop の[製品ページ](https://hub.worldpop.org/geodata/summary?id=80036)は R2025A を更新され得る alpha 版とし、一般には CC BY 4.0、OSM や Microsoft の建物・道路由来の製品には ODbL が適用されると説明する。この韓国版でどの入力が使われたかを個別に確定できないため、HF の変換版は保守的に ODbL 1.0 を表示している。人口はモデル推計で、国勢調査の1セルごとの実測ではない。変換版の再配布時は HF の `LICENSE` と元製品の条件を確認する。
