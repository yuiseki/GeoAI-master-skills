---
kind: dataset
id: yuiseki/mlit-1km-fromto-2022-01
description: 国土交通省の「全国の人流オープンデータ」。1 km メッシュごとと市区町村ごとの滞在人口 (1 か月の 1 日あたりの平均) を、2019-01〜2021-12 の月別、平日と休日、昼と深夜と終日に分けた表。配布元の CSV を種類ごとの Parquet にしたもの。
url: https://huggingface.co/datasets/yuiseki/mlit-1km-fromto-2022-01
card_revision: 2424a9d9a0518f5575f0af54602eb428ca6d97b2
license: CC BY 4.0 (元は「全国の人流オープンデータ利用規約」。政府標準利用規約 2.0 に準拠し、CC BY 4.0 と互換)。出典の表示と、加工したことの明記が要る
formats:
- Parquet (表ごとに 1 ファイル)
- CSV (配布元の zip、raw/ の下)
crs: OGC:CRS84 (attribute_mesh1km の geometry だけ。配布元の定義書は WGS84 と書く。ほかの表は座標を持たない)
spatial_coverage: 日本全国の 47 都道府県。行があるのは滞在人口が 10 人以上のメッシュと市区町村だけ
temporal_coverage: 2019-01〜2021-12 の 36 か月、月ごと。日ごと、時間ごとの値は無い。配布元のファイルは 2022-01-14 以降に変わっていない (カードによる)
as_of:
  period_start: 2019-01
  period_end: 2021-12
  files_last_changed: 2022-01-14
  fetched: 2026-10-02
contents:
- 1 km メッシュ (3 次メッシュ) ごとの月別の滞在人口
- 市区町村ごとの月別の滞在人口を、居住地の 4 区分 (同じ市区町村、同じ都道府県、同じ地方ブロック、それ以外) に分けたもの
- メッシュの中心と範囲の経度緯度、所属の都道府県と市区町村 (2019 年版と 2020 年版)
- 都道府県と市区町村のコードと名前、地方ブロックのマスタ (2019 年版と 2020 年版)
tables:
- name: monthly_mdp_mesh1km
  read: hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/monthly_mdp_mesh1km.parquet
  grain: メッシュ × 年月 × dayflag × timezone。10 人未満の組は行が無い
  rows: 38079507
  id:
  - mesh1kmid
  - year
  - month
  - dayflag
  - timezone
  join_keys:
  - column: mesh1kmid
    type: VARCHAR
    meaning: 8 桁の 3 次メッシュのコード (JIS の標準地域メッシュ)。国勢調査のメッシュと同じ書式
    unique: false
    joins:
    - attribute_mesh1km.mesh1kmid
    - estat-census-mesh-2020:T001140.KEY_CODE
  - column: citycode
    type: VARCHAR
    meaning: 5 桁の市区町村コード。政令指定都市は区のコードで、親の市のコードは出てこない
    unique: false
    joins:
    - prefcode_citycode_master.citycode
    - jp-admin-2026-09:municipalities.code5
  - column: prefcode
    type: VARCHAR
    meaning: 2 桁の都道府県コード (文字列)
    unique: false
    joins:
    - regioncode_master.prefcode
    - jp-admin-2026-09:prefectures.pref_code
  no_key:
  - name: geometry
    note: 面を持たない。attribute_mesh1km の geometry を mesh1kmid で結ぶか、コードから計算する
  columns:
  - name: year
    type: VARCHAR
    meaning: 年 ('2019'、'2020'、'2021')
  - name: month
    type: VARCHAR
    meaning: 月 ('01'〜'12'。0 で埋めた 2 桁の文字列)
  - name: dayflag
    type: VARCHAR
    meaning: '0 は休日、1 は平日、2 は全日'
    note: 全日は休日と平日の和ではない。0 と 1 と 2 が揃う組の全て (11,291,869 組) で、2 の値は 0 と 1 の間にある (実測)
  - name: timezone
    type: VARCHAR
    meaning: 0 は昼 (11 時台〜14 時台の平均)、1 は深夜 (1 時台〜4 時台の平均)、2 は終日 (0 時台〜23 時台の平均)
    note: 終日は昼と深夜から作れない。和に一致するのは 974 組だけで、0 と 1 の間に入るのも 86% (実測)
  - name: population
    type: INTEGER
    meaning: 滞在人口。1 か月の 1 日あたりの平均の換算人口 (定義書による)。最小 10
    missing: 10 人未満は行が出ない。行が無いことは 0 ではなく、0〜9 人のどれか
