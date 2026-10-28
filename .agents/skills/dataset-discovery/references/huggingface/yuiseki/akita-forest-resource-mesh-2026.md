---
kind: dataset
id: yuiseki/akita-forest-resource-mesh-2026
description: 林野庁の「全国森林資源メッシュ」(20 m メッシュ) の秋田県の部分 29,088,595 セル。森林簿の林種、樹種 (粗い区分)、林齢を原典の列名と値のまま GeoParquet にし、森林計画対象森林レイヤの民有林・国有林と市町村を足したもの。秋田では広葉樹が 1 区分で、ブナもナラも分けられない
url: https://huggingface.co/datasets/yuiseki/akita-forest-resource-mesh-2026
license: 公共データ利用規約 第1.0版 (PDL1.0、CC BY 4.0 互換) と林野庁の全国森林資源メッシュの利用規約。出典と、加工したことと加工者の表示が要る。カードの表示は license other (pdl-1.0)
formats:
- GeoParquet (原典の図郭ごとに 60 ファイル)
crs: EPSG:6678 (JGD2011 / 平面直角座標系 第 X 系)。cell_x、cell_y もこの座標の m
spatial_coverage: 秋田県の陸地全体 (セルの中心が N03 2026-01-01 の秋田県の面に入るセル)
temporal_coverage: 原典ごとの森林簿年月日 2019-04-01〜2024-04-01。レーザ計測の値は秋田に無い
as_of:
  retrieved: 2026-10-28
  source_metadata_modified: 2026-07-27
  huggingface_revision: 1cad01a041ad2e1bfc2fa9ba35bd1385070d3f5f
contents:
- 20 m セル 1 つごとの林種、森林簿樹種 1〜3、林齢、森林簿年月日、民有林か国有林か、市町村
- 列ごとの値と NULL の割合、市町村別と所有別の埋まり方 (docs/akita_profile.md)
tables:
- name: mesh
  read: read_parquet('hf://datasets/yuiseki/akita-forest-resource-mesh-2026@1cad01a041ad2e1bfc2fa9ba35bd1385070d3f5f/parquet/*.parquet')
  grain: 1 つの 20 m セル。森林でないセルも含む (属性は NULL)
  rows: 29088595
  id:
  - sheet
  - source_fid
  join_keys:
  - column: layer_municipality_code5
    type: VARCHAR
    meaning: 5 桁の市町村コード (森林計画対象森林レイヤから、セルの中心で付けた)。秋田の 25 市町村。レイヤの外のセルは NULL
    unique: false
    joins:
    - jp-admin-2026-09:municipalities.code5
    note: NULL が 8,196,848 セルある。市町村ごとに数えるなら、セルの中心を jp-admin-2026-09 の面に入れるほうが漏れない
  no_key:
  - name: Dryad の地点 ID
    note: ブナの結実の地点とは空間結合で結ぶ。地点を EPSG:6678 に移し、cell_x、cell_y の 20 m 格子に落とすと速い
  columns:
  - name: sheet
    type: VARCHAR
    meaning: 追加列。原典の図郭 (10IC1 など、60 種類)
  - name: source_fid
    type: BIGINT
    meaning: 追加列。その図郭のファイルの中の GeoPackage fid
  - name: 林種
    type: VARCHAR
    meaning: 人工林、天然林、伐採跡地、未立木地、竹林、その他。森林簿の外は NULL
  - name: 森林簿樹種1
    type: VARCHAR
    meaning: 面積の多い順に 1 番目の樹種の区分 (スギ、広葉樹、マツ類、カラマツ、ヒバなど)。実際の列名の数字は半角
  - name: 森林簿樹種2
    type: VARCHAR
    meaning: 2 番目の樹種の区分。24.7% のセルだけにある
  - name: 森林簿樹種3
    type: VARCHAR
    meaning: 3 番目の樹種の区分。9.7% のセルだけにある
  - name: 林齢
    type: DOUBLE
    meaning: 森林簿樹種1 の林齢 (年)
  - name: 森林簿年月日
    type: VARCHAR
    meaning: 原典の森林簿の日付 (2024/3/31 などの文字列)
  - name: 樹冠高
    type: DOUBLE
    meaning: レーザ計測の値。秋田では全て NULL
  - name: レーザ解析樹種
    type: VARCHAR
    meaning: レーザ計測の値。秋田では全て NULL
  - name: 立木密度
    type: DOUBLE
    meaning: レーザ計測の値。秋田では全て NULL
  - name: 平均標高
    type: DOUBLE
    meaning: レーザ計測の値。秋田では全て NULL
  - name: 計測年月日
    type: '"NULL"'
    meaning: レーザ計測の日。秋田では全て NULL で、Parquet の型も NULL になっている
  - name: geometry
    type: GEOMETRY('EPSG:6678')
    meaning: 20 m セルの MultiPolygon (原典のまま)
  - name: cell_x
    type: BIGINT
    meaning: 追加列。セルの左下の x (EPSG:6678、m)
  - name: cell_y
    type: BIGINT
    meaning: 追加列。セルの左下の y (EPSG:6678、m)
  - name: layer_ownership
    type: VARCHAR
    meaning: 追加列。民有林か国有林 (森林計画対象森林レイヤの民国別)。レイヤの外は NULL
  - name: layer_municipality_code5
    type: VARCHAR
    meaning: 追加列。市町村コード 5 桁
  - name: layer_municipality_name
    type: VARCHAR
    meaning: 追加列。市町村名
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: GeoParquet の外接矩形の列 (EPSG:6678)
---

