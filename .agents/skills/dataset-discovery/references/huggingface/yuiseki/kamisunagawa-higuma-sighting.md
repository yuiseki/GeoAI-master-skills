---
kind: dataset
id: yuiseki/kamisunagawa-higuma-sighting
description: 北海道上砂川町の「ヒグマ出没マップ」(令和6〜8年度) 105 件を、1 つの GeoParquet にしたもの。小さな町の全件。令和8年度は途中 (2026-09-14 時点)。
url: https://huggingface.co/datasets/yuiseki/kamisunagawa-higuma-sighting
license: CC BY 4.0 (BODIK の各年度のエントリが CC BY 4.0 国際を表示)。出典の表示と加工の明記が要る
formats:
- GeoParquet
- CSV 3 (配布元のまま。R6 は Shift_JIS、R7 と R8 は UTF-8)
crs: OGC:CRS84 として書いてある。配布元は測地系を書いていない (WGS84 とみなしている)
spatial_coverage: 北海道空知郡上砂川町とその周り
temporal_coverage: 2024-05-11〜2026-08-19 (令和6年度〜令和8年度の途中)
as_of:
  source_state: 2026-09-14
  retrieved: 2026-10-26
  huggingface_revision: 0a6f16be810deb3fac4b17befde7791120f1fdbd
contents:
- ヒグマの出没 (目撃、足跡、ふん) の 1 件ごとの点、日付、時刻、場所、状況
tables:
- name: sighting
  read: hf://datasets/yuiseki/kamisunagawa-higuma-sighting@0a6f16be810deb3fac4b17befde7791120f1fdbd/parquet/sighting.parquet
  grain: 1 件の出没の記録
  rows: 105
  id:
  - source_file
  - row
  join_keys:
  - column: municipality_code
    type: VARCHAR
    meaning: 全国地方公共団体コード。R6 と R7 は `14257` (先頭の 0 が落ちている)、R8 は `014257`
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.lg_code
    note: 6 桁に 0 で埋めると (lpad(municipality_code, 6, '0')) 105 行全てが上砂川町 (code5 01425) に結べる (実測)
  columns:
  - name: fiscal_year
    type: SMALLINT
    meaning: 年度 (2024、2025、2026)
  - name: source_file
    type: VARCHAR
    meaning: 元の CSV
  - name: row
    type: INTEGER
    meaning: CSV の中の順番。ファイルごとに 1 から
  - name: date
    type: DATE
    meaning: 出没年月日
  - name: time_text
    type: VARCHAR
    meaning: 時刻 (`H:MM` の文字列)
  - name: place
    type: VARCHAR
    meaning: 場所の文 (R7 と R8)。R6 は address_text、town、lot に分かれている
  - name: situation
    type: VARCHAR
    meaning: 状況 (自由記述)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点 (経度, 緯度)
---

# 上砂川町 ヒグマ出没マップ (kamisunagawa-higuma-sighting)

上砂川町が BODIK のオープンデータカタログに年度ごとに出している「ヒグマ出没マップ」(<https://data.bodik.jp/dataset/014257_r6bear_map>、`_r7bear_map`、`_r8bear_map`) の 3 つの CSV を、1 つの表にしたもの。年度で列が違う (R6 は住所を分けて持ち、R7 と R8 は場所を 1 つの文で持つ) ので、無い列は NULL。
分析では、1 つの町の中での出没の場所と季節の例として使う。105 件しかないので、統計の推定より、手順を確かめる小さな例に向く。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 105 (R6 14、R7 82、R8 9。README と一致) |
| 日付 | 2024-05-11〜2026-08-19 |
| 範囲 | 経度 141.948〜142.021、緯度 43.466〜43.485 |
| 点と面 (`jp-admin-2026-09`) | 104 点が上砂川町の面、1 点が隣の砂川市の面に入る |
| `municipality_code` | `14257` が 96 行、`014257` が 9 行 |

## 気をつけること

- `row` はファイルごとに 1 から振り直す。行を区別するなら `source_file` と `row` の組を使う。
- `municipality_code` は年度で桁が違う。結ぶ前に 6 桁に揃える。
- R8 は年度の途中 (2026年9月14日現在)。年度の件数を比べるなら、R8 を外すか、同じ時期までで比べる。
- 記録は町が受けた通報で、同じ個体が何度も記録されうる。

## 出典の表示

> 出典：上砂川町「ヒグマ出没マップ」（https://data.bodik.jp/dataset/014257_r6bear_map, https://data.bodik.jp/dataset/014257_r7bear_map, https://data.bodik.jp/dataset/014257_r8bear_map）を加工して作成