- name: monthly_fromto_city
  read: hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/monthly_fromto_city.parquet
  grain: 滞在先の市区町村 × 年月 × dayflag × timezone × 居住地の区分 (from_area)。10 人未満の組は行が無い
  rows: 2340980
  id:
  - citycode
  - year
  - month
  - dayflag
  - timezone
  - from_area
  join_keys:
  - column: citycode
    type: VARCHAR
    meaning: 滞在先の 5 桁の市区町村コード。政令指定都市は区
    unique: false
    joins:
    - prefcode_citycode_master.citycode
    - jp-admin-2026-09:municipalities.code5
  - column: prefcode
    type: VARCHAR
    meaning: 滞在先の 2 桁の都道府県コード
    unique: false
    joins:
    - regioncode_master.prefcode
  no_key:
  - name: from_citycode
    note: 居住地の市区町村は無い。from_area の 4 区分だけ。市区町村の間の OD 行列は作れない
  columns:
  - name: from_area
    type: VARCHAR
    meaning: 居住地の区分。0 は同じ市区町村、1 は同じ都道府県の別の市区町村、2 は同じ地方ブロックの別の都道府県、3 は別の地方ブロック
    missing: 10 人未満の区分は行が無い。4 区分が揃う組は 614,316 組のうち 512,722 組
  - name: population
    type: INTEGER
    meaning: 滞在人口 (1 日あたりの平均)。最小 10
  - name: dayflag
    type: VARCHAR
    meaning: monthly_mdp_mesh1km と同じ
  - name: timezone
    type: VARCHAR
    meaning: monthly_mdp_mesh1km と同じ
- name: attribute_mesh1km
  read: hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/attribute_mesh1km.parquet
  grain: 版 (2019、2020) × メッシュ。各版 387,500 メッシュ
  rows: 775000
  id:
  - version
  - mesh1kmid
  join_keys:
  - column: mesh1kmid
    type: VARCHAR
    meaning: 8 桁の 3 次メッシュのコード。版の中では一意
    unique: false
    joins:
    - monthly_mdp_mesh1km.mesh1kmid
    - estat-census-mesh-2020:T001140.KEY_CODE
  - column: version
    type: VARCHAR
    meaning: 版 ('2019' か '2020')。結ぶ前にどちらかに絞る
    unique: false
  columns:
  - name: geometry
    type: GEOMETRY('OGC:CRS84') (DuckDB 2.0.0 で読んだとき)
    meaning: lon_min、lat_min、lon_max、lat_max から作った矩形 (配布元には無い列)。775,000 行全てで範囲の矩形と一致し、無効な面は 0
  - name: lon_center
    type: VARCHAR
    meaning: 中心の経度。lat_center、lon_min、lat_min、lon_max、lat_max も同じく文字列。数として使うには cast する
  - name: citycode
    type: VARCHAR
    meaning: メッシュを割り当てた市区町村 (1 メッシュに 1 つ)。2019 年版と 2020 年版で違うのは 70 メッシュ
- name: prefcode_citycode_master
  read: hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/prefcode_citycode_master.parquet
  grain: 版 × 市区町村。各版 1,896
  rows: 3792
  id:
  - version
  - citycode
  join_keys:
  - column: citycode
    type: VARCHAR
    meaning: 5 桁の市区町村コード
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.code5
  columns:
  - name: cityname
    type: VARCHAR
    meaning: 市区町村の名前。2019 年版は東京の特別区を「東京２３区千代田区」のように書く
- name: regioncode_master
  read: hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/regioncode_master.parquet
  grain: 版 × 都道府県。各版 47
  rows: 94
  id:
  - version
  - prefcode
  join_keys:
  - column: prefcode
    type: VARCHAR
    meaning: 2 桁の都道府県コード
    unique: false
    joins:
    - jp-admin-2026-09:prefectures.pref_code
  columns:
  - name: regioncode
    type: VARCHAR
    meaning: 地方ブロック ('01' 北海道〜'10' 沖縄の 10)。from_area の 2 と 3 はこの区分による。2 つの版は同じ
---

# 全国の人流オープンデータ (mlit-1km-fromto-2022-01)

国土交通省 不動産・建設経済局 情報活用推進課が G 空間情報センターで公開している「全国の人流オープンデータ（1kmメッシュ、市区町村単位発地別）」。1 km メッシュと市区町村ごとに、その月に平均して 1 日に何人がいたかを、平日と休日、昼と深夜と終日に分けて出している。元は Agoop 社の SDK を組み込んだスマートフォンのアプリの GPS の位置を、日本の総人口の規模に拡大推計し、滞在時間で按分した換算人口 (定義書による)。数えた人数ではなく推計値。