# 全国森林資源メッシュ 秋田県 (akita-forest-resource-mesh-2026)

林野庁の「全国森林資源メッシュ」の平面直角座標系 第 X 系の記録 (<https://www.geospatial.jp/ckan/dataset/mesh_10>) から、秋田県にかかる 60 図郭を 2026-10-28 に取り、セルの中心が秋田県に入る 20 m セルを残した GeoParquet。原典の 11 属性は名前も値も変えていない。民有林・国有林と市町村の列は、同じ林野庁の秋田県の森林計画対象森林レイヤ (`fr_layer_05_2025`、<https://www.geospatial.jp/ckan/dataset/layer>) から、セルの中心で付けた。
分析では、人工林 (主にスギ) と天然林 (主に広葉樹) の場所、林齢、民有林と国有林の違いに使う。秋田ではブナとナラを分けられない (下)。ブナ林やナラ林の面は [akita-vegetation-2024](akita-vegetation-2024.md) を使う。

作り方とスクリプトは GitHub の <https://github.com/yuiseki/akita-forest-resource-mesh-2026> にある。調べた経緯は <https://github.com/yuiseki/akita-beech-oak-sources> にある。

## 実測 (2026-10-29、DuckDB 2.0.0、固定版を hf:// で読んだ)

| 項目 | 値 |
|---|---|
| 行 | 29,088,595 (60 ファイル)。(cell_x, cell_y) の異なる組は 29,088,593 で、2 か所が同じ図郭の中で 2 回ある (属性も同じ、原典のまま) |
| 範囲 (cell_x、cell_y) | x −97,460〜13,740、y −125,080〜56,720 (EPSG:6678、m) |
| 所有 | 民有林 11,248,619、国有林 9,643,128、レイヤの外 (NULL) 8,196,848 |
| 市町村コード | 25 種類、05201〜05464 |
| 天然林の樹種1 | 広葉樹 9,961,634、スギ 180,312、マツ類 163,860 (上位 3 つ) |

カード (README) と `docs/akita_profile.md` の件数と一致した。配布側の検証 (`docs/verify_local.json`) は別のエンジンで 60 図郭を読み直し、選んだセル、11 属性、geometry の WKB、セルの角、レイヤの列の差がどれも 0 だった。

列ごとの埋まり方 (`docs/akita_profile.md`): 林種と林齢 74.2%、森林簿樹種1 74.4%、樹種2 24.7%、樹種3 9.7%、レーザ系の 5 列 0%。森林簿樹種1 は広葉樹 10,162,359、スギ 9,875,955、NULL 7,446,525、マツ類 602,040、カラマツ 354,106 の順。

## 気をつけること

- 樹種は森林簿の粗い区分で、広葉樹は全て「広葉樹」の 1 区分。どの樹種の列にもブナ、ミズナラ、ナラ、コナラの値は無い。このデータでブナ林を探さない。
- レーザ系の 5 列 (樹冠高、レーザ解析樹種、立木密度、平均標高、計測年月日) は秋田では全てのセルで NULL。
- 森林でない土地も含めた県の陸地全体のセルで、林種が NULL のセルが 7,492,834 ある。森林の面積は林種が NULL でないセルで数える (1 セル 400 m2)。
- 湯沢市の民有林は 829,185 セルのうち 176,552 (約 21%) に森林簿の値が無い。ほかの市町村はほぼ埋まっている。市町村で比べるときはこの欠けを書く。
- 森林簿樹種2、3 は国有林でずっと多く埋まっている (国有林 69.4%、28.8%。民有林 3.7%、0.1%)。2 番目以降の樹種の有無を、混交の度合いとして民有林と国有林で比べない。
- 森林簿樹種1 に `#N/A` という文字列が 207,673 セル (樹種2 は 589) ある。NULL とは別の値として残っている。
- 林齢は 0 が 432,421 セル (0 歳か不明かは書かれていない)。200 を超えるセルが 723,712 あり、最大 2023 は年に見える (主に天然林の広葉樹)。林齢で平均を取る前に外す規則を決める。
- 森林簿年月日は原典ごとに 2019〜2024 年で、今の状態ではない。
- メッシュとレイヤは縁で一致しない。レイヤの外 (NULL) なのに森林簿の値があるセルが 931,623 ある。
- 林野庁の利用規約によると、森林簿の値は主に 1/5,000 の空中写真の判読で作られ誤りを含みうる。現地や登記、税の記録と同じではなく、所有、境界、面積、立木の価値の証明にならない。
- 2,900 万行ある。全体を読むと時間がかかるので、列と `sheet` や `cell_x`、`cell_y` の範囲で絞って読む。メモリの上限を決めてから集計する。
- 個人情報のデータベースと突き合わせる使い方は、個人情報保護の法令の対象になる (配布元の注意)。

## 出典の表示

> 出典：林野庁（https://www.geospatial.jp/ckan/dataset/mesh_10、https://www.geospatial.jp/ckan/dataset/layer）、PDL1.0（https://www.digital.go.jp/resources/open_data/public_data_license_v1.0）をもとに yuiseki が作成。林野庁の「全国森林資源メッシュ」と「森林計画対象森林レイヤ」から秋田県の部分を切り出し、GeoParquet に変換し、市町村と民有林・国有林の列を加えた加工物であり、林野庁が作成した未加工のデータではない。（取得日 2026-10-28）
