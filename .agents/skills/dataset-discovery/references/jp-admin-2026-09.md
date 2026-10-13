---
kind: dataset
id: yuiseki/jp-admin-2026-09
description: 日本の 47 都道府県と 1,918 市区町村の名前、コード、面、2020 年国勢調査の人口と世帯数を結んだもの。市区町村より細かい単位は無い。
url: https://huggingface.co/datasets/yuiseki/jp-admin-2026-09
card_revision: e6c87b1d7095c17422147962185071a986e13135
license: CC-BY-4.0
formats:
- GeoParquet 1.1
crs: EPSG:4612
spatial_coverage: 日本 47 都道府県、1,918 市区町村。面、人口、世帯数が空の自治体が 9 ある
temporal_coverage: 名前とコードは 2026-09、面と人口と世帯数は 2020 年国勢調査
as_of:
  names_and_codes: 2026-09
  boundaries_and_counts: 2020-10-01
contents:
- 行政区域の名前とコード
- 代表点
- 行政区域の面
- 人口
- 世帯数
tables:
- name: municipalities
  read: hf://datasets/yuiseki/jp-admin-2026-09/municipalities.parquet
  grain: 1 つの市区町村。政令指定都市は、親の市と、その区が別の行になる (171 区)
  rows: 1918
  id:
  - lg_code
  - code5
  join_keys:
  - column: code5
    type: VARCHAR
    meaning: 5 桁の市区町村コード。区は区のコードを持つ
    unique: true
    joins:
    - mlit-toshi-keikaku-jp:*.Citycode
    note: 1,918 行で重複が無い (実測)。全国の合計を取るときは、親と区が重なるので ward is null に絞る
  - column: pref_code
    type: VARCHAR
    meaning: 2 桁の都道府県コード (文字列)
    joins:
    - ekidata-jp:station.pref_cd (整数。型を揃える)
    cast: ekidata-jp の pref_cd は整数。cast(pref_code as integer) で揃える
  no_key:
  - name: osm_id
    note: OpenStreetMap とは ID で結べない。コードか空間結合で結ぶ
  columns:
  - name: lg_code
    type: VARCHAR
    meaning: 地方公共団体コード 6 桁 (住所基盤登録簿)
  - name: name
    type: VARCHAR
    meaning: 市区町村名。区は 浜松市中央区 のように市名つき
  - name: ward
    type: VARCHAR
    meaning: 政令指定都市の区の名前。親の市の行では空
  - name: population
    type: BIGINT
    meaning: 2020 年国勢調査の人口 (小地域の合計)。推計ではない。空は調べていないこと
    missing: NULL は調べていない (9 行。北方領土の 6 村と浜松市の新しい 3 区)。0 ではない
  - name: households
    type: BIGINT
    meaning: 2020 年国勢調査の世帯数
    missing: NULL は調べていない (9 行)
  - name: geometry_source
    type: VARCHAR
    meaning: 面の出所。census small areas、union of its wards、none
  - name: rep_lon
    type: DOUBLE
    meaning: 住所基盤登録簿の代表点の経度。rep_lat が緯度
  - name: geometry
    type: geometry:EPSG:4612
    meaning: 市区町村の面 (EPSG:4612)。海を含まない
    missing: NULL は面が無い (9 行)
- name: prefectures
  read: hf://datasets/yuiseki/jp-admin-2026-09/prefectures.parquet
  grain: 1 つの都道府県
  rows: 47
  id:
  - pref_code
  columns:
  - name: population
    type: BIGINT
    meaning: 2020 年国勢調査の人口。市区町村の ward is null の行の合計と一致する
    missing: 欠損なし (47 行すべてに値がある)
---

# jp-admin-2026-09 (日本の都道府県と市区町村)

日本の 47 都道府県と 1,918 市区町村の、コード、名前 (漢字、かな、ローマ字)、面、2020 年国勢調査の人口と世帯数。市区町村より細かい単位は無い。
分析では、点や格子を行政区に集計するときの境界、人口で割る分母、日本の地域の結合キーに使う。

## どこから読むか

Hugging Face の `yuiseki/jp-admin-2026-09`。2 つのファイルがある。

```
hf://datasets/yuiseki/jp-admin-2026-09/prefectures.parquet
hf://datasets/yuiseki/jp-admin-2026-09/municipalities.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/jp-admin-2026-09>
- 作り方は GitHub の `yuiseki/jp-admin-2026-09` (入力は 2 つの凍結データセットを、コミットで固定して読む)。

## 粒度と範囲

2026-10-13 に実測した。

| 項目 | 値 |
|---|---|
| 単位 | 1 つの都道府県、1 つの市区町村 |
| 行数 | `prefectures` 47、`municipalities` 1,918 (政令指定都市の区 171 を含む) |
| CRS | `geometry` は `GEOMETRY('EPSG:4612')` (JGD2000 の経度、緯度)。GeoParquet 1.1、`bbox` 列付き |
| 範囲 | 日本全国 |
| 時点 | 名前とコードは 2026-09 の住所基盤登録簿、面と人口は 2020 年国勢調査 |
| ライセンス | CC BY 4.0。出典の表示が要る (カードに文例がある) |

主な列は、`lg_code` (6 桁)、`code5` (5 桁)、`pref_code`、`pref` `county` `city` `ward` (それぞれ `_kana`、`_roma` 付き)、`name`、`efct_date`、`rep_lon` `rep_lat` (代表点)、`population`、`households`、`small_areas`、`geometry_source`、`geometry`、`bbox`。

## 気をつけること

- 市区町村の表には、政令指定都市の親 (札幌市など) と、その区が両方入っている。全国の合計は `ward is null` の行で取る。実測で、`ward is null` の行の `population` の合計は 126,146,099 で、`prefectures` の合計と一致し、令和 2 年国勢調査の公表値と同じ (カードによる)。
- 面と人口が空の行がある。`geometry` が空なのは 9 行で、`geometry_source` が `none`。北方領土の 6 村 (国勢調査が調べていない) と、2024 年に浜松市にできた 3 区 (2020 年の国勢調査より後)。空は 0 ではなく、調べていないことを表す。
- 名前は 2026-09、面は 2020 年で、時点が 6 年違う。この間に変わった市区町村は、現在の名前に古い形が付く。
- 面は国勢調査の小地域を溶かしたもの。海を含まないので、海岸の点が面に入らないことがある (下の結合の例)。
- 政令指定都市の親 20 件の面は、区の面を合わせたもの (`geometry_source` が `union of its wards`)。

## ほかのデータとの結合

- 結合キーは `code5` (5 桁の市区町村コード)。`mlit-toshi-keikaku-jp` の `Citycode` と結べる。実測で、`youto` の 1,215 の `Citycode` はすべて `code5` に一致した。
- 空間結合では、座標系の名前が揃っていないとエラーになる。ekidata-jp の点 (`OGC:CRS84`) をそのまま入れると、DuckDB 1.5 は座標系が互換でないと拒む。名前だけ揃える (どちらも経度、緯度で、差は駅の位置の精度より小さい)。

```sql
load spatial;
select count(*) from (
  select ST_SetCRS(geometry, 'EPSG:4612') as g
  from 'hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/station.2026-07-31.parquet' where e_status = 0
) s join 'hf://datasets/yuiseki/jp-admin-2026-09/municipalities.parquet' m
  on ST_Within(s.g, m.geometry) and m.ward is null;
```

運行中の駅 10,465 のうち、10,464 が面に入った。入らなかった 1 駅は、長崎県の海沿いの千綿駅 (2026-10-13 実測)。入った駅では、駅の `pref_cd` と面の `pref_code` が全部一致した。
