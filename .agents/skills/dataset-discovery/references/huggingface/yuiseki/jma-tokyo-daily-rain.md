---
kind: dataset
id: yuiseki/jma-tokyo-daily-rain
description: 気象庁の東京都の 31 観測所 (気象台 6、アメダス 25、島しょと観測を終えた観測所を含む) の日別の降水量 1974-01-01〜2025-12-31。日の合計、1 時間の最大、10 分間の最大と、品質情報、均質番号、現象なし情報。過去の気象データ・ダウンロードから 2026-10-26 に取得した CSV と、それをまとめた Parquet。
url: https://huggingface.co/datasets/yuiseki/jma-tokyo-daily-rain
license: CC BY 4.0 (気象庁ホームページのコンテンツ利用規約、公共データ利用規約 第1.0版に準拠)。出典の表示と加工の明記が要る
formats:
- Parquet (日別、観測所、取得したファイルの 3 つ)
- CSV (配布元のまま、cp932、raw/2026-10-26/daily/)
crs: 観測所の表の lat と lon は経緯度 (度)。測地系は配布元が書いていない (未確認)
spatial_coverage: 東京都 (気象庁の都道府県番号 44) の観測所。本土 11 (うち 23 区の中は 東京、練馬、世田谷、江戸川臨海、羽田)、島しょ 20
temporal_coverage: 1974-01-01〜2025-12-31 を要求した。値のある期間は観測所ごと (本土のアメダスは 1976 年から)
as_of:
  retrieved: 2026-10-26
  huggingface_revision: 7cd59f3d0b51eb52fcb0c5f3535d0c12d4076d6c
contents:
- 観測所 × 日の降水量の合計、1 時間降水量の最大、10 分間降水量の最大 (mm)
- 値ごとの品質情報、均質番号、現象なし情報 (気象台だけ)
- 観測所の名前、種類、緯度経度、標高、観測終了の日
tables:
- name: daily
  read: hf://datasets/yuiseki/jma-tokyo-daily-rain@7cd59f3d0b51eb52fcb0c5f3535d0c12d4076d6c/parquet/daily.parquet
  grain: 1 つの観測所の 1 日 (日本時間)。要求した全ての日に行があり、観測の前と後の日は値が NULL
  rows: 588783
  id:
  - station_id
  - date
  join_keys:
  - column: station_id
    type: VARCHAR
    meaning: 観測所 ID。気象台は s + 地点番号 5 桁、アメダスは a + 4 桁
    unique: false
    joins:
    - stations.station_id
  - column: date
    type: DATE
    meaning: 日 (日本時間)
    unique: false
    joins:
    - tokyo-flood-record-jp:flood_area.dis_date_s
    note: 浸水実績の災害の開始の日と、日付で結べる。場所は観測所の点で、浸水の場所とは違う
  no_key:
  - name: code5
    note: 市区町村コードは無い。観測所の lat と lon を jp-admin-2026-09 の面に入れて付ける
  columns:
  - name: precip_mm
    type: DOUBLE
    meaning: 日の降水量の合計 (mm)
    missing: NULL は CSV の空欄 (観測の前後、欠測)。0 で埋めていない
  - name: precip_nophen
    type: TINYINT
    meaning: 現象なし情報。1 降水なし、0 降水あり。気象台だけで、アメダスは NULL
  - name: precip_quality
    type: TINYINT
    meaning: 品質情報。8 正常、5 準正常、4 資料不足、2 疑問、1 欠測、0 観測の項目でない
  - name: precip_homog
    type: TINYINT
    meaning: 均質番号。番号が変わったところで観測の環境が変わった。この取得 (1974〜2025 年を 1 回で要求) の中での番号
  - name: max1h_mm
    type: DOUBLE
    meaning: その日の 1 時間降水量の最大 (mm)。_nophen、_quality、_homog の列も同じ形で付く
  - name: max10m_mm
    type: DOUBLE
    meaning: その日の 10 分間降水量の最大 (mm)。アメダスは 2008〜2009 年から
