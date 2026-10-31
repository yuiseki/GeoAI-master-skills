---
kind: dataset
id: yuiseki/jma-rain-kanto
description: 気象庁「過去の気象データ・ダウンロード」から取得した関東の4県 (茨城40・埼玉43・千葉45・神奈川46) の全73観測所 (気象官署9・アメダス64、終了した観測所8を含む) の1974-01-01〜2026-09-30の日別降水量 (日合計・日最大1時間・日最大10分間、1,406,418行) と時間別降水量 (29,536,104行)、および観測所一覧 (73行) の Parquet。県ごとに1ファイルで、県を足して育てる。千葉の行は jma-rain-chiba と全て同じ。
url: https://huggingface.co/datasets/yuiseki/jma-rain-kanto
license: CC BY 4.0 (気象庁ホームページの利用規約は公共データ利用規約第1.0版 [PDL 1.0] に準拠し CC BY 4.0 と互換)。出典の明記と加工の表示が要る
formats:
- Parquet (parquet/stations.parquet と parquet/stations/pref=NN.parquet、parquet/daily/pref=NN.parquet、parquet/hourly/pref=NN.parquet、parquet/daily_files/、parquet/hourly_files/)
- CSV (配布元の Shift_JIS CSV のまま、raw/2026-10-30/pref=45/ と raw/2026-10-31/pref=NN/)
crs: null
spatial_coverage: 茨城県 28、埼玉県 15、千葉県 18、神奈川県 12 の気象庁観測所 73 地点 (緯度 34.987〜36.868、経度 138.923〜140.857)。栃木県 (41)、群馬県 (42)、東京都 (44) はこの版に無い
temporal_coverage: 日別は 1974-01-01 〜 2026-09-30 (アメダスは1976年から)。時間別は各観測所に日別値が存在する年の全時間 (1974-01-01 01時 〜 2026-10-01 00時 JST)。2026年10月は含まない
as_of:
  retrieved: 2026-10-31
  huggingface_revision: e7064e30dabf6fd3bd5fa8d5e01d8b63f69a3a5b
contents:
- 観測所マスタ (73地点の station_id、名前、県番号、種別 synop/amedas、緯度・経度、標高、観測終了日、観測要素コード)
- 日別降水量 (1,406,418行、日降水量、最大1時間降水量、最大10分間降水量とそれぞれの現象なし情報・品質情報・均質番号)
- 時間別降水量 (29,536,104行、1時間ごとの降水量と現象なし情報・品質情報・ファイル内均質番号)
tables:
- name: stations
  read: hf://datasets/yuiseki/jma-rain-kanto@e7064e30dabf6fd3bd5fa8d5e01d8b63f69a3a5b/parquet/stations.parquet
  grain: 気象庁の1つの観測所 (気象官署またはアメダス)
  rows: 73
  id:
  - station_id
  columns:
  - name: station_id
    type: VARCHAR
    meaning: 観測所ID (気象官署は `s` + 5桁、アメダスは `a` + 4桁。例は `s47670` 横浜、`a0390` 箱根)
  - name: station_name
    type: VARCHAR
    meaning: 観測所名 (73行で73名称、同名なし)
  - name: pref
    type: BIGINT
    meaning: 気象庁の都府県番号 (40 茨城、43 埼玉、45 千葉、46 神奈川)。日別と時間別の表では TINYINT
  - name: kind
    type: VARCHAR
    meaning: 観測所種別 (`synop` 気象官署 9地点、`amedas` アメダス 64地点)
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
    meaning: 一覧が書く観測終了日
    missing: 65行 NULL (終了した観測所 8 地点だけに値がある)
    note: 堂平 (`a0361`) は一覧では 2000-06-06 だが、日別の最後の値は 2000-04-27 で、翌日からときがわ (`a1497`) の値が始まる。README の終了日は最後の値の日で書かれている
  - name: kansoku
    type: VARCHAR
    meaning: 観測要素の6桁フラグ (`100000` は雨量のみ観測)
