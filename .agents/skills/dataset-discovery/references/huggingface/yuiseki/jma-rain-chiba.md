---
kind: dataset
id: yuiseki/jma-rain-chiba
description: 気象庁「過去の気象データ・ダウンロード」から取得した千葉県内の全18観測所 (気象官署4・アメダス14、終了した観測所なし) の1974-01-01〜2026-09-30の日別降水量 (日合計・日最大1時間・日最大10分間、346,788行) と時間別降水量 (8,025,000行)、および観測所一覧 (18行) の Parquet。jma-rain-tokyo と同じ取得方法・同じ列で、令和8年8月千葉豪雨と9月の大雨を含む2026年9月までを持つ。
url: https://huggingface.co/datasets/yuiseki/jma-rain-chiba
license: CC BY 4.0 (気象庁ホームページの利用規約は公共データ利用規約第1.0版 [PDL 1.0] に準拠し CC BY 4.0 と互換)。出典の明記と加工の表示が要る
formats:
- Parquet (parquet/stations.parquet, parquet/daily.parquet, parquet/hourly.parquet, parquet/daily_files.parquet, parquet/hourly_files.parquet)
- CSV (配布元の Shift_JIS CSV のまま、raw/2026-10-30/pref=45/)
crs: null
spatial_coverage: 千葉県内の気象庁観測所 18 地点 (気象官署は銚子、館山、勝浦、千葉。アメダスは香取、我孫子、東庄、成田、茂原、木更津、鋸南、鴨川、佐倉、横芝光、大多喜、船橋、牛久、坂畑。緯度 34.987〜35.863、経度 139.837〜140.857)
temporal_coverage: 日別は 1974-01-01 〜 2026-09-30 (アメダスは1976年から、船橋・牛久・坂畑は1978年1月から)。時間別は各観測所に日別値が存在する年の全時間 (1974-01-01 01時 〜 2026-10-01 00時 JST)。2026年10月は含まない
as_of:
  retrieved: 2026-10-31
  huggingface_revision: 7a23cd0b738c016c243863903b6bdafc7963ab06
contents:
- 観測所マスタ (18地点の station_id、名前、県番号、種別 synop/amedas、緯度・経度、標高、観測終了日、観測要素コード)
- 日別降水量 (346,788行、日降水量、最大1時間降水量、最大10分間降水量とそれぞれの現象なし情報・品質情報・均質番号)
- 時間別降水量 (8,025,000行、1時間ごとの降水量と現象なし情報・品質情報・ファイル内均質番号)
tables:
- name: stations
  read: hf://datasets/yuiseki/jma-rain-chiba@7a23cd0b738c016c243863903b6bdafc7963ab06/parquet/stations.parquet
  grain: 気象庁の1つの観測所 (気象官署またはアメダス)
  rows: 18
  id:
  - station_id
  columns:
  - name: station_id
    type: VARCHAR
    meaning: 観測所ID (気象官署は `s` + 5桁、アメダスは `a` + 4桁。例は `s47682` 千葉、`a1241` 坂畑)
  - name: station_name
    type: VARCHAR
    meaning: 観測所名 (18行で18名称、同名なし)
  - name: pref
    type: TINYINT
    meaning: 気象庁の都府県番号 (全行 45)
  - name: kind
    type: VARCHAR
    meaning: 観測所種別 (`synop` 気象官署 4地点、`amedas` アメダス 14地点)
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
    meaning: 観測終了日
    missing: 全18行 NULL (終了した観測所は一覧に無い)
  - name: kansoku
    type: VARCHAR
    meaning: 観測要素の6桁フラグ (`100000` は雨量のみ観測で東庄、鋸南、大多喜。`111000`、`111201`、`111111` は気温・風・日照等も観測)
