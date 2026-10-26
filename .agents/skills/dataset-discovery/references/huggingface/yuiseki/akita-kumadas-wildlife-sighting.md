---
kind: dataset
id: yuiseki/akita-kumadas-wildlife-sighting
description: 秋田県の「ツキノワグマ等情報マップシステム『クマダス』」の出没情報 24,757 件 (2022-04〜2026-09)。ツキノワグマ、イノシシ、ニホンジカの目撃、痕跡、人身被害を、場所の点、日時、頭数とともに GeoParquet にしたもの。毎月上書きされる配布元の 2026-10-26 の状態。
url: https://huggingface.co/datasets/yuiseki/akita-kumadas-wildlife-sighting
license: CC BY 4.0 (秋田県オープンデータカタログが CC-BY-4.0 を表示)。出典の表示と加工の明記が要る
formats:
- GeoParquet
- CSV (配布元のまま、raw/2026-10-26/)
crs: OGC:CRS84 として書いてある。配布元は測地系を書いていない (WGS84 とみなしている)
spatial_coverage: 秋田県の 25 市町村
temporal_coverage: 2022-04-10〜2026-09-30 (目撃日時)。配布元の 20260930 時点の版
as_of:
  source_state: 2026-09-30
  retrieved: 2026-10-26
  huggingface_revision: c7047ab442ea3471aaa52af6e56a966ac768ff61
contents:
- 出没情報 1 件ごとの点、住所の文字列、日時、獣種、情報の種別、性別、単独か親子か、頭数、状況の文
tables:
- name: sighting
  read: hf://datasets/yuiseki/akita-kumadas-wildlife-sighting@c7047ab442ea3471aaa52af6e56a966ac768ff61/parquet/sighting.parquet
  grain: 1 件の通報 (出没情報)。1 頭の個体ではない
  rows: 24757
  id:
  - id
  join_keys:
  - column: municipality
    type: VARCHAR
    meaning: 市町村名 (25 種類)。コードは無い
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.name
    note: 名前の一致で結べるが、点を市区町村の面に入れて付けるほうが確か (本文)
  no_key:
  - name: code5
    note: 市町村コードは無い。点と jp-admin-2026-09 の面の空間結合で付ける
  columns:
  - name: id
    type: INTEGER
    meaning: 出没情報ID。重複なし。1〜28054 のうち 3,297 の番号は欠けている
  - name: info_type
    type: VARCHAR
    meaning: 情報種別。目撃、痕跡(その他)、痕跡(食害)、人身被害
  - name: municipality
    type: VARCHAR
    meaning: 市町村
  - name: address
    type: VARCHAR
    meaning: 地番情報 (郵便番号と住所や目印の文字列)
  - name: observed_at
    type: TIMESTAMP
    meaning: 目撃日時。日本時間、時間帯の情報なし
  - name: species
    type: VARCHAR
    meaning: 獣種。ツキノワグマ、イノシシ、ニホンジカ
  - name: sex
    type: VARCHAR
    meaning: 性別。不明、メス、オス
  - name: group
    type: VARCHAR
    meaning: 単独か親子か (群れはイノシシとシカ)
  - name: count
    type: SMALLINT
    meaning: 頭数。87 件は 0
  - name: situation
    type: VARCHAR
    meaning: 目撃時の状況 (自由記述)。空は NULL (2,009 件)
  - name: latitude
    type: DOUBLE
    meaning: 緯度 (配布元の列名は x(緯度))
  - name: longitude
    type: DOUBLE
    meaning: 経度 (配布元の列名は y(経度))
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点 (経度, 緯度)
---

# 秋田県 クマダスの出没情報 (akita-kumadas-wildlife-sighting)