市区町村の表 (`monthly_fromto_city`) は、滞在先の市区町村ごとに、居住地を 4 つの区分に分けた人数を持つ。居住地の市区町村そのものは無い。

## どこから読むか

Hugging Face の `yuiseki/mlit-1km-fromto-2022-01`。版 2424a9d に固定して読む。

```
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/monthly_mdp_mesh1km.parquet       104 MB、38,079,507 行
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/monthly_fromto_city.parquet       2,340,980 行
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/attribute_mesh1km.parquet         775,000 行 (面つき)
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/prefcode_citycode_master.parquet  3,792 行
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/regioncode_master.parquet         94 行
hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/raw/                                      配布元の zip、license.pdf、opendatadefinition.pdf (定義書)、MANIFEST.sha256
```

- カード: <https://huggingface.co/datasets/yuiseki/mlit-1km-fromto-2022-01>
- 取得と変換のコード: <https://github.com/yuiseki/mlit-1km-fromto-2022-01>
- 配布元: <https://www.geospatial.jp/ckan/dataset/mlit-1km-fromto>
- メッシュの表は、都道府県、年、月の順に並べてあり (カードによる)、380 の row group に分かれる。`prefcode`、`year`、`month` で絞ると、読む量が減る。
- 出典の表示: 利用規約 (`raw/license.pdf`、令和 3 年 1 月 27 日) は、出典を「出典：「全国の人流オープンデータ」（国土交通省）（https://www.geospatial.jp/ckan/dataset/mlit-1km-fromto）」と書くよう求める。加工したなら、それとは別に加工したことを書く (記載例は「「全国の人流オープンデータ」（国土交通省）（https://www.geospatial.jp/ckan/dataset/mlit-1km-fromto）を加工して作成」)。加工したものを国が作ったように見せない。この Parquet は配布元の CSV を加工したもので、`LICENSE` に加工の内容が日本語で書いてある。規約は政府標準利用規約 2.0 に準拠し、CC BY 4.0 に従って使ってもよいと書いてある。

## 実測

2026-10-23 に、版 2424a9d の Parquet を落として DuckDB 2.0.0 で数えた。

| 項目 | 値 |
|---|---|
| 行数 | メッシュ 38,079,507、市区町村 2,340,980、メッシュ属性 775,000 (版ごとに 387,500)、市区町村マスタ 3,792 (版ごとに 1,896)、地方ブロックのマスタ 94 (版ごとに 47) |
| 期間 | 2019-01〜2021-12。3 年とも 12 か月ある。47 都道府県の全てが、メッシュの表と市区町村の表の両方で 36 か月を持つ |
| 重複 | メッシュの表は (`mesh1kmid`、`year`、`month`、`dayflag`、`timezone`) で重複なし。市区町村の表は (`citycode`、`year`、`month`、`dayflag`、`timezone`、`from_area`) で重複なし |
| 欠け | 全ての列で NULL は 0。`population` の最小は両方の表で 10。0 の行は無い |
| 型 | `population` だけが INTEGER。ほかは全て VARCHAR (`month` は `'01'`、`prefcode` は `'01'`、`citycode` は `'01101'`)。メッシュ属性の経度緯度も文字列 |
| メッシュ | 全て 8 桁の数字。メッシュの表に出るのは 245,770 メッシュで、全てメッシュ属性にある。メッシュ属性の 387,500 のうち 141,730 は一度も行が無い |
| 1 か月の行 | 全日 (`dayflag` 2) かつ終日 (`timezone` 2) で 2019-01 は 124,391 メッシュ。36 か月全てに行があるメッシュは、行が一度でもある 180,692 のうち 84,917 |
| 全国の合計 | 2019-01 の全日で、メッシュの表の合計は昼 126,861,291、深夜 126,939,332、終日 126,870,298。市区町村の表は 127,094,529、127,094,440、127,094,519。どの組でも日本の人口の規模になる |
| 市区町村 | メッシュの表に 1,896 種類、市区町村の表に 1,900 種類 |
| 居住地の区分 | `from_area` の行は 0 が 612,951、1 が 612,623、2 が 525,560、3 が 589,846 |

### メッシュのコード

