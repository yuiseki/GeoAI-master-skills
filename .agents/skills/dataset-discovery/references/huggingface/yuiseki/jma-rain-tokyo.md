---
kind: dataset
id: yuiseki/jma-rain-tokyo
description: 気象庁「過去の気象データ・ダウンロード」から取得した東京都内全31観測所 (気象官署6・アメダス25、島しょ部および廃止観測所を含む) の1974〜2025年の日別降水量 (日合計・日最大1時間・日最大10分間、588,783行) と時間別降水量 (8,660,976行)、および観測所一覧 (31行) の Parquet。品質情報・現象なし情報・均質番号を全て保持している。
url: https://huggingface.co/datasets/yuiseki/jma-rain-tokyo
license: CC BY 4.0 (気象庁ホームページの利用規約は公共データ利用規約第1.0版 [PDL 1.0] に準拠し CC BY 4.0 と互換)。出典の明記と加工の表示が要る
formats:
- Parquet (parquet/stations.parquet, parquet/daily.parquet, parquet/hourly.parquet, parquet/daily_files.parquet, parquet/hourly_files.parquet)
- CSV (配布元の Shift_JIS CSV のまま、raw/2026-10-26/)
crs: null
spatial_coverage: 東京都内の気象庁観測所 31 地点 (本土11地点は東京、練馬、世田谷、江戸川臨海、羽田、府中、調布、八王子、青梅、小沢、小河内。島しょ部20地点は大島、利島、新島、神津島、三宅島、八丈島、青ヶ島、父島、母島、南鳥島など。緯度 24.288〜35.792、経度 139.050〜153.983)
temporal_coverage: 日別は 1974-01-01 〜 2025-12-31 (52年間、本土で1976年以前の値があるのは東京 s47662 のみ)。時間別は各観測所に日別値が存在する年の全時間 (1976-01-01 01時 〜 2026-01-01 00時 JST)
as_of:
  retrieved: 2026-10-26
  huggingface_revision: 4391f7698523f5fd8f7c485a407a20f1545a6fc9
contents:
- 観測所マスタ (31地点の station_id、名前、種別 synop/amedas、緯度・経度、標高、観測終了日、観測要素コード)
- 日別降水量 (588,783行、日降水量、最大1時間降水量、最大10分間降水量とそれぞれの現象なし情報・品質情報・均質番号)
- 時間別降水量 (8,660,976行、1時間ごとの降水量と現象なし情報・品質情報・ファイル内均質番号)
tables:
- name: stations
  read: hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/stations.parquet
  grain: 気象庁の1つの観測所 (気象官署またはアメダス)
  rows: 31
  id:
  - station_id
  no_key:
  - name: station_name
    note: 観測所名 (station_name) は一意ではない。新島 (a1134 [2008年終了] と a1522) および神津島 (a1505 [2006年終了] と a1523) に同名2地点があるため、結合には必ず station_id を使う。また tokyo-flood-record-jp の nro_name / mro_name は東京都建設局の独自雨量観測所名 (丸の内、荒川など) であり、気象庁観測所とは空間距離で対応づける
  columns:
  - name: station_id
    type: VARCHAR
    meaning: 観測所ID (気象官署は `s` + 5桁、アメダスは `a` + 4桁。例は `s47662` 東京、`a1002` 練馬)
  - name: station_name
    type: VARCHAR
    meaning: 観測所名 (全31行で29名称。新島と神津島が2行ずつ)
  - name: kind
    type: VARCHAR
    meaning: 観測所種別 (`synop` 気象官署 6地点、`amedas` アメダス 25地点)
  - name: lat
    type: DOUBLE
    meaning: 緯度 (十進度。気象庁一覧表の0.1分単位の度分から換算、現在の位置のみ)
  - name: lon
    type: DOUBLE
    meaning: 経度 (十進度。現在の位置のみ)
  - name: elevation_m
    type: DOUBLE
    meaning: 標高 (m)
  - name: ended
    type: DATE
    meaning: 観測終了日 (調布 1976-12-13、神津島旧 2006-03-01、三宅島阿古・三宅伊豆 2008-02-20、新島旧 2008-11-18、大島臨時 2014-11-20、大島泉津・大島差木地 2016-11-30)
    missing: NULL が 23 行 (現在も観測継続中)
  - name: kansoku
    type: VARCHAR
    meaning: 観測要素の6桁フラグ (`100000` は雨量のみ観測、`111201` や `111111` は気温・風・日照等も観測)
