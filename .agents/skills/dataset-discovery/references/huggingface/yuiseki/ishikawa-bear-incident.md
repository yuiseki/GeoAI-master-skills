---
kind: dataset
id: yuiseki/ishikawa-bear-incident
description: 石川県の「石川県クマ出没データ」。R1〜R6 の出没分析マップ (要因ごとの 5 ファイル) と R7 の目撃情報の 6 つの表、3,901 行を GeoParquet にしたもの。R1〜R6 の 5 つの表は同じ出没を要因で切り出したもので、重なっている。
url: https://huggingface.co/datasets/yuiseki/ishikawa-bear-incident
license: CC BY 4.0 (配布元は cc-by を表示、版は書いていない)。出典の表示と加工の明記が要る
formats:
- GeoParquet (6 ファイル)
- CSV (配布元のまま、raw/2026-10-26/)
crs: OGC:CRS84 として書いてある。配布元は測地系を書いていない (WGS84 とみなしている)
spatial_coverage: 石川県
temporal_coverage: R1〜R6 の表は 2019-01-08〜2024-12-26 (暦の年で区切られている。本文)。R7 の表は 2025-01〜2025-06-18
as_of:
  source_last_modified: 2025-09-26
  retrieved: 2026-10-26
  huggingface_revision: d2b77a201a1ab2cfa0534a7c8b513a495179f24a
contents:
- 出没 1 件ごとの点、種別 (目撃、痕跡、人身被害)、日付、時刻、市町、場所、備考、頭数、集落
- R1〜R6 は、森林、河川、誘引物、親離れした若グマ、大量出没年 (R2) の要因ごとのファイル
tables:
- name: forest_r1_r6
  read: hf://datasets/yuiseki/ishikawa-bear-incident@d2b77a201a1ab2cfa0534a7c8b513a495179f24a/parquet/forest_r1_r6.parquet
  grain: 森林からの出没と分類された 1 件。同じ形で river_r1_r6 (390)、attractants_r1_r6 (273)、young_bears_r1_r6 (467)、mass_outbreak_r2 (245) がある
  rows: 2423
  id:
  - row
  join_keys:
  - column: municipality
    type: VARCHAR
    meaning: 市町名
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.name
  no_key:
  - name: id
    note: 配布元の ID は年ごとに振り直され、表の中でも重なる。表どうしを結ぶ鍵にならない
  - name: settlement_code
    note: 集落コードと 500 m メッシュコードは、配布元の表計算ソフトで指数表記になっている。1,130 行は 3 桁しか残らず、元に戻せない
  columns:
  - name: row
    type: BIGINT
    meaning: CSV の中の順番 (1 から)
  - name: record_type
    type: VARCHAR
    meaning: 目撃痕跡種別。目撃、痕跡、人身被害 (1 行だけ `1`)
  - name: year
    type: VARCHAR
    meaning: 出没年 `R1`〜`R6`。中身は暦の年 (本文)
  - name: date_text
    type: VARCHAR
    meaning: 出没日の文字列 (`R4.3.3`、`2019/1/8`、`2025.1.9`、Excel の通し番号が混ざる)
  - name: date
    type: DATE
    meaning: date_text から読んだ日付。forest で 1 行が NULL
  - name: municipality
    type: VARCHAR
    meaning: 市町名
  - name: place
    type: VARCHAR
    meaning: 場所
  - name: count_text
    type: VARCHAR
    meaning: 頭数の文字列 (`1`、`1頭`、`-`)
  - name: forest
    type: VARCHAR
    meaning: 要因の印 (`1` か `1.0`)。表ごとに列の名前が違う (river、attractant_cause、young_bear、mass_outbreak)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点 (経度, 緯度)
- name: sightings_r7
  read: hf://datasets/yuiseki/ishikawa-bear-incident@d2b77a201a1ab2cfa0534a7c8b513a495179f24a/parquet/sightings_r7.parquet
  grain: R7 (2025 年) の目撃・痕跡の 1 件。ID もコードも無い別の形の表
  rows: 103
  id:
  - row
  columns:
  - name: date
    type: DATE
    meaning: 日付 (2025-01〜2025-06-18)
  - name: municipality
    type: VARCHAR
    meaning: 市町名
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点
---

# 石川県 クマ出没データ (ishikawa-bear-incident)

石川県自然環境課が県のオープンデータカタログ (<https://ckan.opendata.pref.ishikawa.lg.jp/dataset/bear_incidents_data>) に出している「石川県クマ出没データ」の 6 つの CSV を、それぞれ GeoParquet にしたもの。
分析では、県が付けた出没の要因 (森林、河川、誘引物、若グマ、大量出没年) ごとの場所の違いに使う。要因の分類は県の判断で、データから作り直せない。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 6 表で 3,901 (README と一致)。R1〜R6 の 5 表で 3,798 |
| R1〜R6 の重なり | 日付、場所、座標が同じ行が別の表にもある行は 2,221 (4 つが揃う行で数えた。README は 2,224)。日付、場所、座標の組は 2,589 種類 |
| 種別 (R1〜R6 の 5 表) | 目撃 3,161、痕跡 612、人身被害 24、`1` が 1 |
| `year` と日付 | R1 は 2019-01-08〜2019-11-05、R2 は 2020-01-05〜2020-12-29、…、R6 は 2024-01-12〜2024-12-26。どの年も 1 月から 12 月で、年度 (4 月〜翌 3 月) ではない |
| 点と面 (`jp-admin-2026-09`) | 3,901 点が全て石川県の面に入る (2 点は富山県の面にもかかる県境の点)。記録の市町と面の市町が違うのは 19 点 (羽咋市と記録して志賀町の面に入る 4 点など) |

## 気をつけること

- R1〜R6 の 5 つの表を足して出没の件数にしない。同じ出没が複数の要因の表に入っている。出没の数を数えるなら、日付、場所、座標で重なりを除き、除き方を書く (同じ日に同じ場所で 2 件あった場合と区別できない)。
- `year` の R1〜R6 は、README の説明 (年度) と違い、中身は暦の年。年度で集計するなら日付から作り直す。
- ID は年ごとに振り直されていて、表の中でも重なる。鍵にしない。
- 集落コードと 500 m メッシュコードは、配布元で指数表記に壊れている行がある (1,130 行)。メッシュが要るなら点から作り直す。
- R7 の表は形が違い (ID もコードも無い)、2025-06-18 までしかない。配布元が後から足しうる。
- 他の県のクマのデータとは、集め方と分類が違う。

## 出典の表示

> 出典：石川県「石川県クマ出没データ」（https://ckan.opendata.pref.ishikawa.lg.jp/dataset/bear_incidents_data）を加工して作成
