---
kind: dataset
id: yuiseki/nagaoka-bear-sighting
description: 新潟県長岡市の「クマ出没情報」、平成26・27年度 (2014-04-09〜2016-03-30) の目撃と痕跡 166 件を GeoParquet にしたもの。古く小さい。
url: https://huggingface.co/datasets/yuiseki/nagaoka-bear-sighting
license: CC BY 4.0 (長岡市オープンデータ利用規約。改変したことの表示の形が決まっている。本文)
formats:
- GeoParquet
- CSV 4 (各年度の UTF-8 と Shift_JIS。配布元のまま)
crs: OGC:CRS84 として書いてある。配布元は測地系を書いていない (WGS84 とみなしている)
spatial_coverage: 新潟県長岡市 (栃尾、長岡、越路、山古志、小国、川口の地域)
temporal_coverage: 2014-04-09〜2016-03-30 (FY2014、FY2015)
as_of:
  source_data_updated: 2016-06-10
  retrieved: 2026-10-26
  huggingface_revision: 724bde2a1b5168ae39e9a4a781220d28fabeb762
contents:
- 目撃と痕跡の 1 件ごとの点、日付、区分、地域名、場所、状況
tables:
- name: sighting
  read: hf://datasets/yuiseki/nagaoka-bear-sighting@724bde2a1b5168ae39e9a4a781220d28fabeb762/parquet/sighting.parquet
  grain: 1 件の目撃または痕跡の確認
  rows: 166
  id:
  - fiscal_year
  - no
  no_key:
  - name: code5
    note: 市町村コードは無い。全行が長岡市 (15202) で、点も全て長岡市の面に入る (実測)
  columns:
  - name: fiscal_year
    type: SMALLINT
    meaning: 年度 (2014 か 2015)
  - name: no
    type: INTEGER
    meaning: ファイルの中の番号。年度ごとに振り直す
  - name: date_text
    type: VARCHAR
    meaning: 日付の文字列 (`平成26年6月27日 目撃` など)
  - name: date
    type: DATE
    meaning: date_text から読んだ日付
  - name: kind
    type: VARCHAR
    meaning: 区分。目撃 86、痕跡 62、◆目撃 17、末尾に空白のある目撃 1
  - name: district
    type: VARCHAR
    meaning: 地域名 (合併前の市町村)。栃尾 107、長岡 30 など
  - name: classification
    type: VARCHAR
    meaning: 分類。目撃か痕跡
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 点 (経度, 緯度)
---

# 長岡市 クマ出没情報 (nagaoka-bear-sighting)

長岡市危機管理防災本部がオープンデータのページ (<https://www.city.nagaoka.niigata.jp/shisei/cate10/bousai/03.html>) に出している「クマ出没情報」の CSV (FY2014、FY2015) を、GeoParquet にしたもの。ページのデータの最終更新は 2016-06-10 で、後の年度は足されていない。
分析では、合併前の地域 (`district`) ごとの違いを見る小さな例に使う。2 年分しかないので、年ごとの変動は読めない。

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 166 (FY2014 95、FY2015 71。README と一致) |
| 日付 | 2014-04-09〜2016-03-30。全行で読めている |
| 範囲 | 経度 138.66〜139.08、緯度 37.24〜37.52 |
| 点と面 (`jp-admin-2026-09`) | 166 点全てが長岡市の面に入る |

## 気をつけること

- `kind` は表記が揺れている (`◆目撃`、末尾の空白)。目撃と痕跡に分けるなら `classification` を使う。date_text の末尾の語と `classification` が食い違う行が 1 つある (README)。
- `no` は年度ごとに振り直す。行を区別するなら `fiscal_year` と `no` の組を使う。
- 2014〜2015 年度だけで、2016 年に公開されたまま。今の出没の様子には使えない。
- 出典の表示は、市の利用規約が改変したことの表示の形を決めている。下の文をそのまま使う。

## 出典の表示

> この「データセット」は、以下の著作物を改変して利用しています。
> 「クマ出没情報」、長岡市、クリエイティブ・コモンズ・ライセンス表示4.0国際（https://creativecommons.org/licenses/by/4.0/legalcode.ja）