- name: daily
  read: hf://datasets/yuiseki/jma-rain-kanto@e7064e30dabf6fd3bd5fa8d5e01d8b63f69a3a5b/parquet/daily/*.parquet
  grain: 1つの観測所の1日 (JST)。観測開始前と終了後の日も全期間 (1974-01-01〜2026-09-30) の行が作られ、値は NULL になっている
  rows: 1406418
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
    missing: NULL が 198,133 行 (茨城 116,128、埼玉 32,693、千葉 22,306、神奈川 27,006。開始前、終了後の日と欠測)
    note: 気象官署 (`synop`) の 0.0 mm には「降水なし (`precip_nophen = 1`)」と「降水があったが 0.0 mm (`precip_nophen = 0`)」の両方がある。アメダスは `precip_nophen` が常に NULL のため区別できない
  - name: precip_nophen
    type: TINYINT
    meaning: 日降水量の現象なし情報 (1が現象なし、0が現象あり。気象官署のみ)
    missing: NULL が 1,233,035 行 (アメダスは全行 NULL)
  - name: precip_quality
    type: TINYINT
    meaning: 日降水量の品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし。全行で 8 が 1,205,455、5 が 1,430、4 が 1,400、1 が 3,682、0 が 194,451)
  - name: precip_homog
    type: TINYINT
    meaning: 日降水量の均質番号 (観測環境の変化で番号が増える。筑波山 1981-08-21、船橋 1999-08-03、香取 1999-10-12、木更津 2006-09-22、我孫子 2010-03-11 に 1 から 2 へ変化)
  - name: max1h_mm
    type: DOUBLE
    meaning: 日最大1時間降水量 (mm/h、任意の連続60分間の最大値と推測、配布元の定義は未確認)
    missing: NULL が 198,163 行
  - name: max1h_nophen
    type: TINYINT
    meaning: 日最大1時間降水量の現象なし情報
  - name: max1h_quality
    type: TINYINT
    meaning: 日最大1時間降水量の品質情報
  - name: max1h_homog
    type: TINYINT
    meaning: 日最大1時間降水量の均質番号
  - name: max10m_mm
    type: DOUBLE
    meaning: 日最大10分間降水量 (mm/10min)
    missing: NULL が 856,212 行 (アメダスでは2008〜2009年以降のみ記録、気象官署は1974年から記録)
  - name: max10m_nophen
    type: TINYINT
    meaning: 日最大10分間降水量の現象なし情報
  - name: max10m_quality
    type: TINYINT
    meaning: 日最大10分間降水量の品質情報
  - name: max10m_homog
    type: TINYINT
    meaning: 日最大10分間降水量の均質番号
  - name: pref
    type: TINYINT
    meaning: 気象庁の都府県番号 (ファイル名の pref=NN と同じ)
- name: hourly
  read: hf://datasets/yuiseki/jma-rain-kanto@e7064e30dabf6fd3bd5fa8d5e01d8b63f69a3a5b/parquet/hourly/*.parquet
  grain: 1つの観測所の1時間 (JST の正時終了時刻)。各観測所に日別値がある年だけ
  rows: 29536104
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
    missing: NULL が 552,884 行
  - name: precip_nophen
    type: TINYINT
    meaning: 現象なし情報 (気象官署のみ)
    missing: NULL が 25,375,860 行
  - name: precip_quality
    type: TINYINT
    meaning: 品質情報 (8が正常、5が準正常、4が資料不足、2が疑問値、1が欠測、0が観測なし)
  - name: precip_homog_in_file
    type: TINYINT
    meaning: 取得年別 CSV 内の均質番号 (年ごとに 1 から振り直されるため、年をまたぐ比較には `daily.precip_homog` を使う)
  - name: pref
    type: TINYINT
    meaning: 気象庁の都府県番号
---

# 気象庁 関東の観測所の日別・時間別降水量 1974〜2026年9月 (jma-rain-kanto)

