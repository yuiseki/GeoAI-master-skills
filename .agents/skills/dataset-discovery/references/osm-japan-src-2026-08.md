---
kind: dataset
id: yuiseki/osm-japan-src-2026-08
description: OpenStreetMap の 2026-08-31 の planet から切り出した日本の固定スナップショット。osm2pgsql のテーブルを GeoParquet にしたもの。
url: https://huggingface.co/datasets/yuiseki/osm-japan-src-2026-08
card_revision: 9a9b4a77e89e28a66bf15781644a16b63501f622
license: ODbL-1.0
formats:
- OSM PBF
- GeoParquet 1.1
- GeoJSON
crs: EPSG:3857
spatial_coverage: 日本全国。complete_ways のため、境界の外へ延びる地物も含む
temporal_coverage: 2026-08-31
as_of:
  planet: 2026-08-31
contents:
- OSM の点
- 線
- 面
- 道路
- 切り出しの境界
tables:
- name: planet_osm_point
  read: hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_point.parquet
  grain: OSM の 1 つのノード (タグのあるもの)
  rows: 3720141
  id:
  - osm_id
  no_key:
  - name: code5
    note: 市区町村コードは持たない。市区町村とは、点を面に入れる空間結合で結ぶ
  - name: relation_id
    note: リレーションの ID の列は無い。マルチポリゴンは負の osm_id
- name: planet_osm_line
  read: hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_line.parquet
  grain: OSM の 1 つのウェイ (道路、鉄道、川など)。ウェイやリレーションが複数行に分かれることがある
  rows: 12259617
  id: []
  join_keys:
  - column: osm_id
    type: BIGINT
    meaning: OSM のウェイの ID。12,259,617 行に対し、異なる値は 12,209,517 (実測)
    unique: false
- name: planet_osm_polygon
  read: hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_polygon.parquet
  grain: 1 つの面 (建物、土地利用、行政区域など)。マルチポリゴンは、同じ osm_id (負の値) の複数行になる
  rows: 33281956
  id: []
  join_keys:
  - column: osm_id
    type: BIGINT
    meaning: OSM のウェイの ID。マルチポリゴンでは負の値で、行が重なる
    unique: false
  columns:
  - name: admin_level
    type: VARCHAR
    meaning: 行政区域の階層 (2 が国、4 が都道府県、7 が市区町村と東京の特別区)。boundary が administrative の行で意味を持つ
  - name: way
    type: geometry:EPSG:3857
    meaning: 面 (EPSG:3857。メートルだが、実際の長さとは緯度で違う)
  - name: tags
    type: VARCHAR
    meaning: osm2pgsql が列にしなかったタグ。JSON の文字列
  - name: bbox
    type: STRUCT
    meaning: way の外接矩形 (EPSG:3857)。範囲での絞り込みに使う
- name: planet_osm_roads
  read: hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_roads.parquet
  grain: 縮尺の小さい地図に出す道路の線
  rows: 762255
  id: []
  join_keys:
  - column: osm_id
    type: BIGINT
    meaning: OSM のウェイの ID。762,255 行に対し、異なる値は 757,067 (実測)
    unique: false
---

# OpenStreetMap 日本 (osm-japan-src-2026-08)

2026-08-31 の OpenStreetMap の planet ファイルから切り出した、日本全国の凍結版。osm2pgsql のテーブル (`planet_osm_point`、`planet_osm_line`、`planet_osm_polygon`、`planet_osm_roads`) を GeoParquet にしたもの。
分析では、POI の数や密度、道路や建物の特徴量、行政界に入る点の集計に使う。日付を固定してあるので、同じ問いに同じ答えが出る。

## どこから読むか

Hugging Face の `yuiseki/osm-japan-src-2026-08`。