`mesh1kmid` は、JIS の標準地域メッシュの 3 次メッシュのコード (8 桁) で、`estat-census-mesh-2020` の `KEY_CODE` と同じ書式。コード `abcdefgh` の南西の角は、緯度 `ab / 1.5 + e * 5 / 60 + g * 30 / 3600`、経度 `cd + 100 + f * 7.5 / 60 + h * 45 / 3600` で、大きさは緯度 1/120 度、経度 1/80 度。メッシュ属性の 2020 年版の 387,500 行で、この式の範囲と `lon_min` などの差は最大で経度 0.000006 度、緯度 0.0000018 度 (1 m 未満。値が 6〜7 桁に丸めてあるため)。5 桁目と 6 桁目が 8 以上のコードは無い。

面は、`attribute_mesh1km` の `geometry` (矩形、`GEOMETRY('OGC:CRS84')`) を使うか、上の式で作る。東京駅を含む `53394611` は、両方の版で 139.762497〜139.774994、35.6749992〜35.6833344 の矩形で、国勢調査のカードが同じ式で求めた範囲と一致する。メッシュ属性の範囲は、経度 122.925〜153.9875、緯度 20.4167〜45.5583 (沖ノ鳥島と南鳥島を含む)。

### 国勢調査のメッシュとの結合

`estat-census-mesh-2020` の `T001140` の `KEY_CODE` (176,964 種類、VARCHAR) と、文字列のまま結べる。

- 国勢調査のメッシュ 176,964 のうち、168,777 はこのデータに一度でも行がある。残る 8,187 は一度も行が無い。この 8,187 の国勢調査の人口は合計 65,473 人、最大 134 人、中央値 5 人で、人の少ないメッシュが 10 人未満で落ちたと考えられる。
- 国勢調査のメッシュは全て、メッシュ属性 (2020 年版) にある。
- このデータの 245,770 メッシュのうち 76,993 は、国勢調査に行が無い (住む人のいないメッシュ)。
- 国勢調査は都道府県の境をまたぐメッシュを都道府県ごとに 2 行に分けるが、このデータは 1 メッシュを 1 つの都道府県と市区町村に割り当てる。国勢調査で 2 行あるメッシュのうち 887 がこのデータにあり、どれも `prefcode` は 1 つだけ。

### 市区町村のコード

`jp-admin-2026-09` の `municipalities.code5` (VARCHAR) と、文字列のまま結べる。

- メッシュの表の 1,896 種類のうち 1,888、市区町村の表の 1,900 種類のうち 1,892 が `code5` に一致した。
- 一致しないのは 8 つ。浜松市の 7 区 (`22131`〜`22137`、中区など) は `jp-admin-2026-09` に無く、そちらには `22138` 中央区、`22139` 浜名区、`22140` 天竜区がある。7 区と 3 区で数が違い、コードを 1 対 1 には読み替えられない。面で結ぶ。もう 1 つは 2019 年の那珂川町 (`40305`)。
- 政令指定都市は区のコードで出る。親の市のコード (`01100` 札幌市、`14100` 横浜市など) は、どちらの表にも 1 行も無い。`jp-admin-2026-09` の区の行 (`ward` が空でない) のうち 168 がこのデータに出る。親の市と結ぶなら、区を親にまとめてから結ぶ。東京の特別区は `13101`〜`13123` で、`jp-admin-2026-09` では `ward` が空の行。
- `jp-admin-2026-09` の `ward` が空の行で、メッシュの表に出ないのは 27。20 の政令指定都市の親、北方領土の 6 村 (`01695`〜`01700`)、野迫川村 (`29447`)。

## 気をつけること

