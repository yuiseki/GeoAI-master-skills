---
kind: dataset
id: yuiseki/tokyo-flood-record-jp
description: 東京都水害リスク情報システムの「浸水実績図データ」(1974〜2019年の43年分、水害統計調査で把握された1箇所あたり浸水面積0.1 ha以上または浸水棟数10棟以上の区域) を集約した GeoParquet。浸水区域ポリゴン 5,845 行とポイント 121 行に、災害名称、発生日、河川名、区市町村、町丁目、浸水面積、床下・床上・半壊・全壊の棟数と世帯数、浸水原因、最寄り雨量観測所および最大時間雨量観測所の総雨量・60分最大雨量を持つ。
url: https://huggingface.co/datasets/yuiseki/tokyo-flood-record-jp
license: CC BY 4.0 (東京都水害リスク情報システム「浸水実績図データ」のページが「クリエイティブ・コモンズ・ライセンス 表示4.0国際」と明記)。出典の明記と加工の表示が要る
formats:
- GeoParquet (parquet/flood_area.parquet と parquet/flood_point.parquet)
- Shapefile の zip 43個 (配布元のまま、raw/2026-10-26/)
crs: EPSG:4612 (JGD2000 の経緯度。元 Shapefile の平面直角座標系第IX系 EPSG:2451 から投影変換済)
spatial_coverage: 東京都 (23区、多摩地域、および大島・神津島・小笠原などの島しょ部を含む。経度 138.99〜142.21、緯度 26.64〜35.84)
temporal_coverage: 1974年 (昭和49年) 〜 2019年 (令和元年) の43年分 (1980, 2012, 2015, 2020〜2022年の zip は配布元一覧に無し)
as_of:
  retrieved: 2026-10-26
  huggingface_revision: 354b0d9f8030347192eaa387500f60da76c07e1a
