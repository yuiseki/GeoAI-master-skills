---
kind: dataset
id: yuiseki/env-biodic-bear-distribution-mesh-jp
description: 環境省生物多様性センターが配布するクマ (ツキノワグマ、ヒグマ) の分布メッシュを、5 つの調査 (自然環境保全基礎調査の第 2、4、5、6 回と、要注意鳥獣 (クマ等) 生息分布調査) から 1 つの縦長の表 28,194 行にした GeoParquet。値は配布ファイルのまま。いた記録のメッシュの集計で、行の無いメッシュはいないことの証拠ではない
url: https://huggingface.co/datasets/yuiseki/env-biodic-bear-distribution-mesh-jp
license: 生物多様性センター ウェブサイト利用規約に従い、公共データ利用規約 第1.0版 (PDL1.0、CC BY 4.0 互換)。出典と、加工したことと加工者の表示が要る。カードの表示は license other (biodic-terms-of-service-pdl-1.0)
formats:
- GeoParquet (parquet/bear_mesh_long.parquet、parquet/bear_mesh_cells_from_code.parquet)
crs: EPSG:6668 (JGD2011 の経緯度)。do02〜do05 の測地系は配布ファイルに書かれておらず、yo4 に合わせて付けたラベル
spatial_coverage: 日本全国のメッシュ。メッシュコードから計算したセルの範囲は経度 122.875〜154.0、緯度 20.417〜45.583。都道府県の列は無い
temporal_coverage: 調査ごとに違う。第 2 回は昭和53年度 (1978)、第 4 回は平成元〜3年度、第 5 回は平成9、10年度、第 6 回は平成12〜16年度、yo4 は平成22年度 (2010) 以降の情報 (報告書は平成30年度)。2026-10-31 取得
as_of:
  retrieved: 2026-10-31
  huggingface_revision: 7f635cbfb92be5093fa707dbe6afec0e37d240f4
contents:
- 調査、種名、メッシュコードごとの記録の行と、調査ごとの元の列 (地名、年月、確認調査、yo4 のフラグなど)
- yo4 だけ、配布された 5 km メッシュの面
- 全ての行について、メッシュコードから計算したセルの面 (別ファイル。環境省が配った形ではない)
tables:
- name: bear_mesh_long
  read: hf://datasets/yuiseki/env-biodic-bear-distribution-mesh-jp@7f635cbfb92be5093fa707dbe6afec0e37d240f4/parquet/bear_mesh_long.parquet
  grain: 配布ファイルの 1 行 (CSV) または 1 地物 (yo4)。do04 と do05 は記録の行で、同じメッシュが繰り返す
  rows: 28194
  id:
  - survey_id
  - source_row
  no_key:
  - name: 都道府県、市町村
    note: 列は無い。メッシュのセルを行政界 (jp-admin-2026-09 など) と空間結合して付ける
  columns:
  - name: survey_id
    type: VARCHAR
    meaning: do02、do04、do05、do06、yo4
  - name: survey_label
    type: VARCHAR
    meaning: 調査の名前と期間
  - name: species
    type: VARCHAR
    meaning: 種名。do02〜do05 はツキノワグマかヒグマ。do06 は「ツキノワグマ・ヒグマ」。yo4 はファイルに種の列が無く、Geoportal のメタデータの名前「クマ類（ヒグマ・ツキノワグマ）」を入れた
  - name: species_in_source
    type: BOOLEAN
    meaning: 種名が元のファイルにあるか。yo4 は false
  - name: mesh_code
    type: VARCHAR
    meaning: メッシュコード (文字列)。do02〜do05 は 6 桁 (2 次メッシュに当たる)、do06 と yo4 は 8 桁の 5 km メッシュ
  - name: source_file
    type: VARCHAR
    meaning: 元の ZIP と中のファイル
  - name: source_row
    type: BIGINT
    meaning: 元のファイルの 1 から数えた行 (CSV) か地物の番号 (yo4)
  - name: 地名、分類群、種コード、備考
    type: VARCHAR
    meaning: do02 の列 (分類群と種コードは do04、do05 にもある)
  - name: 調査票番号、年月
    type: VARCHAR
    meaning: do04 と do05 の列。年月は 4 桁で書式の説明が無い。調査者コードは公開していない
  - name: 確認調査
    type: VARCHAR
    meaning: do06 の列。「第2回と第6回で確認」か「第6回のみ確認」
  - name: Descriptio、H22_29、単年度、第6回で確、第6回のみ、両調査で確
    type: VARCHAR
    meaning: yo4 (Bear.dbf) の列。値は文字列の 1 と 0。列名は DBF の 10 バイトで切れている
  - name: geometry
    type: GEOMETRY('EPSG:6668')
    meaning: yo4 は配布された 5 km メッシュの面。CSV 由来の行は null
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: GeoParquet の外接矩形の列
- name: bear_mesh_cells_from_code
  read: hf://datasets/yuiseki/env-biodic-bear-distribution-mesh-jp@7f635cbfb92be5093fa707dbe6afec0e37d240f4/parquet/bear_mesh_cells_from_code.parquet
  grain: bear_mesh_long の 1 行に 1 行。survey_id と source_row で結ぶ
  rows: 28194
  id:
  - survey_id
  - source_row
  columns:
  - name: survey_id
    type: VARCHAR
    meaning: bear_mesh_long と同じ
  - name: source_row
    type: BIGINT
    meaning: bear_mesh_long と同じ
  - name: mesh_code
    type: VARCHAR
    meaning: bear_mesh_long と同じ
  - name: mesh_digits
    type: BIGINT
    meaning: メッシュコードの桁数 (6 か 8)
  - name: cell_kind
    type: VARCHAR
    meaning: 計算したセルの種類 (2 次メッシュか 5 km メッシュ)
  - name: geometry_computed_from_mesh_code
    type: GEOMETRY('EPSG:6668')
    meaning: yuiseki がメッシュコードから計算した長方形。環境省が配った形ではない
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: GeoParquet の外接矩形の列
---