- 10 人未満は出ない。行が無いことは 0 ではない。メッシュを格子として使うなら、メッシュ属性から全メッシュを作り、無い行は「10 人未満」として扱う (0 で埋めると、0〜9 人を 0 と書くことになる)。月によって出たり消えたりするメッシュが多く、全日・終日で 36 か月全てに行があるのは、一度でも行があるメッシュの半分に満たない (84,917 / 180,692)。メッシュごとの時系列は、欠けた月を含む前提で扱う。
- `population` は、その月の 1 日あたりの平均の人数 (定義書による)。月の延べ人数ではない。
- `dayflag` と `timezone` は内訳ではない。全日 (`dayflag` 2) と終日 (`timezone` 2) は別の集計で、足すと二重に数える。全国の合計はどの組でも約 1.27 億人で、9 つの組を全部足した 41,119,094,290 (メッシュの表の全行の和) には意味が無い。表を読むときは `dayflag` と `timezone` を 1 つずつ選ぶ。
- 終日 (`timezone` 2) は 0 時台〜23 時台の平均で、昼と深夜から作れない。3 つの値が揃う 10,814,292 組で、終日が昼と深夜の和に一致するのは 974 組、昼と深夜の間に入るのは 9,283,562 組 (86%)。残りは両方より大きいか小さい。全日 (`dayflag` 2) は、3 つが揃う 11,291,869 組の全てで休日と平日の間にあり、和に一致する組は無い。日数で重みを付けた平均と考えられるが、その月の休日の日数はデータに無く、確かめていない。
- 市区町村の表とメッシュの表は別に集計されていて、合わない。2021-12 の全日・終日で、市区町村の表の合計をメッシュの表の市区町村ごとの合計で割ると、1,864 市区町村の中央値は 1.009、範囲は 0.64〜2.16。メッシュの表には 10 人未満のメッシュが無く、メッシュは 1 つの市区町村にまるごと割り当てられている。
- 市区町村の表で 4 区分が揃わない組がある (614,316 組のうち 101,594)。足りない区分は 10 人未満。区分を足して市区町村の合計にすると、落ちた分だけ小さい。
- 市区町村の表にあってメッシュの表に無い市区町村がある。野迫川村 (`29447`) は市区町村の表に 1,166 行あるが、メッシュの表には 0 行 (メッシュ属性には 148 メッシュある)。北方領土の `01695`、`01696`、`01699` は 2019-08 と 2019-09 に合計 12 行だけあり、市区町村マスタに無い。36 か月に満たない市区町村は、この 3 つと那珂川の 2 つのコードの計 5。
- 那珂川市は、2019 年のデータでは町だったときのコード `40305`、2020 年からは `40231` (定義書にも書いてある)。2019 年をまたいで市区町村を追うなら、`40305` を `40231` に読み替える。この読み替えで、57 メッシュの `citycode` が年で変わる。ほかに、`citycode` が途中で変わるメッシュは 3 つある (新潟県 `56397264` が 2020 年に `15307` から `15206`、神戸市の `52350057` と `52350164` が 2021 年に別の区へ)。メッシュの表で `mesh1kmid` と `citycode` の組は 245,830 で、メッシュの数 245,770 より 60 多い。
- メッシュ属性とマスタは、2019 年版と 2020 年版の 2 つが `version` 列で並んでいる。絞らずに結ぶと行が 2 倍になる。メッシュ属性の 2 つの版の違いは `citycode` だけで 70 メッシュ (那珂川の 69 と `15307` から `15206` の 1)。神戸市の 2 メッシュは、2021 年のデータの `citycode` がメッシュ属性の 2020 年版と違う。市区町村マスタの違いは 25 行で、特別区 23 の名前の書き方 (2019 年版は「東京２３区千代田区」)、篠山市から丹波篠山市 (コード `28221` は同じ)、那珂川。
- メッシュは 1 つの市区町村にまるごと割り当てられる。メッシュを市区町村ごとに足した値は、市区町村の境の中の人数ではない。境で按分するなら、メッシュの面と市区町村の面を重ねる。
- 配布元の定義書 (2021 年 2 月) は、期間を 2019-01〜2020-12 の 24 か月と書く。データは 2021-12 までの 36 か月あり、定義書の期間は古い。
- 無いもの: 日ごとや時間ごとの値、2022 年以降、年齢や性別、居住地の市区町村 (区分だけ)、メッシュの間の移動。値は GPS からの推計で、アプリの利用者の偏りを拡大推計で補ったもの。

## DuckDB で読む

```sql
-- 台東区の 2021 年 12 月、全日の昼。メッシュの面をつける
select m.mesh1kmid, m.population, a.geometry
from 'hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/monthly_mdp_mesh1km.parquet' m
join 'hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet/attribute_mesh1km.parquet' a
  on a.version = '2020' and a.mesh1kmid = m.mesh1kmid
where m.prefcode = '13' and m.citycode = '13106'
  and m.year = '2021' and m.month = '12' and m.dayflag = '2' and m.timezone = '0'
order by m.population desc;
-- 53394652  63678
-- 53394642  54161
-- 53394653  44031
```

コードは全て文字列なので、`prefcode = '13'`、`month = '01'` のように 0 で埋めた文字列で比べる。`month = '1'` は 0 行を返し、エラーにならない。DuckDB 2.0.0 では `month = 1` (数) は暗黙の変換で `'01'` と同じ行を返した。
