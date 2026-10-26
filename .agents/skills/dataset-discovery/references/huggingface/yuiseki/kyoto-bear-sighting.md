---
kind: dataset
id: yuiseki/kyoto-bear-sighting
description: 京都府の「クマ目撃情報」の統合版、平成21年度〜平成30年度 (2009-04-08〜2018-12-10) の 10,225 件を GeoParquet にしたもの。場所、環境区分、成獣と幼獣の数、目撃時の状況、その後の処置、市町村コードを持つ。2018 年 12 月より後は無い。
url: https://huggingface.co/datasets/yuiseki/kyoto-bear-sighting
license: CC BY 4.0 (BODIK のエントリが CC BY 4.0 国際を表示)。出典の表示と加工の明記が要る
formats:
- GeoParquet
- CSV (配布元のまま、raw/2026-10-26/)
crs: OGC:CRS84 として書いてある。配布元は測地系を書いていない (WGS84 とみなしている)
spatial_coverage: 京都府 (府境の外に少しはみ出す点がある)
temporal_coverage: 2009-04-08〜2018-12-10 (FY2009〜FY2018。FY2018 は 12 月まで)
as_of:
  source_last_modified: 2022-04-18
  retrieved: 2026-10-26
  huggingface_revision: a2a50c4bd863efe96ef7ed8087ee4e1d0db01858
contents:
- 目撃 1 件ごとの点、日付、場所、環境区分、成獣・幼獣・その他の数 (文字列)、状況、個体の状況、処置、市町村コード
tables:
- name: sighting
  read: hf://datasets/yuiseki/kyoto-bear-sighting@a2a50c4bd863efe96ef7ed8087ee4e1d0db01858/parquet/sighting.parquet
  grain: 1 件の目撃の通報
  rows: 10225
  id: []
  join_keys:
  - column: municipality_code6
    type: VARCHAR
    meaning: 6 桁の市町村コード (検査数字つき)
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.lg_code
    note: 10,225 行全てが結べる (実測)
  - column: municipality_code
    type: VARCHAR
    meaning: 5 桁の市町村コード。京都市は区のコード
    unique: false
    note: jp-admin-2026-09 の code5 と 10,224 行が結べる。1 行は結べない
  columns:
  - name: fiscal_year
    type: SMALLINT
    meaning: 年度。date の年度と全行で一致 (実測)
  - name: place
    type: VARCHAR
    meaning: 観察場所 (市町村名と地名)
  - name: environment
    type: VARCHAR
    meaning: 環境区分 (集落内、路上、畑、スギ林など 16 種類)
  - name: date
    type: DATE
    meaning: 目撃年月日
  - name: adults_text
    type: VARCHAR
    meaning: 成獣の数 (文字列)
  - name: juveniles_text
    type: VARCHAR
    meaning: 幼獣の数 (文字列)
  - name: others_text
    type: VARCHAR
    meaning: その他の数 (文字列。`不明` が 100 行)
  - name: action
    type: VARCHAR
    meaning: その後の処置 (自由記述)
  - name: municipality
    type: VARCHAR
    meaning: 市町村名 (京都市は区に分けず「京都市」)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点 (経度, 緯度)
---

# 京都府 クマ目撃情報 (kyoto-bear-sighting)

京都府が BODIK のオープンデータカタログ (<https://data.bodik.jp/dataset/260002_bear>) に出している「【京都府】クマ目撃情報」の統合版 CSV (平成21年度分〜平成30年度分) を、GeoParquet にしたもの。年度ごとの CSV、XLSX、RDF は取っていない。
分析では、10 年分のクマの目撃の年ごとの変動と、環境区分 (集落内、路上、林など) ごとの違いに使う。2018 年 12 月で止まっているので、近年の出没には使えない。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 10,225 (README と一致) |
| 日付 | 2009-04-08〜2018-12-10。`fiscal_year` と date の年度は全行で一致 |
| 範囲 | 経度 134.87〜135.85、緯度 34.84〜35.78 |
| 点と面 (`jp-admin-2026-09`) | 10,203 点が京都府の面に入る。15 点はどの面にも入らない (記録は宮津市 10、京丹後市 4 など。海岸の近くの点とみられる)。7 点は隣の県の面に入る (兵庫県 4、福井県 2、大阪府 1) |
| 記録の市町村と面 | 京都府の面に入る点のうち、記録の市町村と面の市町村が違うのは 84 点 (舞鶴市と記録して綾部市の面に入る 10 点など) |
| 市町村コード | 6 桁の `municipality_code6` は jp-admin-2026-09 の `lg_code` と 10,225 行全てで結べる。5 桁は京都市の区のコードで、1 行は結べない |
| 多い市町村 | 京丹後市 2,557、宮津市 1,619、与謝野町 1,542 (コードで 19 種類) |

## 気をつけること

- 2018 年 12 月までで、FY2018 は年度の途中で終わる。年度の件数を比べるなら FY2018 の扱いを書く。
- 頭数は文字列で、合計の列は無い。`others_text` には `不明` と、数でない文が 1 行ある。数にするなら、読めない値の扱いを書く。
- 年の件数は 239 (FY2009、年度の途中から) から 1,975 (FY2010) まで 8 倍違う。配布元は集め方を書いていない。出没の変動と通報の集め方の変化を区別できない。
- 同じ場所、座標、日付の行が 101 組ある (README)。同じ通報の重複か、別の目撃かは分からない。
- 場所の精度は書かれていない。84 点が記録と別の市町村の面に入る。
- 他の府県のクマのデータとは、集め方、期間、列が違う。

## 出典の表示

> 出典：京都府「クマ目撃情報」（https://data.bodik.jp/dataset/260002_bear）を加工して作成
