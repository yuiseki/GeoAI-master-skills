---
kind: dataset
id: yuiseki/gifu-bear-sighting
description: 岐阜県の「クママップ（過去）」のツキノワグマ出没情報 6,946 件 (平成26年度〜令和7年度、FY2014〜FY2025)。年度ごとに列の違う 12 の表を、配布元の列のまま GeoParquet にしたもの。令和2〜7年度の点は、平面直角座標系 VII 系と読んで経緯度に直してある。
url: https://huggingface.co/datasets/yuiseki/gifu-bear-sighting
license: CC BY 4.0 (配布元の表示は CC BY 2.1 JP。同じ系統の後の版として 4.0 で配っている)。出典の表示と加工の明記が要る
formats:
- GeoParquet (年度ごとに 12 ファイル)
- Shapefile の zip 11 と CSV 1 (配布元のまま、raw/2026-10-26/)
crs: OGC:CRS84 として書いてある。H26〜H30 は WGS84 の経緯度、R1 は JGD2011 の経緯度、R2〜R7 は平面直角座標の VII 系 (EPSG:6675) と推定して変換
spatial_coverage: 岐阜県 (県境の外に少しはみ出す点がある)
temporal_coverage: 平成26年度〜令和7年度 (2014-04〜2026-03 の各年度)。行には月と日だけがあり、年はファイルの年度から決まる
as_of:
  source_last_modified: 2025-11-18
  retrieved: 2026-10-26
  huggingface_revision: b7f59470885e485b53cfbdddc0b2e0c2ceb11661
contents:
- 出没の通報 1 件ごとの点と、月、日、時刻、市町村、場所、頭数、通報者の種類、誘因の予測などの配布元の列 (年度で違う)
tables:
- name: h26
  read: hf://datasets/yuiseki/gifu-bear-sighting@b7f59470885e485b53cfbdddc0b2e0c2ceb11661/parquet/h26.parquet
  grain: 1 件の通報。平成26年度 (FY2014)。同じ形で h27、h28、h29、h30 がある (列は Shapefile の 10 文字で切れた名前)
  rows: 1318
  id:
  - row
  no_key:
  - name: code5
    note: 市町村コードは無い。市町村名の列は年度で名前が違う (`出没市町村`、`市町村名` など)。点と jp-admin-2026-09 の面の空間結合で付ける
  columns:
  - name: row
    type: INTEGER
    meaning: 元のファイルの中の順番 (追加した列)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点。ほかの列は配布元の名前と文字列のまま (全角の数字も残る)
- name: r7
  read: hf://datasets/yuiseki/gifu-bear-sighting@b7f59470885e485b53cfbdddc0b2e0c2ceb11661/parquet/r7.parquet
  grain: 1 件の通報。令和7年度 (FY2025)。同じ考え方で r1〜r6 がある (r1 だけ CSV が元で列が多い)
  rows: 721
  id:
  - row
  no_key:
  - name: code5
    note: 市町村コードは無い。`市町村名` の文字列か、点の空間結合で付ける
  columns:
  - name: row
    type: INTEGER
    meaning: 元のファイルの中の順番
  - name: 出没月
    type: VARCHAR
    meaning: 月 (配布元の文字列。`１１月` のような全角もある)
  - name: 出没日
    type: VARCHAR
    meaning: 日 (配布元の文字列)
  - name: 市町村名
    type: VARCHAR
    meaning: 市町村
  - name: 頭数
    type: VARCHAR
    meaning: 頭数 (文字列)
  - name: source_x
    type: DOUBLE
    meaning: 配布元の Shapefile の x (平面直角座標、m)
  - name: source_y
    type: DOUBLE
    meaning: 配布元の Shapefile の y (平面直角座標、m)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: source_x、source_y を EPSG:6675 と読んで経緯度に直した点
---

# 岐阜県 クママップ (過去) (gifu-bear-sighting)

岐阜県環境生活政策課が県のオープンデータカタログ (<https://gifu-opendata.pref.gifu.lg.jp/dataset/c11265-010>) に出している「クママップ （過去）」の 12 ファイルを、年度ごとの GeoParquet にしたもの。最新の情報は県の GIS (県域統合型GISぎふ) にあり、ここには無い。
分析では、12 年度にわたるクマの出没の通報の年ごとの変動 (大量出没の年) と、場所の偏りに使う。年度ごとに列と座標の書き方が違うので、まとめる前に列を対応づける。

## 表

| 表 | 年度 | 行 | 元のファイル | 座標 |
|---|---|---|---|---|
| `h26`〜`h30` | FY2014〜FY2018 | 1,318、443、382、485、269 | Shapefile の zip | WGS84 の経緯度 (`.prj` あり) |
| `r1` | FY2019 | 813 | CSV | JGD2011 の経緯度の列 |
| `r2`〜`r7` | FY2020〜FY2025 | 612、315、253、661、674、721 | Shapefile の zip (`.prj` なし) | 平面直角座標 (m)。VII 系と推定 |

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 12 表で 6,946 (README の表と全て一致) |
| 点と都道府県の面 (`jp-admin-2026-09`) | r1〜r7 の 4,049 点は全て岐阜県の面に入る。h26 は 34 点が長野県、1 点が富山県の面に入り、h27 は 1 点が石川県、h28 は 1 点が長野県の面に入る (ほかに県境で 2 つの面に入る点が 7) |
| h26 の県外の点 | 岐阜県の面からの距離は中央値 0.26 km、最大 0.66 km。どれも県境から 1 km 以内で、座標系の読み違いよりも、位置の粗さか県境の外での通報とみられる |

README は、r2〜r7 の 3,236 点のうち 3,228 点が記録の市町村の面に入ることを、VII 系と読む根拠にしている (国土数値情報 N03 の 2026-01-01 版で)。ここでは都道府県までしか測っていない。

## 気をつけること

- 12 の表は列が揃っていない。Shapefile の列名は 10 文字で切れていて (`出没時間（`、`出没市町2`)、r1 の CSV の列名は `出没市町_1` のように番号が付く。同じ意味の列を年度ごとに対応づけてから合わせる。対応づけた表を報告に書く。
- 年は行に無い。年度 (4 月〜翌 3 月) と月から暦の年を作る (1〜3 月は年度 + 1 年)。
- 月や日は全角の数字を含む文字列。数にするときは NFKC で正規化する。
- r2〜r7 の点は、座標系を推定して変換したもの。配布元は座標系を書いていない。元の値は `source_x`、`source_y` にある。
- 配布元の r1〜r7 には入力した職員の名前の列があり、Parquet では外してある (raw のファイルには残っている)。
- 1 行は通報で、同じ個体が何度も通報されうる。年度の件数の変動 (FY2014 の 1,318 と FY2022 の 253) は、出没の変動と、通報の集め方の変化の両方を含みうる。
- 「過去」の版で、年度が後から足される (R5〜R7 は 2025 年 10 月)。

## 出典の表示

> 出典：岐阜県「クママップ（過去）」（https://gifu-opendata.pref.gifu.lg.jp/dataset/c11265-010）を加工して作成