- name: daily
  read: hf://datasets/yuiseki/jma-rain-chiba@7a23cd0b738c016c243863903b6bdafc7963ab06/parquet/daily.parquet
  grain: 1つの観測所の1日 (JST)。観測開始前の日も全期間 (1974-01-01〜2026-09-30) の行が作られ、値は NULL になっている
  rows: 346788
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
    meaning: 観測日 (JST、1974-01-01 〜 2026-09-30)
  - name: precip_mm
    type: DOUBLE
    meaning: 日降水量 (mm)
    missing: NULL が 22,306 行 (開始前の日と欠測。成田 a0378 は1978〜2002年に値が無い)
    note: 気象官署 (`synop`) の 0.0 mm には「降水なし (`precip_nophen = 1`、35,164日)」と「降水があったが 0.0 mm (`precip_nophen = 0`、15,679日)」の両方がある。アメダスは `precip_nophen` が常に NULL のため区別できない
  - name: precip_nophen
    type: TINYINT
    meaning: 日降水量の現象なし情報 (1が現象なし、0が現象あり。気象官署のみ)
    missing: NULL が 269,735 行 (アメダスは全行 NULL)
  - name: precip_quality
    type: TINYINT
    meaning: 日降水量の品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし。全行で 8 が 323,805、5 が 352、4 が 325、1 が 659、0 が 21,647)
  - name: precip_homog
    type: TINYINT
    meaning: 日降水量の均質番号 (観測環境の変化で番号が増える。香取 1999-10-12、我孫子 2010-03-11、木更津 2006-09-22、船橋 1999-08-03 に 1 から 2 へ変化)
  - name: max1h_mm
    type: DOUBLE
    meaning: 日最大1時間降水量 (mm/h、任意の連続60分間の最大値と推測、配布元の定義は未確認)
    missing: NULL が 22,341 行
    note: 同じ日の `hourly.parquet` の正時1時間降水量の最大値より大きい日が 39,076 日、小さい日が 7 日
  - name: max1h_nophen
    type: TINYINT
    meaning: 日最大1時間降水量の現象なし情報
    missing: NULL が 269,772 行
  - name: max1h_quality
    type: TINYINT
    meaning: 日最大1時間降水量の品質情報
  - name: max1h_homog
    type: TINYINT
    meaning: 日最大1時間降水量の均質番号
  - name: max10m_mm
    type: DOUBLE
    meaning: 日最大10分間降水量 (mm/10min)
    missing: NULL が 177,118 行 (アメダスでは2008〜2009年以降のみ記録、気象官署4地点は1974年から記録)
  - name: max10m_nophen
    type: TINYINT
    meaning: 日最大10分間降水量の現象なし情報
    missing: NULL が 269,777 行
  - name: max10m_quality
    type: TINYINT
    meaning: 日最大10分間降水量の品質情報
  - name: max10m_homog
    type: TINYINT
    meaning: 日最大10分間降水量の均質番号
  - name: pref
    type: TINYINT
    meaning: 気象庁の都府県番号 (全行 45)
- name: hourly
  read: hf://datasets/yuiseki/jma-rain-chiba@7a23cd0b738c016c243863903b6bdafc7963ab06/parquet/hourly.parquet
  grain: 1つの観測所の1時間 (JST の正時終了時刻)。各観測所に日別値がある年だけ
  rows: 8025000
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
    meaning: 1時間の終了時刻 (JST。2026-08-13 20時は 19時〜20時、2026-08-14 00時は 8月13日 23時〜24時を表す。所属する日付は `CAST(time_end - INTERVAL 1 HOUR AS DATE)`)
  - name: precip_mm
    type: DOUBLE
    meaning: 1時間降水量 (mm)
    missing: NULL が 241,954 行
  - name: precip_nophen
    type: TINYINT
    meaning: 現象なし情報 (気象官署のみ)
    missing: NULL が 6,176,286 行
  - name: precip_quality
    type: TINYINT
    meaning: 品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし)
  - name: precip_homog_in_file
    type: TINYINT
    meaning: 取得年別 CSV 内の均質番号 (年ごとに 1 から振り直されるため、年をまたぐ比較には `daily.precip_homog` を使う)
  - name: pref
    type: TINYINT
    meaning: 気象庁の都府県番号 (全行 45)
---

# 気象庁 千葉県内観測所の日別・時間別降水量 1974〜2026年9月 (jma-rain-chiba)