contents:
- 年別の浸水実績区域ポリゴン (5,845行) とポイント (121行)
- 災害名、開始・終了日、河川名、区市町村、町丁目、浸水原因 (内水、溢水、有堤部溢水など)
- 浸水面積 (ha)、被害棟数・世帯数 (床下、床上、半壊、全壊、合計)
- 自治体最寄り雨量観測所および最大時間雨量観測所の観測所名、総雨量、60分最大雨量
tables:
- name: flood_area
  read: hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet/flood_area.parquet
  grain: 元 Shapefile の1つのポリゴン行。ただし同一の浸水区域 (同じ layer・id・area_no) が複数の離れたポリゴン行に分かれて収録され、それら全ての行にグループ全体の浸水面積 (area) や被害棟数 (tot_bldg) が重複して書かれているケースがある (5,845行に対し layer×id の組は 5,672組)
  rows: 5845
  id:
  - layer
  - row
  no_key:
  - name: code5
    note: 市区町村コードは無く、当時の表記の文字列 (munic) のみ。合併前の旧自治体名 (田無市、保谷市、秋川市、五日市町、羽村町) や表記ゆれ (太田区、世田ヶ谷区) がそのまま入っているため、現代の行政区域と結ぶには空間結合か名寄せ辞書が要る
  - name: unique_id
    note: id 列は1つの Shapefile 内でも一意ではなく、20のレイヤーで同じ id が複数行に現れる。行の一意識別には (layer, row) を使う
  columns:
  - name: year
    type: INTEGER
    meaning: 配布 zip の西暦年 (1974〜2019)
  - name: source_zip
    type: VARCHAR
    meaning: 元の zip ファイル名
  - name: layer
    type: VARCHAR
    meaning: 元の Shapefile レイヤー名 (1979年は2レイヤーあり)
  - name: row
    type: INTEGER
    meaning: レイヤー内の行番号 (0始まり)
  - name: id
    type: INTEGER
    meaning: 水害統計調査票等の整理番号。同一レイヤー内で重複あり (5,845行中 layer×id は 5,672組)
  - name: area_no
    type: INTEGER
    meaning: 水害区域番号
    missing: NULL が 2,403 行 (元データの `****` 等の桁あふれ記号を NULL 化)
  - name: dis_name
    type: VARCHAR
    meaning: 災害名称 (`台風24号`, `集中豪雨` など表記ゆれあり)
    missing: NULL が 13 行
  - name: dis_date_s
    type: DATE
    meaning: 災害開始日
    missing: NULL が 323 行 (元データの `00000000` を NULL 化)
  - name: dis_date_e
    type: DATE
    meaning: 災害終了日
    missing: NULL が 323 行
  - name: river
    type: VARCHAR
    meaning: 河川名 (`神田川`, `隅田川`, `荒川` などのほか、`普通河川`, `河川海岸以外`, `99` を含む)
  - name: munic
    type: VARCHAR
    meaning: 区市町村名 (当時の表記。`田無市` 68行、`保谷市` 51行、`太田区` 22行、`世田ヶ谷区` 10行などを含む)
  - name: district
    type: VARCHAR
    meaning: 町丁目名 (スラッシュ区切りで複数町丁目が入る行が多い。8年分のレイヤーではここが NULL で district0〜district4 に分割格納)
    missing: NULL が 2,166 行
  - name: district0
    type: VARCHAR
    meaning: 分割格納された町丁目名 (その1。他に district1〜district4 あり)
    missing: NULL が 3,681 行
  - name: area
    type: DOUBLE
    meaning: 属性表に記載された浸水面積 (単位 ha)
    note: 同じ (layer, id) に属する複数ポリゴン行にグループ全体の面積が重複記載されていることがあるため、単純合算すると過大になる (SUM(area) は 44,058 ha だが、ポリゴン実面積の合計は 12,927 ha)
  - name: utf_bldg
    type: VARCHAR
    meaning: 床下浸水棟数 (括弧付き表記 `16(3)` 等があるため VARCHAR)
    missing: NULL が 22 行
  - name: utf_house
    type: VARCHAR
    meaning: 床下浸水世帯数
    missing: NULL が 172 行
  - name: otf_bldg
    type: VARCHAR
    meaning: 床上浸水棟数 (括弧付き表記あり)
    missing: NULL が 22 行
  - name: otf_house
    type: VARCHAR
    meaning: 床上浸水世帯数
    missing: NULL が 200 行
  - name: pd_bldg
    type: VARCHAR
    meaning: 半壊棟数
    missing: NULL が 5,747 行
  - name: cd_bldg
    type: VARCHAR
    meaning: 全壊棟数
    missing: NULL が 5,713 行
  - name: tot_bldg
    type: VARCHAR
    meaning: 浸水・被害合計棟数 (5,845行中 42行に `27(3)` のような括弧付き表記あり)
  - name: tot_house
    type: VARCHAR
    meaning: 浸水・被害合計世帯数
    missing: NULL が 153 行
  - name: reason
    type: VARCHAR
    meaning: 浸水原因 (`内水` 4,856行、`溢水` 435行、`有堤部溢水` 90行、`有堤部溢水　内水　窪地浸水` 90行など自由記述の表記ゆれあり)
  - name: nro_name
    type: VARCHAR
    meaning: 当該区市町村の最寄り雨量観測所名
    missing: NULL が 8 行
  - name: nro_tot
    type: VARCHAR
    meaning: 最寄り雨量観測所の総雨量 (mm、文字列)
    missing: NULL が 120 行
  - name: nro_60min
    type: VARCHAR
    meaning: 最寄り雨量観測所の最大時間雨量 (mm/h、5,845行中 81行に括弧付き表記あり)
    missing: NULL が 106 行
  - name: nro_flag
    type: INTEGER
    meaning: 最寄り雨量観測所フラグ
    missing: NULL が 4 行
  - name: mro_name
    type: VARCHAR
    meaning: 当該水害で最大時間雨量を記録した雨量観測所名
    missing: NULL が 96 行
  - name: mro_tot
    type: VARCHAR
    meaning: 最大時間雨量観測所の総雨量 (mm、文字列)
    missing: NULL が 96 行
  - name: mro_60min
    type: VARCHAR
    meaning: 最大時間雨量観測所の最大時間雨量 (mm/h、文字列)
    missing: NULL が 96 行
  - name: geometry
    type: GEOMETRY('EPSG:4612')
    meaning: 浸水実績区域ポリゴン (POLYGON 5,821行、MULTIPOLYGON 24行、ST_IsValid 偽は 0行)