秋田県自然保護課が県のオープンデータカタログ (<https://ckan.pref.akita.lg.jp/dataset/050008_shizenhogoka_003>) に出している「ツキノワグマ等情報マップシステム『クマダス』データ」の CSV を、GeoParquet にしたもの。配布元は毎月ファイルを上書きするので、ここにあるのは 2026-10-26 に取った 20260930 時点の版だけ。
分析では、クマの出没の通報の時期と場所の偏り、集落や道路からの距離、年ごとの増え方 (2025 年の大量出没) に使う。通報の記録で、個体数の調査ではない。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 24,757 (README と一致)。`id` の重複 0 |
| 日時 | 2022-04-10 14:00〜2026-09-30 22:03 |
| 獣種と種別 | ツキノワグマ 23,306 (目撃 22,109、痕跡(その他) 584、痕跡(食害) 457、人身被害 156)、イノシシ 885、ニホンジカ 566。人身被害は全てクマ |
| 範囲 | 経度 139.70〜140.98、緯度 38.90〜40.51 |
| 点と市町村の面 (`jp-admin-2026-09`) | 24,747 点が秋田県の面に入る。9 点はどの面にも入らない (記録の市町村は男鹿市 4、由利本荘市 2、にかほ市 2、大潟村 1。海岸や八郎潟の面の外とみられる)。1 点 (記録は鹿角市) は青森県新郷村の面に入る。秋田県の面に入って、記録の `municipality` と面の市町村が違うのは 32 点 (秋田市と記録して北秋田市の面に入る 4 点、鹿角市と記録して小坂町の面に入る 3 点など) |
| 2025 年のクマの月別 | 10 月 5,810、11 月 3,333 で、この 2 か月で年の 66% |
| 位置の重なり | クマ 23,306 件の座標は 23,240 か所。2 件が同じ座標の場所は 50、3 件は 6、5 件は 1 か所。住所の文字列は番地の単位 (`〒011-0931 秋田県秋田市将軍野東２丁目１３－１２` など)。代表点への丸めは見えない |
| 熊の年度 (4 月〜翌 3 月) ごとのクマ | 2022 年度 864 (4 月 10 日から)、2023 年度 3,895、2024 年度 1,586、2025 年度 13,592、2026 年度 3,369 (9 月 30 日まで) |
| `【投稿】` | 状況がちょうど `【投稿】` の行は、全獣種で 1,003、クマで 903。`【投稿】` を含む行は、クマで 7,709 |

年別のクマの件数は README の表のとおり (2022 年は 4 月 10 日から、2026 年は 9 月 30 日まで)。

## 気をつけること

- 3 種が 1 つの表に入っている。クマだけなら `species = 'ツキノワグマ'` で絞る。
- 1 行は通報で、同じ個体が何度も通報されうる。件数を個体数として読まない。2025 年の急増は出没の増加と、通報のしやすさや関心の高まりの両方を含みうる。
- 1,003 件 (全獣種) は状況が「【投稿】」だけで、住民の投稿とみられる (配布元は説明していない)。状況の文に「【投稿】」を含む行はクマだけで 7,709 あり、投稿の数を数えるなら、どちらで数えたかを書く。投稿とそれ以外で、場所の確かさが違うかもしれない。
- 場所は通報者が言った住所や目印から付けた点で、精度は書かれていない。点を市町村の面に入れると、32 点が記録と別の市町村に入る。
- 点は、通報された住所や目印に置かれている。クマのいた位置かどうかは未確認。細かい格子 (100 m) に入れても同じ座標の重なりはほとんど無い (上の表) が、点は人の住む場所や道に寄る。
- 配布元は毎月上書きし、欠けた番号 (3,297) の理由も書いていない。後から消された通報がある可能性がある。版をまたいで比べるときは、取った日を書く。
- 他の県のクマの出没データ (`gifu-bear-sighting`、`ishikawa-bear-incident`、`kyoto-bear-sighting` など) とは、集め方、種別、期間が違う。県の間で件数を比べるなら、その違いを先に書く。

## 出典の表示

> 出典：秋田県「ツキノワグマ等情報マップシステム『クマダス』データ」（https://ckan.pref.akita.lg.jp/dataset/050008_shizenhogoka_003）を加工して作成