気象庁「過去の気象データ・ダウンロード」(<https://www.data.jma.go.jp/risk/obsdl/index.php>) から、千葉県 (都府県番号 45) の全 18 観測所について 1974-01-01〜2026-09-30 の日別降水量と時間別降水量を取得し、品質情報 (`_quality`)、現象なし情報 (`_nophen`)、均質番号 (`_homog`) を落とさずに Parquet 化したもの。
[jma-rain-tokyo](jma-rain-tokyo.md) と取得方法も列も同じで、`pref` 列が足されている。東京の版が 2025年で止まるのに対し、こちらは令和8年8月千葉豪雨と 2026年9月の大雨を含めるために 2026年9月まで取っている。2026年10月は、月が終わる前の要求が気象庁のフォームでエラーになったため含まない。

## 観測所の内訳 (2026-10-31 実測)

| 区分 | `station_id` と観測所名 (括弧内は標高、日別値の始まり) |
|---|---|
| 気象官署 (4地点) | `s47682` 千葉 (3.5 m、1974)、`s47648` 銚子 (20.1 m、1974)、`s47672` 館山 (5.8 m、1974)、`s47674` 勝浦 (11.9 m、1974) |
| 北西部 (5地点) | `a1236` 船橋 (28 m、1978-01-10)、`a0376` 我孫子 (20 m、1976)、`a0916` 佐倉 (5 m、1976)、`a0378` 成田 (41 m、1976、1978〜2002年は欠け)、`a0375` 香取 (37 m、1976) |
| 東部 (3地点) | `a0377` 東庄 (52 m、1976、雨のみ)、`a1003` 横芝光 (5 m、1976)、`a0381` 茂原 (11 m、1976) |
| 南部・房総 (6地点) | `a0382` 木更津 (60 m、1976)、`a1238` 牛久 (30 m、1978-01-11)、`a1241` 坂畑 (120 m、1978-01-12)、`a1004` 大多喜 (70 m、1976、雨のみ)、`a0383` 鋸南 (10 m、1976、雨のみ)、`a0384` 鴨川 (5 m、1976) |

区分はこのカードでの便宜の分け方で、気象庁の区分ではない。

## 気をつけること

- ジオメトリ列は無く、`lat`・`lon` 列のみ:
  `stations.parquet` は GeoParquet ではない。空間結合や距離計算では `ST_Point(lon, lat)` で点を作る。移転があっても過去の位置は分からない (現在の座標だけ)。
- 時間別の `time_end` の日付境界 (24時は翌日 00時):
  日別表と結合するときは `CAST(time_end - INTERVAL 1 HOUR AS DATE)` を日のキーにする。こうすると、24 時間の値と日別値がそろう 323,829 日のうち 323,828 日で、時別の合計が日別の合計と一致する (残る 1 日は勝浦で 0.5 mm の差)。
- 成田 (`a0378`) の長い欠け:
  1978〜2002年に日別値が無い (記録の期間内で 9,122 日)。ほかの観測所の欠けは最大 285 日 (東庄)。成田を長期の比較に使うときは、この期間を分けて扱う。
- 観測開始時期と要素の非対称性:
  1974〜1975年に値があるのは気象官署 4 地点だけ。日最大10分間降水量は、アメダスでは2008〜2009年以降にしか入っていない。
- 東京と組み合わせるとき:
  東京都の [jma-rain-tokyo](jma-rain-tokyo.md) (版 4391f76) は 2025-12-31 で終わる。両方を縦に積むときは期間をそろえ、`station_id` が県をまたいで重ならないこと (2026-10-31 時点で重なりなし) を確かめる。浸水実績の [tokyo-flood-record-jp](tokyo-flood-record-jp.md) は東京都だけで、千葉県の浸水の記録はカタログに無い。

## 補足の実測 (2026-10-31、DuckDB 1.5.5 以上、固定した版から)

| 項目 | 値 |
|---|---|
| 行 | daily 346,788 (18 観測所 × 19,266 日)、hourly 8,025,000。どちらもキーの重複 0 |
| 時別の欠け | 観測所 × 年の全てで、時間の数が 8,760 (閏年は 8,784、2026年は 6,552) |
| 時別と日別 | 上の 323,828 / 323,829 日の一致。時別の値が 1 つも無く日別も NULL の日が 9,893 日 |
| README との食い違い | README は「1〜23 個の時別の値を持つ日は無い」と書くが、NULL でない時別の値を数えると 1〜23 個の日が 653 日ある (どの日も 24 行はそろっていて、日別の値はある)。行の数で数えた記述と読める |
| 均質番号 | 日別の均質番号が 2 つあるのは香取、我孫子、木更津、船橋の 4 地点 |
| 例 | 2026-08-13 千葉 日降水量 351.0 mm、日最大1時間 115.0 mm。2026-09-21 坂畑 375.0 mm、牛久 341.0 mm、茂原 309.5 mm、千葉 309.5 mm |
| 日最大1時間の最大 | 香取 153.0 mm (1999-10-27)、千葉 115.0 mm (2026-08-13)、大多喜 109.5 mm (2023-09-08) |

README が挙げる出来事 (令和8年8月千葉豪雨、令和8年台風第25号、北印旛沼の堤防決壊) の説明は、それぞれの出典にあり、このデータには含まれない。ここにあるのは観測所の雨量だけで、どの日がどの出来事かの対応も無い。気象庁は過去の値を訂正しうるので、引用するときは revision を書く。取得の方法は [jma-obsdl](../../jma-obsdl.md) にある。

## 出典の表示

> 出典：気象庁ホームページ「過去の気象データ・ダウンロード」（https://www.data.jma.go.jp/risk/obsdl/index.php）を加工して作成
