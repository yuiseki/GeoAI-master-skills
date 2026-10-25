---
kind: dataset
id: yuiseki/natural-earth
description: 全世界の小縮尺ベクター (国、州・省、都市、海岸線、陸、海、湖、川、道路など)。1 レイヤーが 1 つの GeoParquet。
url: https://huggingface.co/datasets/yuiseki/natural-earth
card_revision: efdd0668c57c9d42307e12eacbf66d8d151de5b9
license: public domain
formats:
- GeoParquet
crs: EPSG:4326
spatial_coverage: 全世界。縮尺は 1:10m、1:50m、1:110m
temporal_coverage: 2022-05 の版 v5.1.2 で止まっている。以後の境界変更、改名、合併は入っていない
as_of:
  version: v5.1.2
  fetched: 2026-10-06
contents:
- 国と地域
- 州・省・県
- 郡 (米国のみ)
- 都市の点
- 陸と海
- 海岸線
- 市街地
tables:
- name: ne_10m_admin_0_countries
  read: hf://datasets/yuiseki/natural-earth@efdd0668c57c9d42307e12eacbf66d8d151de5b9/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet
  grain: 1 つの国または地域 (属領や係争地を含む)
  rows: 258
  id:
  - ADM0_A3
  join_keys:
  - column: ADM0_A3
    type: VARCHAR
    meaning: 3 文字の国コード (Natural Earth 独自)。258 件すべてに入り、重複が無い
    unique: true
    joins: []
  - column: ISO_A3_EH
    type: VARCHAR
    meaning: ISO の 3 文字コードの補正版
    unique: false
    joins:
    - worldbank-wdi:countries.Country Code
    - unhcr-refugee-stats:population.Country of origin (ISO)
    note: 属領が本体と同じ値を持つので、本体の行に絞ってから結ぶ
  - column: ISO_A2_EH
    type: VARCHAR
    meaning: ISO の 2 文字コードの補正版
    joins:
    - ourairports-2026-08:airports.iso_country
  no_key:
  - name: ISO_A3
    note: 22 件が -99。結合キーにしない
  columns:
  - name: POP_EST
    type: DOUBLE
    meaning: 推計人口。年は POP_YEAR で、国によって 2009 から 2020 年
  - name: GDP_MD
    type: INTEGER
    meaning: GDP (百万米ドル)。年は GDP_YEAR で、国によって 1999 から 2019 年
  - name: NAME_JA
    type: VARCHAR
    meaning: 国名の日本語。国境の見方 (de facto) によって表記が変わる
  - name: geometry
    type: geometry:EPSG:4326
    meaning: 国の面 (EPSG:4326)
- name: ne_10m_admin_1_states_provinces
  read: hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_admin_1_states_provinces.parquet
  grain: 1 つの州・省・県。日本は 47 都道府県
  rows: 4596
  id:
  - adm1_code
- name: ne_10m_populated_places
  read: hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_populated_places.parquet
  grain: 1 つの都市 (点)
  rows: 7342
  id: []
---

# Natural Earth

全世界の小縮尺ベクター。国、州・省、都市、海岸線、陸地、海、湖、川、道路、鉄道、空港、港、時間帯など。
分析では、国や州を単位にした集計、点を国や州に割り当てる空間結合、陸と海の判定、地図の下地に使う。

## どこから読むか

Hugging Face の `yuiseki/natural-earth` を使う。1 レイヤーが 1 つの GeoParquet で、認証なしに DuckDB から直接読める。

```
hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/<scale>_<category>/<layer>.parquet
```

- `<scale>` は `10m`、`50m`、`110m`。`<category>` は `cultural` か `physical`。
- 例: `hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet`
- 全レイヤーの一覧 (地物数、列数、ジオメトリ型、無効ジオメトリ数、版) はデータセットカードの Layers の表にある: <https://huggingface.co/datasets/yuiseki/natural-earth>
- ラスタ (陰影起伏など) は入っていない。

```sql
load spatial;
select NAME, ADM0_A3, ST_Area(geometry)
from 'hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/110m_cultural/ne_110m_admin_0_countries.parquet';
```

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 空間範囲 | 全世界 |
| 座標系 | EPSG:4326 (経度、緯度)。面積や距離は投影してから測る。`geometry` の CRS 名は `EPSG:4326` で、`OGC:CRS84` の点 (OurAirports、UCDP GED) とは DuckDB 1.5 がそのままでは空間結合しない |
| 縮尺 | 1:10m (細かい)、1:50m、1:110m (粗い) の 3 段 |
| 時点 | 2022-05 の v5.1.2 で止まっている。以後の境界変更、改名、合併は入っていない |
| ライセンス | public domain。表示も不要 |

