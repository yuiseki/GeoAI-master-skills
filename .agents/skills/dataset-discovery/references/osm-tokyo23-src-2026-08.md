---
kind: dataset
id: yuiseki/osm-tokyo23-src-2026-08
description: OpenStreetMap の東京 23 区の凍結版 (2026-08-31)。osm2pgsql の 4 つの表を GeoParquet にしたもの。全国版と同じ列で、約 30 分の 1 の大きさ。
url: https://huggingface.co/datasets/yuiseki/osm-tokyo23-src-2026-08
card_revision: 38f7a5f961b6e33343d82a11152e768c37d22664
license: ODbL-1.0。派生物にも同じ条件と出典の表示が及ぶ
formats:
- GeoParquet 1.1
- OSM PBF
crs: EPSG:3857
spatial_coverage: 東京 23 区。区に 1 点でも掛かる way は丸ごと入るので、外接矩形は区の外へ大きく広がる
temporal_coverage: 2026-08-31 の planet ファイルから切り出した 1 時点
as_of:
  snapshot: 2026-08-31
  checked: 2026-10-14
contents:
- 点、線、面、縮尺の小さい地図向けの道路
- 建物の面
- 区の境界の面
tables:
- name: planet_osm_polygon
  read: hf://datasets/yuiseki/osm-tokyo23-src-2026-08/parquet/planet_osm_polygon.parquet
  grain: 1 つの面。マルチポリゴンのリレーションは、負の osm_id を共有する複数の行になる
  rows: 1437105
  id:
  - osm_id
  join_keys:
  - column: osm_id
    type: BIGINT
    meaning: OSM の要素の ID。way は正、リレーションは負
    unique: false
    joins:
    - planet_osm_polygon.osm_id
  no_key:
  - name: code5
    note: 市区町村コードは持たない。区とは、境界の面 (boundary = administrative、admin_level = 7) か、jp-admin-2026-09 の面との空間結合で結ぶ
  columns:
  - name: building
    type: VARCHAR
    meaning: 建物のタグの値 (yes、house など)。建物でない面では NULL
  - name: way
    type: GEOMETRY('EPSG:3857')
    meaning: 面の形。EPSG:3857 (Web メルカトル) のメートル。面積も距離も実際より大きい
  - name: bbox
    type: STRUCT
    meaning: way の外接矩形 (xmin、ymin、xmax、ymax、EPSG:3857 のメートル)。範囲での絞り込みに使う
  - name: tags
    type: VARCHAR
    meaning: 列にならなかったタグの JSON の文字列。(tags->>'キー') と括弧を付けて取り出す
- name: planet_osm_point
  read: hf://datasets/yuiseki/osm-tokyo23-src-2026-08/parquet/planet_osm_point.parquet
  grain: タグを持つ 1 つの節点
  rows: 306642
  id:
  - osm_id
- name: planet_osm_line
  read: hf://datasets/yuiseki/osm-tokyo23-src-2026-08/parquet/planet_osm_line.parquet
  grain: 1 本の線 (道路、線路、川、経路のリレーションなど)
  rows: 347735
  id:
  - osm_id
- name: planet_osm_roads
  read: hf://datasets/yuiseki/osm-tokyo23-src-2026-08/parquet/planet_osm_roads.parquet
  grain: 縮尺の小さい地図に出す道路の線
  rows: 33113
  id:
  - osm_id
---

# OpenStreetMap 東京 23 区の凍結版 (osm-tokyo23-src-2026-08)

OpenStreetMap の 2026-08-31 の planet から、東京 23 区を切り出した凍結版。表は osm2pgsql の既定の 4 つ (`planet_osm_point`、`_line`、`_polygon`、`_roads`) で、列も型も全国版 (`osm-japan-src-2026-08.md`) と同じ。全国版は約 6.5 GB で、範囲で絞らずに読むと時間切れになりやすい。区の中で答えが閉じる問いなら、こちらを読む。

## どこから読むか