- name: daily
  read: hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/daily.parquet
  grain: 1つの観測所の1日 (JST)。観測開始前・終了後の日も全期間 (1974〜2025年) の行が作られ、値は NULL になっている
  rows: 588783
  id:
  - station_id
  - date
  join_keys:
  - column: station_id
    type: VARCHAR
    meaning: 観測所ID
    unique: false
    joins:
    - stations.station_id
    - hourly.station_id
  columns:
  - name: station_id
    type: VARCHAR
    meaning: 観測所ID (`stations.station_id` と結合)
  - name: date
    type: DATE
    meaning: 観測日 (JST、1974-01-01 〜 2025-12-31)
  - name: precip_mm
    type: DOUBLE
    meaning: 日降水量 (mm)
    missing: NULL が 233,548 行 (未開設・廃止期間や欠測)
    note: 気象官署 (`synop`) の 0.0 mm には「降水なし (`precip_nophen = 1`)」と「降水があったが 0.0 mm (`precip_nophen = 0`)」の両方がある。アメダスは `precip_nophen` が常に NULL のため区別できない
  - name: precip_nophen
    type: TINYINT
    meaning: 日降水量の現象なし情報 (1が現象なし、0が現象あり。気象官署のみ)
    missing: NULL が 475,288 行 (アメダスは全行 NULL)
  - name: precip_quality
    type: TINYINT
    meaning: 日降水量の品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし)
  - name: precip_homog
    type: TINYINT
    meaning: 日降水量の均質番号 (観測環境・移転等の変化があると番号が増える。練馬 a1002 は 2012-12-26 に 1から2へ変化)
  - name: max1h_mm
    type: DOUBLE
    meaning: 日最大1時間降水量 (mm/h、任意の連続60分間の最大値)
    missing: NULL が 233,574 行
    note: 任意の60分間で測られるため、同日の `hourly.parquet` の正時1時間降水量の最大値より大きくなる日が多い
  - name: max1h_nophen
    type: TINYINT
    meaning: 日最大1時間降水量の現象なし情報
    missing: NULL が 475,317 行
  - name: max1h_quality
    type: TINYINT
    meaning: 日最大1時間降水量の品質情報
  - name: max1h_homog
    type: TINYINT
    meaning: 日最大1時間降水量の均質番号
  - name: max10m_mm
    type: DOUBLE
    meaning: 日最大10分間降水量 (mm/10min)
    missing: NULL が 371,582 行 (アメダスでは2008〜2009年以降のみ記録、東京 s47662 は1974年から記録)
  - name: max10m_nophen
    type: TINYINT
    meaning: 日最大10分間降水量の現象なし情報
    missing: NULL が 475,318 行
  - name: max10m_quality
    type: TINYINT
    meaning: 日最大10分間降水量の品質情報
  - name: max10m_homog
    type: TINYINT
    meaning: 日最大10分間降水量の均質番号
- name: hourly
  read: hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/hourly.parquet
  grain: 1つの観測所の1時間 (JST の正時終了時刻)
  rows: 8660976
  id:
  - station_id
  - time_end
  join_keys:
  - column: station_id
    type: VARCHAR
    meaning: 観測所ID
    unique: false
    joins:
    - stations.station_id
    - daily.station_id
  columns:
  - name: station_id
    type: VARCHAR
    meaning: 観測所ID
  - name: time_end
    type: TIMESTAMP
    meaning: 1時間の終了時刻 (JST。2019-10-12 01時は 10月12日 00時〜01時、2019-10-13 00時は 10月12日 23時〜24時を表す。所属する日付は `CAST(time_end - INTERVAL 1 HOUR AS DATE)`)
  - name: precip_mm
    type: DOUBLE
    meaning: 1時間降水量 (mm)
    missing: NULL が 138,015 行
  - name: precip_nophen
    type: TINYINT
    meaning: 現象なし情報 (気象官署のみ)
    missing: NULL が 5,933,688 行
  - name: precip_quality
    type: TINYINT
    meaning: 品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし)
  - name: precip_homog_in_file
    type: TINYINT
    meaning: 取得年別 CSV 内の均質番号 (年ごとに 1 から振り直されるため、年をまたぐ比較には `daily.precip_homog` を使う)
---

# 気象庁 東京都内観測所の日別・時間別降水量 1974〜2025 (jma-rain-tokyo)

