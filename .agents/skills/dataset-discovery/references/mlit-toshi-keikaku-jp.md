---
kind: dataset
id: yuiseki/mlit-toshi-keikaku-jp
description: 国土交通省の都市計画決定GISデータの全国版を、レイヤーごとの GeoParquet にしたもの。参考情報で、範囲は概略。
url: https://huggingface.co/datasets/yuiseki/mlit-toshi-keikaku-jp
card_revision: 39fdb22f42b7619b753b5389bc107aaadf8ba614
license: PDL1.0 (CC BY 4.0 と互換)。出典の表示と、加工したことの明記が要る。旧原典の自治体別の条件に未確認の点がある
formats:
- GeoParquet 1.0
- Shapefile (ZIP)
- GeoJSON (ZIP)
- CityGML (ZIP)
crs: EPSG:6668
spatial_coverage: 日本 47 都道府県の約 1,400 自治体。レイヤーによって収録される自治体が違う
temporal_coverage: 令和 7 年度版 (2026-05 公開、2026-07 に一部修正)。決定の日付は市区町村によって古い
as_of:
  edition: fy2025
  published: 2026-05-21
  corrected: 2026-07
contents:
- 用途地域と容積率と建蔽率
- 都市計画道路
- 公園
- 地区計画
- 立地適正化計画ほか 25 レイヤー
tables:
- name: youto
  read: hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/youto.parquet
  grain: 1 つの用途地域の面 (決定の 1 区画)
  rows: 102159
  id: []
  join_keys:
  - column: Citycode
    type: VARCHAR
    meaning: 5 桁の市区町村コード (文字列、先頭の 0 を保つ)
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.code5
    note: 1,215 件すべてが code5 に一致する
  no_key:
  - name: feature_id
    note: 区画を一意に指す ID は無い。source_file と fid の組で行を指す
  columns:
  - name: YoutoName
    type: VARCHAR
    meaning: 用途地域の名前 (商業地域など)
  - name: YoutoCode
    type: INTEGER
    meaning: 用途地域の種類のコード
  - name: FAR
    type: DOUBLE
    meaning: 容積率 (%)。空は値が無いこと
    missing: NULL は値が無いこと (8,561 行)。0 ではない
  - name: BCR
    type: DOUBLE
    meaning: 建蔽率 (%)
  - name: INDate
    type: VARCHAR
    meaning: 当初決定の日付。書式がばらばらの文字列
    missing: NULL が大半 (102,159 行のうち 101,092 行)
  - name: geometry
    type: geometry:EPSG:6668
    meaning: 用途地域の面 (EPSG:6668)
- name: other_layers
  read: hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/<layer>.parquet
  grain: レイヤーごとに違う。douro は計画道路 1 本の線、kouen は公園などの面、chikukei は地区計画の面、tokei は都市計画区域の面
  rows: 322176
  id: []
  join_keys:
  - column: Citycode
    type: VARCHAR
    meaning: 5 桁の市区町村コード
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.code5
---

# 都市計画決定GISデータ (mlit-toshi-keikaku-jp)

国土交通省都市局の「都市計画決定GISデータ」の全国版。約 1,400 市区町村の都市計画の決定を、用途地域 (容積率、建蔽率つき)、都市計画道路、公園、地区計画、立地適正化計画などのレイヤーに分けて持つ。
分析では、土地利用の特徴量 (点がどの用途地域に入るか、容積率)、規制の空間的な広がり、都市計画区域の内外の比較に使う。

## どこから読むか

Hugging Face の `yuiseki/mlit-toshi-keikaku-jp`。1 レイヤーが 1 つの Parquet で、版 (令和 7 年度、`fy2025`) がディレクトリになっている。