# 環境省 クマ類の分布メッシュ (env-biodic-bear-distribution-mesh-jp)

環境省生物多様性センターの「自然環境保全基礎調査」と「要注意鳥獣(クマ等)生息分布調査」の分布メッシュのうち、クマの行だけを <https://www.biodic.go.jp/shapedata/download.html> から 2026-10-31 に取り、1 つの表にした GeoParquet。値は直さず、投影も変えていない。調査者コードの列だけは、人と結び付くのを避けて外した。
分析では、クマの通報 ([akita-kumadas-wildlife-sighting](akita-kumadas-wildlife-sighting.md) など) とは偏りの違う、2 つ目の観測系として使う。通報は人が見て届けたもの、このメッシュは聞き取りやアンケート、行政と研究機関の調査を集めたもので、どちらも熊の正解ではない。

作り方、取得の記録、検証のスクリプトは GitHub の <https://github.com/yuiseki/env-biodic-bear-distribution-mesh-jp> にある。

## 実測 (2026-11-03、DuckDB 1.5 系、固定版を hf:// で読んだ)

| 調査 | 種名 | 行 | メッシュ | 配布された面 |
|---|---|---:|---:|---:|
| do02 | ツキノワグマ | 1,298 | 1,298 | 0 |
| do02 | ヒグマ | 742 | 742 | 0 |
| do04 | ツキノワグマ | 1,338 | 912 | 0 |
| do04 | ヒグマ | 428 | 340 | 0 |
| do05 | ツキノワグマ | 464 | 252 | 0 |
| do05 | ヒグマ | 121 | 85 | 0 |
| do06 | ツキノワグマ・ヒグマ | 6,735 | 6,735 | 0 |
| yo4 | クマ類（ヒグマ・ツキノワグマ） | 17,068 | 17,068 | 17,068 |

合計 28,194 行で、カード (README) の表と一致した。計算したセルの表も 28,194 行で、`survey_id`、`source_row`、`mesh_code` で全ての行が結べた。yo4 の `H22_29` と `第6回で確` の組み合わせは、(0, 0) 7,641、(0, 1) 72、(1, 0) 2,693、(1, 1) 6,662。

## 気をつけること

- いた記録の集計で、いないことの証拠ではない。yo4 の 17,068 メッシュは全国の枠で、フラグが全て 0 の 7,641 は情報の無いメッシュ。クマのいたメッシュは `H22_29` か `第6回のみ` が 1 の 9,427。
- 調査ごとに方法、期間、情報源、メッシュの大きさが違う。環境省も、第 6 回と平成30年度の調査は手法と情報収集の体制が違い、単純に比較できないとしている。調査の間の数の増減を、熊の増減として読まない。
- 報告書によると、5 km メッシュには一時的な目撃などの情報も含まれ、奥山の情報は薄い可能性がある。
- do02、do04、do05 は 6 桁のコードで 2 次メッシュ (約 10 km) に当たり、do06 と yo4 の 5 km メッシュとは格子が違う。6 桁を 2 次メッシュと読むのも、8 桁の 7、8 桁目を 5 km メッシュの位置と読むのも、データから推定した読み方 (yo4 では 17,068 の面全てで計算したセルと一致した)。
- yo4 には種の列が無く、do06 は 2 種を 1 つの名前にしている。種を分けられるのは do02、do04、do05 だけ。
- yo4 のフラグの意味は、列名の定義ではなく、報告書の図の凡例と数からの読み方。`H22_29` = 1 は平成22年度以降の情報 (報告書の本文は 9,358 メッシュで、ファイルは 9,355)、`単年度` = 1 は 1 年度だけ情報のあったメッシュ。
- 都道府県の列は無い。県で絞るときは、計算したセルか yo4 の面を行政界と空間結合する。
- 2021 年 3 月の訂正で、yo4 に `第6回のみ` が足された。カモシカの訂正はこの表のクマの行に影響しない。

## 出典の表示

> 出典：環境省生物多様性センター『自然環境保全基礎調査』『要注意鳥獣(クマ等)生息分布調査』を加工して作成 (https://www.biodic.go.jp/shapedata/download.html、データダウンロード日 2026-10-31)。yuiseki がクマの行を選び出して Parquet の表にし、メッシュコードからセルを計算した加工物であり、環境省が作成した未加工のデータではない。