気象庁「過去の気象データ・ダウンロード」(<https://www.data.jma.go.jp/risk/obsdl/index.php>) から、東京都 (都県番号 44) の全 31 観測所について 1974年〜2025年の日別降水量 (`daily.parquet` の日降水量、日最大1時間降水量、日最大10分間降水量) と時間別降水量 (`hourly.parquet` の正時1時間降水量) を取得し、品質情報 (`_quality`)、現象なし情報 (`_nophen`)、均質番号 (`_homog`) を落とさずに Parquet 化したもの。
浸水が生じた日しか載らない浸水実績図 ([tokyo-flood-record-jp](tokyo-flood-record-jp.md)) に対し、こちらは浸水が起きなかった豪雨日を含む全期間・全時間の連続観測値 (分母となる降雨イベント全体) と、2020〜2025年の最新6年間の降雨実績を持つ。

## 本土11観測所と島しょ部20観測所の内訳 (2026-10-27 実測)

| 区分 | `station_id` と観測所名 (括弧内は標高・備考) |
|---|---|
| 23区および周辺 (5地点) | `s47662` 東京 (千代田区、25.2 m、1974〜2025)、`a1002` 練馬 (51.0 m、2012-12-26に移転・均質番号変化)、`a0368` 世田谷 (35.0 m)、`a0370` 江戸川臨海 (5.0 m)、`a0371` 羽田 (6.0 m) |
| 多摩地域 (6地点) | `a1133` 府中 (59.0 m、1976-12-15〜)、`a0367` 調布 (41.0 m、1976-12-13終了)、`a0366` 八王子 (123.0 m)、`a1001` 青梅 (155.0 m)、`a1180` 小沢 (420.0 m、1977-08-02〜)、`a0365` 小河内 (530.0 m) |
| 島しょ部 (20地点) | `s47675` 大島、`a1467` 大島北ノ山、`a1642` 大島臨時 (終了)、`a1643` 大島泉津 (終了)、`a1644` 大島差木地 (終了)、`a1646` 利島、`a1134` 新島 (旧・終了)、`a1522` 新島、`a1505` 神津島 (旧・終了)、`a1523` 神津島、`s47677` 三宅島 (2000〜2005年に噴火欠測410日)、`a1506` 三宅坪田、`a1509` 三宅島阿古 (終了)、`a1525` 三宅伊豆 (終了)、`s47678` 八丈島、`a1468` 八重見ヶ原、`a1648` 青ヶ島、`s47971` 父島、`a1595` 母島、`s47991` 南鳥島 |

## 気をつけること

- ジオメトリ列は無く、`lat`・`lon` 列のみ:
  `stations.parquet` は GeoParquet ではなく、`lat` と `lon` (DOUBLE、度分0.1分単位から十進度へ変換済) を持つ通常の Parquet。空間結合や距離計算では `ST_Point(lon, lat)` で点を作って使う。また移転があった観測所（練馬 `a1002` など）も現在の座標のみが格納されている。
- 時間別 (`hourly`) の `time_end` の日付境界 (24時は翌日 00時):
  気象庁の1時間値は「前の1時間の終了時刻」で記録されるため、たとえば `2019-10-12` の最後の1時間 (23時〜24時) は `time_end = '2019-10-13 00:00:00'` になる。日別表 (`daily`) の `date` と結合・照合するときは、必ず `CAST(time_end - INTERVAL 1 HOUR AS DATE)` を日のキーにする。
- 日最大1時間降水量 (`daily.max1h_mm`) と正時1時間降水量の最大 (`MAX(hourly.precip_mm)`) の違い:
  `daily.max1h_mm` は正時区切り (00分〜00分) ではなく任意の連続60分間の最大値であるため、同じ日の `hourly.precip_mm` の最大値より大きくなる日が多い。
- 観測開始時期と要素の非対称性:
  1974〜1975年に本土で値があるのは `s47662` (東京) のみで、アメダス各局は1976年以降に始まる。また日最大10分間降水量 (`max10m_mm`) は東京 (`s47662`) では1974年からあるが、アメダス各局では2008〜2009年以降にしか入っていない。長期トレンドを見る際は `max1h_mm` または `precip_mm` を使い、観測開始年と品質情報 (`_quality IN (8, 5)`)、均質番号 (`_homog`) を揃える。
- 東京都建設局の雨量観測所 (`tokyo-flood-record-jp`) との違い:
  `tokyo-flood-record-jp` の `nro_name`・`mro_name` に書かれている観測所名（`丸の内`、`荒川`、`千川` など）は東京都建設局の水防災総合情報システムの雨量計であり、気象庁のアメダス名とは異なる。両者を突き合わせる際は、同日の気象庁最寄り観測所（台東区なら `s47662` 東京など）の `daily.max1h_mm` / `precip_mm` と `tokyo-flood-record-jp` の `nro_60min` / `nro_tot` を日付 (`dis_date_s`〜`dis_date_e`) で結合して比較する。

## 出典の表示

> 出典：気象庁ホームページ「過去の気象データ・ダウンロード」（https://www.data.jma.go.jp/risk/obsdl/index.php）を加工して作成