```
hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/<layer>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/mlit-toshi-keikaku-jp> (レイヤーの一覧、行数、列、検証のしかた)
- 配布元 (利用条件に同意してからダウンロード): <https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html>
- 元の zip (Shapefile、GeoJSON、CityGML) と定義書の PDF も、同じデータセットの `raw/fy2025/` にある。列の意味は定義書が正本。

## 主なレイヤー

行数はカードの値で、`youto` は 2026-10-13 に実測して一致した。

| レイヤー | 中身 | 型 | 行数 | 市区町村数 |
|---|---|---|---:|---:|
| `youto` | 用途地域 | 面 | 102,159 | 1,215 |
| `douro` | 都市計画道路 | 線 | 191,584 | 785 |
| `kouen` | 公園、緑地、墓園 | 面 | 41,161 | 716 |
| `chikukei` | 地区計画 | 面 | 10,886 | 601 |
| `tokei` | 都市計画区域 | 面 | 10,279 | 1,373 |
| `senbiki` | 区域区分 (市街化区域、市街化調整区域) | 面 | 7,259 | 637 |
| `ritteki` | 立地適正化計画 | 面 | 9,675 | 582 |

ほかに 18 のレイヤー (高度地区、防火地域、風致地区など) がある。全 25 レイヤーで 424,335 行 (カードによる)。

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 単位 | 1 つの決定の面 (線)。`youto` なら用途地域の 1 区画 |
| CRS | `geometry` は `GEOMETRY('EPSG:6668')` (JGD2011 の経度、緯度) (実測) |
| 範囲 | 全国。ただし自治体が提出した分だけで、全部の決定ではない |
| 時点 | 令和 7 年度版 (2026-05-21 公開、同年 7 月に一部修正)。市区町村によって決定の日付は古い |
| ライセンス | 国土交通省のサイトの条件。PDL1.0 で、CC BY 4.0 と互換。出典の表示が要り、加工したことも書く |

`youto` の主な列は、`YoutoName` (用途地域の名前)、`YoutoCode` (種類のコード)、`FAR` (容積率、%)、`BCR` (建蔽率、%)、`Pref`、`Citycode` (5 桁の市区町村コード)、`Cityname`、`INDate`、`FNDate`、`geometry`、取り込み元の `source_file` と `fid`。

```sql
-- 千代田区の用途地域ごとの容積率
select YoutoName, FAR, BCR, count(*)
from 'hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/youto.parquet'
where Citycode = '13101'
group by all order by FAR desc;
```

## 気をつけること

- 掲載は自治体が提供した分だけ。国土交通省は、範囲は概ねの位置を示し、実際の決定範囲と異なることがある、掲載のない決定もあると明記している。建築の確認や重要事項説明には使わない。
- 市区町村ごとに掲載の有無が違う。`youto` がある市区町村は 1,215 で、全国の市区町村の一部。使える市区町村は、データで数える。公表自治体の一覧とは数が合わない (カードによる)。
- `FAR` は `youto` の 8,561 行で空 (実測)。0 ではなく、値が無いこと。
- 日付 (`INDate`、`FNDate`) は文字列で、`S43.3.13`、`昭和48年12月25日`、`2024/03/29` など書式がばらばら。ほとんどの行で空。
- 地理院の測量成果などの条件が絡む部分があるとカードが書いている。国土数値情報の旧データを使っている市区町村 (22 を挙げている) は、再配布の条件が確かめられていない。ファイルの再配布ではなく、分析の結果を公開するだけなら影響は小さいが、再配布するなら国土交通省か自治体に確かめる。
- 一部のレイヤーに `geometry` が空の行がある (`douro` で 5,802 行など)。属性だけが残っている。
- 年の版は 1 つだけで、国土交通省が元の場所で直す。使った版とカードの日付を書く。

## ほかのデータとの結合

- `Citycode` で `jp-admin-2026-09` の `code5` と結べる。実測で、`youto` の 1,215 の `Citycode` はすべて `code5` に一致した。市区町村ごとの面積あたりの指標や人口あたりの指標を出せる。
- 国土数値情報の「都市計画決定情報」(A55) は同じデータを編集したもので、最新が 1 年古い (カードによる)。こちらを読むなら、`mlit-nlftp` の目録を引く。
