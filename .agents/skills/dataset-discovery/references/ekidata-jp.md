---
kind: dataset
id: yuiseki/ekidata-jp
description: 駅データ.jp 無料版の、鉄道事業者、路線、駅 (座標つき)、路線上の隣り合う駅、都道府県の表。日付ごとの版に分けた型つき Parquet。
url: https://huggingface.co/datasets/yuiseki/ekidata-jp
card_revision: a33321099406b47338be0d03a4887059473fde0c
license: 駅データ.jp の利用規約 (https://ekidata.jp/agreement.php)。改変しない再配布は無償のときだけ
formats:
- CSV
- Parquet
- GeoParquet 1.0
crs: OGC:CRS84
spatial_coverage: 日本全国。無料版は新幹線の駅を含まない
temporal_coverage: 取得は 2026-10-05。収録版は 2025-05-23 から 2026-09-14。最新の駅の版は 2026-07-31。都道府県の表は日付なし
as_of:
  fetched: 2026-10-05
  latest_station_edition: 2026-07-31
contents:
- 鉄道事業者
- 路線
- 駅と座標
- 路線上の隣り合う駅
- 都道府県の表
tables:
- name: station
  read: hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/station.2026-07-31.parquet
  grain: 路線ごとの 1 駅。乗換駅は路線の数だけ行がある
  rows: 10962
  id:
  - station_cd
  join_keys:
  - column: station_g_cd
    type: INTEGER
    meaning: 路線が違っても同じ駅とみなす駅のグループ
    unique: false
    joins:
    - station.station_g_cd
  - column: line_cd
    type: INTEGER
    meaning: 路線のコード
    joins:
    - line.line_cd
    - join.line_cd
  - column: pref_cd
    type: INTEGER
    meaning: 都道府県コード (整数 1 から 47)
    joins:
    - pref.pref_cd
    - jp-admin-2026-09:municipalities.pref_code (型を揃える)
    cast: jp-admin-2026-09 の pref_code は 2 桁の文字列。cast(pref_cd as integer) と、cast(pref_code as integer) で揃える
  no_key:
  - name: code5
    note: 市区町村コードは持たない。市区町村とは点の空間結合で結ぶ
  - name: osm_id
    note: OpenStreetMap とは ID で結べない
  columns:
  - name: e_status
    type: INTEGER
    meaning: 0 が運行中、1 が未開業、2 が廃止
  - name: lon
    type: DOUBLE
    meaning: 経度 (世界測地系。WGS 84 として読む)。lat が緯度
  - name: open_ymd
    type: VARCHAR
    meaning: 開業日。0000-00-00 は日付なし (10
    584 駅): null
    missing: '''0000-00-00'' は日付なし (10,962 駅のうち 10,584 駅)'
  - name: geometry
    type: geometry:OGC:CRS84
    meaning: lon と lat から作った点 (OGC:CRS84)
- name: line
  read: hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/line.2026-06-18.parquet
  grain: 1 路線
  rows: 624
  id:
  - line_cd
  join_keys:
  - column: company_cd
    type: INTEGER
    meaning: 事業者のコード
    joins:
    - company.company_cd
  columns:
  - name: lon
    type: DOUBLE
    meaning: 路線全体を地図に収める中心の経度であって、路線の位置ではない。lat、zoom も同じ
- name: company
  read: hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/company.2026-04-09.parquet
  grain: 1 つの鉄道事業者
  rows: 175
  id:
  - company_cd
  columns:
  - name: company_type
    type: INTEGER
    meaning: 0 がその他、1 が JR、2 が大手私鉄、3 が準大手私鉄
- name: join
  read: hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/join.2026-09-14.parquet
  grain: ある路線の上で隣り合う 2 つの駅の組
  rows: 10188
  id:
  - line_cd
  - station_cd1
  - station_cd2
  join_keys:
  - column: station_cd1
    type: INTEGER
    meaning: 隣り合う駅の片方 (station_cd2 がもう片方)
    joins:
    - station.station_cd
- name: pref
  read: hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/pref.parquet
  grain: 1 つの都道府県。コード 99 の「その他」を含む
  rows: 48
  id:
  - pref_cd
---

# 駅データ.jp (ekidata-jp)

日本の鉄道事業者、路線、駅 (座標付き)、路線ごとの隣り合う駅の組、都道府県の表。駅データ.jp の無料版の CSV を、日付ごとの版に分けて型を付けた Parquet にしたもの。
分析では、駅までの距離や駅の密度を点の特徴量にする、鉄道のネットワークの節点にする、といった使い方をする。

## どこから読むか

Hugging Face の `yuiseki/ekidata-jp`。2026-10-05 に取得した版が `parquet/2026-10-05/` にある。

```
hf://datasets/yuiseki/ekidata-jp/parquet/2026-10-05/<table>.<date>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/ekidata-jp>
- 駅データ.jp の仕様: <https://ekidata.jp/doc/>
- 最新の版は、日付のない `station`、`line`、`company`、`join` の名前でも引ける。ただし、日付つきの名前で読んで、版を報告に書く。

| テーブル | 最新の版 | 行数 | 1 行 |
|---|---|---:|---|
| `station` | 2026-07-31 | 10,962 | 路線ごとの 1 駅。点の `geometry` を持つ |
| `line` | 2026-06-18 | 624 | 1 路線 |
| `company` | 2026-04-09 | 175 | 1 事業者 |
| `join` | 2026-09-14 | 10,188 | 路線上の隣り合う 2 駅 |
| `pref` | (日付なし) | 48 | 都道府県。47 と、コード 99 の「その他」(どの駅も使っていない) |

行数は 2026-10-13 に実測した。

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 単位 | `station` は路線ごとの駅。乗換駅は路線の数だけ行がある |
| 駅のグループ | `station_g_cd` が同じ駅は、路線が違っても 1 つの駅とみなす。9,157 のグループ (2026-07-31 版) |
| CRS | `geometry` は `GEOMETRY('OGC:CRS84')` (経度、緯度)。仕様は世界測地系としか書かず、WGS 84 として読んでいる |
| ライセンス | 駅データ.jp の規約 (独自)。使用、改変、再配布は許されるが、再配布は改変せず無償のときだけ。使う前に <https://ekidata.jp/agreement.php> を読む |

運行中 (`e_status = 0`) の駅は 10,465。都道府県で多いのは東京都 943、大阪府 595、愛知県 544。

## 気をつけること

- 新幹線の駅が無い。無料版が省いている。新幹線の 12 路線は `line` にあるが駅は無く、`join` の 154 行は、どの駅の表にもない 6 桁のコードの組。
- 有料の列が空。`station_name_k`、`station_name_r`、`line_type` は全行空 (カードによる)。
- `open_ymd` と `close_ymd` の `0000-00-00` は、日付なしを表す。`station.2026-07-31` では、10,962 駅のうち 10,584 駅の `open_ymd` がそうなので、開業年での絞り込みはほとんどの駅を落とす。
- 加木屋中ノ池 (`station_cd` 3000922) の `lat` が 35.0 で、整数になっている (実測)。ほかの駅は小数点以下 3 桁以上。位置がずれている疑いがあるので、そのまま使わず確かめる。
- 駅の数え方が 3 通りある。行 (路線ごとの駅)、`station_g_cd` (乗換駅を 1 つ)、運行中だけ、で数が違う。何を数えたかを書く。
- 版ごとに数行が違う。分析で使った版を固定して書く。
- 取得は 2026-10-05。サイトは随時直すので、最新の版とは限らない。

## ほかのデータとの結合

- 市区町村との空間結合は `jp-admin-2026-09.md` の例にある。点の座標系の名前を揃えてから結ぶ。
- 駅の `pref_cd` は、1〜47 の整数。`jp-admin-2026-09` の `pref_code` は文字列の 2 桁なので、型を揃えて結ぶ (整数にそろえるか、0 を付ける)。