```
hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_<point|line|polygon|roads>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/osm-japan-src-2026-08>
- 元の pbf (2.8 GB)、輪郭の GeoJSON、出典の記録 (`provenance.yaml`) も同じデータセットにある。
- 姉妹の `osm-tokyo23-src-2026-08` は東京 23 区だけで、同じ形式。

## 粒度と範囲

行数は 2026-10-13 に実測した (Parquet のメタデータ)。

| テーブル | 行数 | 型 | 1 行 |
|---|---:|---|---|
| `planet_osm_point` | 3,720,141 | 点 | 1 つの点 (ノード) |
| `planet_osm_line` | 12,259,617 | 線 | 1 本の線 (道路、鉄道、川など) |
| `planet_osm_polygon` | 33,281,956 | 面 | 1 つの面 (建物、土地利用、行政界など) |
| `planet_osm_roads` | 762,255 | 線 | 地図の縮尺の小さいほうに出る道路 |

| 項目 | 値 |
|---|---|
| CRS | `way` は `GEOMETRY('EPSG:3857')` (Web メルカトル。メートルだが実際の長さではない) |
| 範囲 | 日本全国の外枠。ただし ways を完全な形で残すので、小笠原の航路のように、日本の外へ伸びる線も入る (カードによる) |
| 時点 | 2026-08-31 |
| ライセンス | ODbL 1.0。出典の表示と、同じ条件での共有が、派生物にも及ぶ |
| 大きさ | 全部で約 6.5 GB。`polygon` だけで約 4.2 GB。全部を読まず、`bbox` で絞る |

列は osm2pgsql の既定のとおり。`tags` は JSON の文字列 (PostGIS の hstore ではない)。`bbox` 列 (`xmin`、`ymin`、`xmax`、`ymax`、EPSG:3857 のメートル) が、最後に足してある。

## 気をつけること

- 長さと面積を 3857 のまま測ると、緯度で誤差が違う。カードの値で、3857 の 1 m は、沖縄 (北緯 26 度) で実際の約 1.11 m、東京 (36 度) で約 1.24 m、稚内 (45 度) で約 1.41 m。面積はその 2 乗で、北端では約 2 倍になる。全国で順位を付けるなら、距離は `ST_Transform` で等積か測地線に直してから測る。
- 範囲で絞るときは `bbox` の列を使う。ファイルはヒルベルト曲線の順に並べてあり、`bbox` の統計で行グループを飛ばせる。タグだけの条件 (`amenity = 'cafe'` など) では、飛ばせない。東京駅の周囲 1 km で、`planet_osm_polygon` は 204 の行グループのうち 15 だけを読む (カードによる)。下の例は、`amenity = 'cafe'` の点が 55 件 (2026-10-13 実測)。

```sql
select osm_id, name from 'hf://datasets/yuiseki/osm-japan-src-2026-08/parquet/planet_osm_point.parquet'
where bbox.xmin <= 15559415 and bbox.xmax >= 15558190
  and bbox.ymin <= 4257460  and bbox.ymax >= 4256226
  and amenity = 'cafe';
```

- タグの取り出しは `->>` で、括弧が要る。`(tags->>'operator:en') = 'East Japan Railway'`。
- マルチポリゴンは、同じ `osm_id` (負の値) の複数行になる。測る前に集約する。
- 行政区域は `planet_osm_polygon` の中にある (`boundary = 'administrative'`、`admin_level`)。`admin_level` は、国が 2、都道府県が 4、市区町村と東京の特別区が 7。別の表は無い。
- `ST_Distance_Sphere` は点しか受けず、経度と緯度の順に注意する。メートルで測りたいときは、投影してから測る。
- OSM の行政区域は公式の境界ではない。市区町村の人口を出すなら、人口のある `jp-admin-2026-09` の面を使う。

## ほかのデータとの結合

- 座標系の名前が `EPSG:3857`。ほかのデータ (`EPSG:4612`、`EPSG:6668`、`OGC:CRS84`) と空間結合するなら、経度、緯度に直してから、座標系の名前を揃える。DuckDB は座標系の名前が違うと、そのままの結合を拒む。
- 直すときは `always_xy := true` を付ける。`ST_Transform(way, 'EPSG:4326')` は、東京駅の近くの点を `POINT (35.677 139.770)` と、緯度、経度の順で返した。`ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)` は `POINT (139.770 35.677)` で、経度、緯度の順 (2026-10-13 実測)。順が逆の点は、エラーにならずに、別の場所を指す。