- name: stations
  read: hf://datasets/yuiseki/jma-tokyo-daily-rain@7cd59f3d0b51eb52fcb0c5f3535d0c12d4076d6c/parquet/stations.parquet
  grain: 1 つの観測所
  rows: 31
  id:
  - station_id
  columns:
  - name: station_name
    type: VARCHAR
    meaning: 観測所名。新島と神津島は 2 つの観測所が同じ名前を使う
  - name: kind
    type: VARCHAR
    meaning: synop (気象台) か amedas
  - name: lat
    type: DOUBLE
    meaning: 緯度 (度)。一覧の度と 0.1 分から直した。今の位置で、移転の前の位置は無い
  - name: ended
    type: DATE
    meaning: 観測終了の日。続いている観測所は NULL
  - name: kansoku
    type: VARCHAR
    meaning: 観測する要素の符号 (一覧のまま)。100000 は雨だけの観測所
---

# 気象庁 東京都の日別の降水量 (jma-tokyo-daily-rain)

気象庁の[過去の気象データ・ダウンロード](https://www.data.jma.go.jp/risk/obsdl/index.php)から、東京都の観測所の一覧にある 31 観測所の日別値 (降水量の合計、1 時間降水量の最大、10 分間降水量の最大) を、観測所ごとに 1974-01-01〜2025-12-31 で 1 回ずつ要求して取得したもの。要求の形と CSV の読み方はサービスの reference ([jma-obsdl](../../jma-obsdl.md)) にある。今後、年や要素や時別値を足していく前提のリポジトリで、取得ごとに `raw/<取得日>/` に CSV を残し、Parquet は最新の取得から作り直す。

分析では、浸水実績 (tokyo-flood-record-jp) の災害の日の雨の強さ、雨と浸水の関係のモデルの説明変数に使う。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | daily 588,783 (31 観測所 × 18,993 日)。(station_id、date) の重複 0 |
| CSV との照合 | 変換と別の読み方 (DuckDB の CSV の読み込み) で、観測所ごとに行数、値のある数、3 つの要素の合計が全て一致 |
| HF から読み直し | 固定した版から daily 588,783 行、stations 31 行。東京の CSV の sha256 は手元と一致 |
| 本土の値の始まり | 東京 1974-01-01。アメダスは 1976-01-01 (府中 1976-12-15、小沢 1977-08-02)。調布は 1976-12-13 で終了 |
| 10 分間の最大 | 東京は 1974 年から。本土のアメダスは 2008-03-26〜2009-03-18 から |
| 均質番号 | 練馬が 2012-12-26 に 1 から 2。東京は 1974〜2025 年で 1 のまま |
| 欠測 (品質 1) | 東京 1 日、練馬 5 日など。三宅島は 2000〜2005 年に 410 日 |
| 例 | 2019-10-12 の日降水量 東京 209.5 mm、練馬 282.0 mm |

## 気をつけること

- 観測所は点。23 区の中の観測所は 5 つで、区より細かい場所の雨は分からない。浸水の場所の雨として使うなら、どの観測所の値を当てたか (最寄り、区の中、内挿) を書く。内挿した面は観測ではない。
- 気象台の 0 は、降水なし (`precip_nophen` 1) と、降水ありで 0.0 mm (0) を分けられる。アメダスの 0 は分けられない。
- 均質番号は、この取得の中での番号。別の取得の番号とつながない。番号の変わった前後の値は、そのまま比べない。
- 観測所の位置は今の位置だけ。移転があっても過去の位置は分からない (東京の移転の有無と時期は、このデータからは未確認)。
- 気象庁は過去の値を訂正しうる。同じ要求を後日しても同じ CSV が返る保証は無い。この版の値として引用するときは revision を書く。
- 1974〜1975 年の本土の雨は東京の 1 地点だけ。浸水実績のその 2 年は、雨を細かく当てられない。

## 出典の表示

> 出典：気象庁ホームページ「過去の気象データ・ダウンロード」（https://www.data.jma.go.jp/risk/obsdl/index.php）を加工して作成