気象庁「過去の気象データ・ダウンロード」(<https://www.data.jma.go.jp/risk/obsdl/index.php>) から、関東の県ごとに全観測所の 1974-01-01〜2026-09-30 の日別降水量と時間別降水量を取得し、品質情報 (`_quality`)、現象なし情報 (`_nophen`)、均質番号 (`_homog`) を落とさずに Parquet 化したもの。
取得方法も列も [jma-rain-tokyo](jma-rain-tokyo.md)、[jma-rain-chiba](jma-rain-chiba.md) と同じで、`pref` 列が足されている。この版は茨城、埼玉、千葉、神奈川の 4 県で、栃木、群馬、東京は後から足す予定と README に書かれている。神奈川、茨城、埼玉はこのデータセットにしか無い。

## 観測所の内訳 (2026-10-31 実測)

| 県 (`pref`) | 観測所 | 気象官署 | 終了した観測所 (日別の最後の値) |
|---|---:|---|---|
| 茨城 (40) | 28 | 水戸 `s47629`、つくば (館野) `s47646` | 神峰山 1985-05-28、愛宕山 1982-05-12、筑波山 2001-12-06、高萩 2018-11-30、常総 2018-03-15 |
| 埼玉 (43) | 15 | 熊谷 `s47626`、秩父 `s47641` | 堂平 2000-04-27 (翌日からときがわ) |
| 千葉 (45) | 18 | 千葉、銚子、館山、勝浦 | なし |
| 神奈川 (46) | 12 | 横浜 `s47670` | 江ノ島 1992-02-08 (2日後から辻堂) |

## 気をつけること

- ジオメトリ列は無く、`lat`・`lon` 列のみ:
  `stations.parquet` は GeoParquet ではない。空間結合や距離計算では `ST_Point(lon, lat)` で点を作る。移転があっても過去の位置は分からない (現在の座標だけ)。
- 県ごとのファイル:
  日別と時間別は `parquet/daily/pref=NN.parquet` のように県ごとに分かれている。全県を読むときは `daily/*.parquet` で読む。県が足されると、同じ glob で読む行が増える。引用や再現には revision を固定する。
- 時間別の `time_end` の日付境界 (24時は翌日 00時):
  日別表と結合するときは `CAST(time_end - INTERVAL 1 HOUR AS DATE)` を日のキーにする。
- 終了した観測所と後継:
  堂平 (`a0361`) とときがわ (`a1497`)、江ノ島 (`a0391`) と辻堂 (`a1443`) は、値の期間が続いている。長期の比較では、つなぐかどうかを決めて書く。`stations.ended` と最後の値の日は堂平で食い違う (上の表は最後の値の日)。
- 観測開始時期と要素の非対称性:
  1974〜1975年に値があるのは気象官署だけ。日最大10分間降水量は、アメダスでは2008〜2009年以降にしか入っていない。
- 千葉県と東京都と組み合わせるとき:
  千葉の行は [jma-rain-chiba](jma-rain-chiba.md) (版 7a23cd0) と全て同じ (下の実測)。両方を読むと千葉が二重になる。東京都の [jma-rain-tokyo](jma-rain-tokyo.md) (版 4391f76) は 2025-12-31 で終わり、`station_id` はこの版の 73 観測所と重ならない。都県境に近い観測所 (所沢、越谷、日吉、船橋など) は、東京都の浸水実績の最寄りの観測所の候補になりうる。

## 補足の実測 (2026-10-31、DuckDB 1.5.5 以上、固定した版から)

| 項目 | 値 |
|---|---|
| 行 | daily 1,406,418 (73 観測所 × 19,266 日)、hourly 29,536,104。どちらも (station_id, date) と (station_id, time_end) の重複 0 |
| 県ごとの行 | daily 茨城 539,448、埼玉 288,990、千葉 346,788、神奈川 231,192。hourly 茨城 10,345,728、埼玉 6,245,568、千葉 8,025,000、神奈川 4,919,808 |
| jma-rain-chiba との一致 | 千葉の daily 346,788 行、hourly 8,025,000 行、stations 18 行が、`pref` を除いて jma-rain-chiba@7a23cd0 と行ごとに一致 (`EXCEPT ALL` で両方向 0 行) |
| README との食い違い | README は各県で「1〜23 個の時別の値を持つ日は 0」と書くが、NULL でない時別の値を数えると 1〜23 個の日が茨城 1,000、埼玉 590、千葉 653、神奈川 350 日ある (どの日も 24 行はそろっている)。行の数で数えた記述と読める。千葉の 653 日は jma-rain-chiba のカードと同じ |
| 日最大1時間の最大 | 香取 153.0 mm (1999-10-27)、千葉 115.0 mm (2026-08-13)、柿岡 114.5 mm (2011-08-11)、鳩山 111.0 mm (2022-07-12) |
| 日降水量の最大 | 箱根 922.5 mm (2019-10-12)、浦山 635.0 mm、相模湖 595.0 mm、ときがわ 572.0 mm、三峰 549.0 mm (いずれも 2019-10-12) |

気象庁は過去の値を訂正しうるので、引用するときは revision を書く。取得の方法は [jma-obsdl](../../jma-obsdl.md) にある。

## 出典の表示

> 出典：気象庁ホームページ「過去の気象データ・ダウンロード」（https://www.data.jma.go.jp/risk/obsdl/index.php）を加工して作成