- name: flood_point
  read: hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet/flood_point.parquet
  grain: 1999〜2008年のうち9年分の zip に含まれるポイントレイヤーの1点 (121行に対し layer×id は 75組)
  rows: 121
  id:
  - layer
  - row
  columns:
  - name: year
    type: INTEGER
    meaning: 配布 zip の西暦年 (1999〜2008年のうち9年分)
  - name: layer
    type: VARCHAR
    meaning: 元のポイント Shapefile レイヤー名
  - name: row
    type: INTEGER
    meaning: レイヤー内の行番号
  - name: id
    type: INTEGER
    meaning: 整理番号 (同一レイヤー内で重複あり)
  - name: dis_name
    type: VARCHAR
    meaning: 災害名称
    missing: NULL が 1 行
  - name: dis_date_s
    type: DATE
    meaning: 災害開始日
  - name: river
    type: VARCHAR
    meaning: 河川名
  - name: munic
    type: VARCHAR
    meaning: 区市町村名
  - name: area
    type: DOUBLE
    meaning: 属性記載の浸水面積 (ha)
  - name: tot_bldg
    type: VARCHAR
    meaning: 合計被害棟数
  - name: reason
    type: VARCHAR
    meaning: 浸水原因
  - name: nro_60min
    type: VARCHAR
    meaning: 最寄り観測所の60分最大雨量
  - name: geometry
    type: GEOMETRY('EPSG:4612')
    meaning: 点 (POINT 121行、ST_IsValid 偽は 0行)
---

# 東京都 水害リスク情報システム 浸水実績図データ (tokyo-flood-record-jp)