Hugging Face の `yuiseki/osm-tokyo23-src-2026-08`。

```
hf://datasets/yuiseki/osm-tokyo23-src-2026-08/parquet/planet_osm_<table>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/osm-tokyo23-src-2026-08>
- 切り出した PBF (`tokyo23-260831.osm.pbf`) と、切り出しに使った境界 (`tokyo23_osm_boundary.geojson`) もある。

| 表 | 行数 | 大きさ |
|---|---:|---:|
| `planet_osm_polygon` | 1,437,105 | 151 MB |
| `planet_osm_line` | 347,735 | |
| `planet_osm_point` | 306,642 | |
| `planet_osm_roads` | 33,113 | |

4 表で 208 MB。行数は 2026-10-14 に実測した (DuckDB 1.5.6)。面の表を全部数えて 19 秒 (Hugging Face から、CPU 8)。

## 中身

| 項目 | 値 |
|---|---|
| 建物 | `building` が NULL でない面が 1,361,121 行、osm_id は 1,361,074 種類。負の osm_id (マルチポリゴン) の行が 1,848 |
| 区の境界 | `boundary = 'administrative'` かつ `admin_level = '7'` で名前が「区」で終わる面が 24 行、名前は 23 種類 (1 つの区が 2 行) |
| 座標系 | `way` と `bbox` は EPSG:3857。DuckDB 1.5 は `way` を `GEOMETRY('EPSG:3857')` として読む |
| 範囲 | 区に 1 点でも掛かる way は丸ごと入る (`complete_ways`)。小笠原への航路のように、区のはるか外まで伸びる線がある |
| ライセンス | ODbL 1.0。出典の表示 (© OpenStreetMap contributors) と、同じ条件での共有が派生物に及ぶ |

## 気をつけること

- 面積と距離を 3857 のまま測らない。台東区の中の建物の面積は、区で切って EPSG:6677 に直すと 3.731 km²、3857 のまま測ると 5.673 km² (2026-10-14。区の面は `jp-admin-2026-09` の code5 13106。全国版で同じ計算をしても 3.731 km² で、同じ時点の切り出し)。
- マルチポリゴンは、同じ負の `osm_id` の複数の行になる。数えるとき、測るときは、先に `osm_id` でまとめる。
- 範囲で絞るときは `bbox` の列に定数で条件を書く。台東区の範囲で、建物の候補は 63,482 行 (全国版と同じ)。この表は小さいので、絞らずに読んでも 20 秒ほどで終わる。
- 区の外の地物も入っている。区ごとに数えるなら、区の面との空間結合で区の中に絞る。外接矩形で絞るだけでは、隣の市の地物が入る。
- 区の面は 2 つある。OSM の境界 (この表の中) と、国勢調査の小地域から作った `jp-admin-2026-09` の面。人口と結ぶなら、人口と同じ出所の `jp-admin-2026-09` の面を使う。OSM の境界は公式の境界ではない。
- タグの取り出しは `->>` で、括弧が要る (`(tags->>'operator:en') = 'East Japan Railway'`)。
- 建物の用途は、ほとんど書かれていない。`building` の値は `yes` が 68.5% (932,031)、`house` 21.5%、`apartments` 5.3%、`residential` 2.2%、`commercial` 0.5% (2026-10-14)。住宅だけに絞ると 3 割ほどしか残らず、住む人の分布の代わりにはしにくい。
- 「カフェはいくつ」は、点だけ数えるか、建物として描かれた面も数えるかで変わる (カードは世田谷区で 258 と 279 と書く。この数は測り直していない)。

## ほかのデータとの結合

- 区の人口や面積は `jp-admin-2026-09` (区の code5 は 13101 から 13123)。座標系を揃えてから空間結合する (EPSG:4612 の面を EPSG:3857 に直すときは `always_xy := true`)。
- 全国の OSM は `osm-japan-src-2026-08` (同じ planet の同じ日付)。区の中の答えは、どちらで数えても一致するはず。
