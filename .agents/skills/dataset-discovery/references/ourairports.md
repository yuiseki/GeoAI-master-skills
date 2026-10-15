---
kind: dataset
id: yuiseki/ourairports-2026-08
description: 全世界の空港、ヘリポート、飛行場の点と、IATA と ICAO のコード、滑走路、無線施設。2026-08-31 の凍結。
url: https://huggingface.co/datasets/yuiseki/ourairports-2026-08
license: public domain
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全世界。米国が 38%
temporal_coverage: 2026-08-31。各行がいつ更新されたかは分からない
as_of:
  snapshot: 2026-08-31
contents:
- 空港と飛行場の点
- 滑走路
- 無線施設
- 国と地域の表
- 周波数
- コメント
tables:
- name: airports
  read: hf://datasets/yuiseki/ourairports-2026-08/parquet/airports.parquet
  grain: 1 か所 (空港、ヘリポート、飛行場など)。ほとんどは小さな飛行場とヘリポートで、旅客の空港ではない
  rows: 86002
  id:
  - id
  - ident
  join_keys:
  - column: iso_country
    type: VARCHAR
    meaning: ISO の 2 文字の国コード
    unique: false
    joins:
    - natural-earth:ne_10m_admin_0_countries.ISO_A2_EH
    note: 247 種のうち 237 種が一致する。XP と ZZ は国でない
  - column: ident
    type: VARCHAR
    meaning: 空港の識別子 (ICAO に近い。IATA ではない)
    joins:
    - runways.airport_ident
    - airport_frequencies.airport_ident
  no_key:
  - name: osm_id
    note: OpenStreetMap とは ID で結べない
  columns:
  - name: type
    type: VARCHAR
    meaning: 種類。small_airport、heliport、closed、medium_airport、large_airport など
  - name: scheduled_service
    type: VARCHAR
    meaning: 定期便があるか (yes か no)
  - name: iata_code
    type: VARCHAR
    meaning: IATA コード。利用者の入力で、IATA の登録簿とは照合されていない
    missing: NULL は IATA コードが無いこと (86,002 行のうち 76,945 行)
  - name: geometry
    type: geometry:OGC:CRS84
    meaning: 点 (OGC:CRS84。経度、緯度)
- name: runways
  read: hf://datasets/yuiseki/ourairports-2026-08/parquet/runways.parquet
  grain: 1 本の滑走路
  rows: 48203
  id:
  - id
  join_keys:
  - column: airport_ident
    type: VARCHAR
    meaning: airports.ident を指す
    unique: false
    joins:
    - airports.ident
- name: airport_frequencies
  read: hf://datasets/yuiseki/ourairports-2026-08/parquet/airport_frequencies.parquet
  grain: 1 つの空港の 1 つの周波数
  rows: 30343
  id:
  - id
  join_keys:
  - column: airport_ident
    type: VARCHAR
    meaning: airports.ident を指す
    unique: false
    joins:
    - airports.ident
- name: navaids
  read: hf://datasets/yuiseki/ourairports-2026-08/parquet/navaids.parquet
  grain: 1 つの無線施設
  rows: 11008
  id: []
- name: countries
  read: hf://datasets/yuiseki/ourairports-2026-08/parquet/countries.parquet
  grain: 1 つの国
  rows: 249
  id: []
---

# OurAirports

全世界の空港、ヘリポート、飛行場の点と、IATA / ICAO コード、定期便の有無、滑走路、無線施設。
分析では、点データの密度や最近傍距離の特徴量、施設配置の候補地、空港を結ぶネットワークの節点に使う。

## どこから読むか

Hugging Face の `yuiseki/ourairports-2026-08`。2026-08-31 の `davidmegginson/ourairports-data` のコミットを凍結したもの。配布元は毎晩同じ URL で上書きするので、配布元を直接読むと再現できない。

```
hf://datasets/yuiseki/ourairports-2026-08/parquet/<table>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/ourairports-2026-08>

| テーブル | 行数 | 1 行 |
|---|---:|---|
| `airports` | 86,002 | 1 か所。点の `geometry` を持つ |
| `runways` | 48,203 | 1 本の滑走路。両端の座標 |
| `navaids` | 11,008 | 1 つの無線施設。点の `geometry` |
| `countries` | 249 | 国 |
| `regions` | 3,987 | 第 1 階層の地域。ISO 3166-2 風のコード |
| `airport_frequencies` | 30,343 | 周波数 |
| `airport_comments` | 16,406 | 利用者のコメント |

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 単位 | 1 か所 (点)。面は無い |
| 空間範囲 | 全世界。米国が 32,643 件で 38% |
| 時点 | 2026-08-31。各行がいつ更新されたかは分からない |
| CRS | `geometry` の CRS 名は `OGC:CRS84` (経度、緯度) |
| ライセンス | public domain。表示は任意 |

## Natural Earth との結合

CRS の名前が違うので、そのままでは空間結合できない。 Natural Earth は `EPSG:4326`、こちらは `OGC:CRS84`。DuckDB 1.5 は `ST_Intersects` を拒んでエラーにする。どちらも経度、緯度の順の WGS 84 なので、名前だけ揃えればよい。

```sql
select * replace (ST_SetCRS(geometry, 'EPSG:4326') as geometry) from airports
```

コードで結ぶなら `iso_country` (2 文字) を Natural Earth の `ISO_A2_EH` と結ぶ。247 種のうち 237 種が一致する (2026-10-10 実測)。一致しない 10 種は次のとおり。

- フランスの海外県 (`GF`、`RE`、`GP`、`MQ`、`YT`)。Natural Earth の国の面ではフランスに含まれる
- `BQ`、`CC`、`CX`
- `XP`: 南シナ海の西沙諸島の施設。係争地
- `ZZ`: `Non-Existent Airport` のような架空の行

点を Natural Earth の 10m の国の面に入れ、入らなければ 5 km 以内の最寄りの国に割り当てた結果 (最近傍への割り当てを含む点の結合、2026-10-10):

| 区分 | 件数 | `iso_country` と一致 |
|---|---:|---:|
| 国の面に入った | 82,847 | 82,433 (99.5%) |
| 2 つ以上の面に入った | 0 | |
| 5 km 以内の最寄りの国 | 2,327 | 2,295 (98.6%) |
| 割り当たらない | 828 | |

最寄りに割り当てた距離は中央値 0.64 km、90% 点 2.72 km。面から外れた点には海岸の大空港 (ジェノバ、ポートサイド、トロムソなど) が入る。10m の海岸線では埋立地が海になるため。割り当たらない 828 件のうち 540 件はヘリポート。点を国に割り当てるなら、面への包含だけでなく `iso_country` も使い、食い違いを数えて報告する。

## 気をつけること

ほとんどが空港ではない。 `type` は small_airport 42,707、heliport 23,196、closed 13,482、medium_airport 4,109、seaplane_base 1,273、large_airport 1,172、balloonport 63。旅客の空港を数えるなら `type in ('large_airport', 'medium_airport') and scheduled_service = 'yes'` で絞る。この条件で 3,268 件。日本は 3,747 件のうち 3,040 件がヘリポート。

コードは目安。 IATA コードは 9,057 件、ICAO コードは 10,473 件にあるが、利用者が入力したもので、IATA の登録簿と照合されていない。

型は列名で決めてある。 `regions.local_code` の `02` は文字列のまま。自分で CSV を読み直すと数値の 2 になる。