東京都建設局「水害リスク情報システム」の「浸水実績図データ」(<https://www.suigai-risk.metro.tokyo.lg.jp/shiryoshu/shinsui-chizudata/>) で公開されている 1974年 (昭和49年) 〜 2019年 (令和元年) の43年分の Shapefile zip を、属性を落とさず JGD2000 経緯度 (`EPSG:4612`) の GeoParquet に変換したもの。
水害統計調査（国土交通省の一般統計調査として都および区市町村が実施）によって把握された、1箇所あたりの浸水面積が 0.1 ha 以上、または1箇所あたりの浸水棟数が 10 棟以上の浸水実績区域が収録されている。
計画規模や想定最大規模のシミュレーションである洪水浸水想定区域 ([ksj-a31a-flood-tokyo23](ksj-a31a-flood-tokyo23.md)) とは対照的に、実際にどこで・どの降雨強度で・内水氾濫と外水氾濫（溢水）のどちらが何回起きたかという43年分の記録を扱う。

## 実測 (2026-10-27、DuckDB)

| 項目 | `flood_area` | `flood_point` |
|---|---|---|
| 行数 | 5,845 行 (`POLYGON` 5,821、`MULTIPOLYGON` 24) | 121 行 (`POINT` 121) |
| 無効ジオメトリ (`ST_IsValid = false`) | 0 行 | 0 行 |
| 収録年 | 1974〜2019年のうち43年分 (1980, 2012, 2015年は欠番) | 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2007, 2008年の9年分 |
| 空間範囲 | 経度 138.991〜142.206、緯度 26.642〜35.837 (島しょ部含む) | 経度 139.084〜139.805、緯度 35.545〜35.782 |
| `layer` × `id` のユニーク数 | 5,672 組 (173行は同一 `layer`・`id` の分割ポリゴン) | 75 組 |
| 原因 (`reason`) の内訳上位 | `内水` 4,856行 (83.1%)、`溢水` 435行、`有堤部溢水` 90行、`有堤部溢水　内水　窪地浸水` 90行、`内水　窪地浸水` 83行、`溢水内水` 79行 | `内水` 等 |
| 23区のポリゴン行数上位 | 足立区 645、大田区 486 (+`太田区` 22)、世田谷区 348 (+`世田ヶ谷区` 10)、杉並区 324、文京区 316、中野区 303、江戸川区 287、葛飾区 279、練馬区 277、豊島区 253、品川区 219、新宿区 201、目黒区 139、台東区 133 | - |

## 気をつけること

- 同一イベント・同一区域の分割ポリゴンと属性の重複計上:
  `id` は1つの Shapefile 内でも一意ではなく、さらに同じ調査単位 (`layer`, `munic`, `dis_name`, `dis_date_s`, `district`, `area`, `tot_bldg`) に属する飛び地の浸水区域が異なる `id` や `row` を持つ複数のポリゴン行に分かれて格納されている。このとき、分割された各行にグループ全体の属性浸水面積 (`area`) や被害棟数 (`tot_bldg`, `utf_bldg`, `otf_bldg`) が同じ値で繰り返し入っている場合が多い（例えば台東区の2005年9月4日集中豪雨や2004年台風22号・1981年台風24号など）。そのため、行ごとに `area` や `tot_bldg` を単純に `SUM` すると大幅な重複計上になる（台東区の133ポリゴン行はユニークな調査記録としては37組であり、単純合算すると被害棟数は `25,766棟` となるが重複除去後は `2,473棟` と10.4倍の過大計上になる。他22区の4,617行でも単純合算 `863,819棟` に対し重複除去後は `144,898棟` で6.0倍の差がある。また `flood_area` 全行の `SUM(area)` は `44,058.2 ha` だが、ポリゴン形状の実面積 `SUM(ST_Area_Spheroid(geometry))` は `12,926.9 ha`）。面積を測るときはジオメトリの実面積または `ST_Union_Agg` を使い、被害棟数を集計するときは `(layer, munic, dis_name, dis_date_s, district, area, tot_bldg)` 等で重複行を除いて集計する。
- 棟数・世帯数・雨量列の括弧付き文字列:
  `tot_bldg` (42行)、`otf_bldg`、`utf_bldg`、`nro_60min` (81行) などには `27(3)` や `(213)` のような括弧付き表記が含まれるため、列型は `VARCHAR` になっている。数値として集計する際は `TRY_CAST` だけでなく正規表現 (`regexp_extract(tot_bldg, '^([0-9]+)', 1)`) 等で括弧外の数値と括弧内の扱いを決めて変換する。
- 自治体名 (`munic`) の旧名称と誤記:
  合併前の旧市町村名（`田無市` 68行、`保谷市` 51行 → 現・西東京市、`秋川市` 20行、`五日市町` 12行 → 現・あきる野市、`羽村町` 3行 → 現・羽村市）や、表記ゆれ（`太田区` 22行 → 大田区、`世田ヶ谷区` 10行 → 世田谷区）がある。またポリゴンが区市町村境をまたぐケースが83件あるため、現代の行政区や町丁目・メッシュで集計する際は文字列一致だけでなく空間結合 (`ST_Intersects`) を併用する。
- 町丁目列 (`district` vs `district0`〜`district4`) のスキーマ差:
  43年中35年分は `district` 列にスラッシュ区切り（例: `入谷1丁目/下谷2～3丁目/竜泉1丁目`）で入っているが、8年分のレイヤー（2004年など）では `district` が NULL で `district0`〜`district4` に分かれて格納されている。`COALESCE(district, concat_ws('/', district0, district1, district2, district3, district4))` のように統合して読む。
- 記録の閾値と観測バイアス:
  水害統計調査の基準（原則として1箇所の浸水面積 0.1 ha 以上または浸水棟数 10 棟以上）を満たし都・区市町村が把握した区域のみが載っており、すべての浸水箇所を網羅したものではない。また年代が下るにつれて下水道幹線・調整池の整備によりポリゴン数が減る傾向と、調査・デジタル化方法の変化（1999〜2008年のみ `flood_point` が存在するなど）の両方が含まれる。

## 補足の実測 (2026-10-26、DuckDB 2.0.0)

上の表と重ならない確かめ。組の数は束ね方で変わるので、束ねた列を添える。

| 項目 | 値 |
|---|---|
| 記録の組 | geometry、row、id 以外の全ての属性が同じ行を束ねると 2,255 組。2 行以上の組は 1,004 (4,594 行)、最も多い組は 83 行。組ごとに 1 つ取った `area` の合計は 7,937 ha。束ねる列を (layer、area_no、dis_name、dis_date_s、river、munic、district か district0、area、tot_bldg、tot_house) にすると 2,251 組。上の `layer` × `id` の 5,672 組とは定義が違う |
| `area_no` | 全て 0 か NULL。記録の ID には使えない |
| `area` と面の面積 | 上の 2,251 組ごとに、面の面積 (EPSG:2451) / `area` は中央値 3.18 倍、10% 点 0.76 倍、90% 点 16.9 倍。配布元も、図は記録された場所のおおよそだと書く |
| 面の和集合 | 8,847 ha (面の面積の合計は 12,924 ha) |
| 年をまたいだ重なり | 3,703 行 (63%) の面が、別の年の面と 1 m² を超えて重なる |
| 日付 | NULL 323 行 (配布元の 00000000)。終了が開始より前が 2 行 (1985 年、終了 1960-06-20)。1979 年は 2 つのレイヤーに分かれ、178 行のうち 125 行の日付が NULL |
| 災害 | (年、dis_name、dis_date_s) で 135 組。dis_name は 34 種類で、集中豪雨が 2,620 行 (34 年) |
| `nro_flag` | 0 は区市町村の中の観測所 (4,503 行)、1 はその年に区市町村の中に観測所が無く最寄りを当てた (1,338 行)、NULL 4 行 (配布元の値が * の並び) |
| 雨量の文字列 | `-` と `‐` (U+2010、nro_tot で 224 行) が NULL にされずに残る。nro_tot に `-142` が 2 行 |
| 棟数の合計 | 全て数字の行では、tot_bldg は床下、床上、半壊、全壊の合計と 5,706 行のうち 5,702 行で一致 |
| jp-admin-2026-09 との結合 | 名前で結べるのは 5,659 行 (52 種類)。そのうち面の中の 1 点 (`ST_PointOnSurface`) が同じ名前の面に入るのは 5,586、別の市区町村に入るのは 59、どの面にも入らないのは 14 (jp-admin-2026-09 の面は海を含まない) |
| 点と面の重なり | `flood_point` の 121 のうち 26 は、年、区市町村、開始の日、合計の棟数、町丁目が同じ面の行がある。面と点を足すと同じ浸水を 2 回数えうる |
| 同じ形の面 | 3 組 (1982 年の荒川区、1989 年の杉並区、2004 年の大田区。どれも同じ年の同じレイヤーの中) |

場所ごとの浸水の回数を数えるときは、面を重ねて数え、同じ年の分かれた面を 2 回数えない。記録の数や密度を、浸水の起こりやすさとしてそのまま読まない。記録の付き方は年と区市町村で違う。

## 出典の表示

> 出典：東京都「水害リスク情報システム 浸水実績図データ」（https://www.suigai-risk.metro.tokyo.lg.jp/shiryoshu/shinsui-chizudata/）を加工して作成