## 主なレイヤー

分析でよく使うもの。地物数は 10m のもの。

| レイヤー | 中身 | 地物数 | 単位として使うときの注意 |
|---|---|---:|---|
| `ne_10m_admin_0_countries` | 国と地域 | 258 | 結合キーは `ADM0_A3`。下の「ISO_A3 の -99」を参照 |
| `ne_10m_admin_1_states_provinces` | 州・省・県 | 4,596 | 日本は 47 都道府県が揃い、`name_ja` と `wikidataid` も 47 件すべて入っている |
| `ne_10m_admin_2_counties` | 郡 | 3,224 | 米国だけ。他国の第 2 階層は無い |
| `ne_10m_populated_places` | 都市の点 | 7,342 | `POP_MAX` は 10 件が 0 以下 (最小 -99)。`WIKIDATAID` は 7,192 件にある |
| `ne_10m_land` / `ne_10m_ocean` | 陸と海 | 11 / 1 | 点の陸海判定に使える。`ne_10m_ocean` の 1 件は無効ジオメトリ |
| `ne_10m_coastline` | 海岸線 | 4,133 | 海岸からの距離の特徴量に使える |
| `ne_10m_urban_areas` | 市街地の面 | 11,878 | 版は 4.1.0 で古い |

縮尺を下げると地物が減る。国は 10m で 258、50m で 242、110m で 177 で、小さな島嶼国が消える。点を国に結合するなら 10m を使う。

## 気をつけること

ISO_A3 の -99。 `ne_10m_admin_0_countries` の 258 件中 22 件で `ISO_A3` が `-99`。France と Norway もそう。`ADM0_A3` は 258 件すべてに入っていて重複も無いので、結合キーにはこちらを使う。ISO コードが要るなら `ISO_A3_EH` のほうが埋まっている (France は `FRA`、Norway は `NOR`) が、Kosovo、Somaliland、N. Cyprus などは `ISO_A3_EH` でも `-99`。

ISO_A3_EH は一意でない。 `ISO_A3_EH` が `-99` でない 244 件に対して、値は 238 種類。本体の国と、属領や租借地が同じコードを持つ: `AUS` (Australia、Ashmore and Cartier Is.、Coral Sea Is.、Indian Ocean Ter.)、`BRA` (Brazil、Brazilian I.)、`FRA` (France、Clipperton I.)、`KAZ` (Kazakhstan、Baikonur)。そのまま結合すると国の行が増える。本体を選ぶには、同じ `ISO_A3_EH` の中で `ADM0_A3 = ISO_A3_EH` の行を優先する。`ADM0_A3 = ISO_A3_EH` だけで絞ると、`ADM0_A3` の綴りが違う Palestine (`PSX`)、S. Sudan (`SDS`)、W. Sahara (`SAH`)、Åland (`ALD`) が落ちる (2026-10-10 実測)。

```sql
select * from ne_10m_admin_0_countries
where ISO_A3_EH <> '-99'
qualify row_number() over (partition by ISO_A3_EH order by (ADM0_A3 = ISO_A3_EH) desc) = 1
```

人口と GDP の年が揃っていない。 国の `POP_EST` の年 (`POP_YEAR`) は 258 件中 232 件が 2019 年で、残りは 2009〜2020 年。`GDP_MD` の年 (`GDP_YEAR`) は 193 件が 2019 年で、残りは 1999〜2018 年に散らばる。国の間で比べる特徴量にするなら `POP_YEAR` と `GDP_YEAR` を確かめる。最新の値が要るなら World Bank などの統計と結合する。

国境は de facto。 既定は実効支配の線。`ne_10m_admin_0_countries_<iso>` の 33 レイヤーが国ごとの見方の変種。たとえば `NAME_JA` は Taiwan が `中華民国`、Kosovo が `コソボ共和国`。どの見方を使ったかを報告に書く。

無効ジオメトリ。 `ne_10m_admin_0_countries` では Egypt の 1 件が `ST_IsValid` で偽になる。`ne_10m_urban_areas_landscan` は 6,018 件中 2,238 件が無効。面積や交差を計算する前に `ST_MakeValid` するか、件数を数えて報告する。

ジオメトリの無いレイヤーがある。 `ne_10m_admin_0_names` は geometry 列を持つが 505 件すべて NULL。国名の別表記の表として使う。

## 確かめた日

2026-10-10 に `hf://` から DuckDB 1.5.5 以上で読んで実測した。データセットの取得日は 2026-10-06 (カードの記載)。
