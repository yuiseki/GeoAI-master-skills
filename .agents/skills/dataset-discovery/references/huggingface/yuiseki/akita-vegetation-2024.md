---
kind: dataset
id: yuiseki/akita-vegetation-2024
description: 環境省生物多様性センターの「現存植生図2024」(1/25,000) の秋田県の部分 174,576 ポリゴン。凡例名 (群落名) と植生区分、植生自然度、作成年度を原典の列名と値のまま GeoParquet にしたもの。秋田でブナやミズナラの群落を面で識別できる
url: https://huggingface.co/datasets/yuiseki/akita-vegetation-2024
license: 公共データ利用規約 第1.0版 (PDL1.0、CC BY 4.0 互換)。出典と、加工したことと加工者の表示が要る。カードの表示は license other (pdl-1.0)
formats:
- GeoParquet
crs: EPSG:6668 (JGD2011 の経緯度)。area_m2 と source_area_m2 は EPSG:6678 (平面直角座標系 第 X 系) で測った面積
spatial_coverage: 秋田県 (国土数値情報 N03 2026-01-01 の秋田県の面で切った)。経度 139.69〜141.00、緯度 38.87〜40.51
temporal_coverage: ポリゴンの作成年度 2001〜2022 (1 時点の図ではない)
as_of:
  retrieved: 2026-10-28
  source_metadata_modified: 2026-08-27
  huggingface_revision: b3b36a0fb6ff027fb1f483be3288df2df76c0cf3
contents:
- 植生の群落の面 1 つごとの凡例コード、凡例名、植生区分、植生自然度、作成年度、切る前と後の面積
- 秋田にある 134 凡例の一覧と、名前にブナ、ミズナラ、ナラ、コナラを含む 11 凡例の一覧 (docs/)
tables:
- name: vegetation_akita
  read: hf://datasets/yuiseki/akita-vegetation-2024@b3b36a0fb6ff027fb1f483be3288df2df76c0cf3/parquet/vegetation_akita.parquet
  grain: 1 つの植生ポリゴン (1 群落の面)。県境をまたぐ 1,462 個は県境で切ってある
  rows: 174576
  id:
  - fid
  no_key:
  - name: code5
    note: 市町村の列は無い。jp-admin-2026-09 の面と空間結合で付ける
  - name: Dryad の地点 ID
    note: ブナの結実の地点 (fagus-crenata-masting-jp-2026-06 の study_sites) とは、点をポリゴンに入れる空間結合で結ぶ
  columns:
  - name: fid
    type: BIGINT
    meaning: 原典 GeoPackage の fid。全国で一意、秋田の中でも重複なし (実測)
  - name: 植生区分コード
    type: VARCHAR
    meaning: 植生区分のコード (文字列)
  - name: 大区分コード
    type: VARCHAR
    meaning: 凡例コードの上 2 桁
  - name: 中区分コード
    type: VARCHAR
    meaning: 凡例コードの中 2 桁
  - name: 細区分コード
    type: VARCHAR
    meaning: 凡例コードの下 2 桁
  - name: 凡例コード
    type: VARCHAR
    meaning: 6 桁の凡例コード (文字列)。秋田に 134 種類
  - name: 凡例名
    type: VARCHAR
    meaning: 植物社会学の群落名 (原典の綴り)。チシマザサ－ブナ群団、オクチョウジザクラ－コナラ群集など
  - name: 植生自然度
    type: VARCHAR
    meaning: 1〜10 と 98、99 (文字列)。10 が最も自然に近い
  - name: 植生自然度区分
    type: VARCHAR
    meaning: 植生自然度の区分名
  - name: 植生区分
    type: VARCHAR
    meaning: ブナクラス域自然植生、ブナクラス域代償植生、植林地・耕作地植生などの 10 区分
  - name: 作成年度
    type: VARCHAR
    meaning: ポリゴンを作った年度 (文字列)。2001〜2022
  - name: 地域ブロック
    type: VARCHAR
    meaning: 原典の地域ブロック。秋田は全て 2 (東北)
  - name: source_file
    type: VARCHAR
    meaning: 追加列。元のファイル (veg2024bk2a.gpkg か veg2024bk2b.gpkg)
  - name: clipped
    type: BOOLEAN
    meaning: 追加列。県境で切ったポリゴンなら true (1,462 個)
  - name: source_area_m2
    type: DOUBLE
    meaning: 追加列。切る前のポリゴンの面積 (m2、EPSG:6678)
  - name: area_m2
    type: DOUBLE
    meaning: 追加列。保存したポリゴンの面積 (m2、EPSG:6678)
  - name: geometry
    type: GEOMETRY('EPSG:6668')
    meaning: MultiPolygon
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: GeoParquet の外接矩形の列 (経緯度)
---

# 現存植生図2024 秋田県 (akita-vegetation-2024)

環境省生物多様性センターの「現存植生図2024」を G空間情報センター (<https://www.geospatial.jp/ckan/dataset/biodic_veg2024>) から 2026-10-28 に取り、東北ブロックの 2 ファイル (`veg2024bk2a.gpkg`、`veg2024bk2b.gpkg`) から秋田県の部分を切り出した GeoParquet。原典の 11 属性は名前も値も変えていない。独自の分類にまとめた列は無い。
分析では、秋田のブナ林とミズナラ林、コナラ林の場所と広さに使う。クマの出没 ([akita-kumadas-wildlife-sighting](akita-kumadas-wildlife-sighting.md)) やブナの結実の地点 ([fagus-crenata-masting-jp-2026-06](fagus-crenata-masting-jp-2026-06.md)) の周りの植生を、空間結合で付ける材料になる。同じ秋田の [akita-forest-resource-mesh-2026](akita-forest-resource-mesh-2026.md) では広葉樹を樹種に分けられないので、ブナやナラを面で探すならこちらを使う。

作り方とスクリプトは GitHub の <https://github.com/yuiseki/akita-vegetation-2024> にある。調べた経緯は <https://github.com/yuiseki/akita-beech-oak-sources> にある。

## 実測 (2026-10-29、DuckDB 2.0.0、固定版を hf:// で読んだ)

| 項目 | 値 |
|---|---|
| 行 | 174,576。`fid` の重複 0 |
| 面積の合計 | 11,635.9 km2 (`area_m2` の和) |
| 県境で切った面 | 1,462 (`clipped`) |
| 作成年度 | 2001〜2022 |
| 凡例 | 134 種類 |
| 範囲 (bbox) | 経度 139.692〜140.995、緯度 38.873〜40.511 |
| 植生区分の面積 | 植林地・耕作地植生 5,617.5 km2、ブナクラス域代償植生 3,445.4、ブナクラス域自然植生 1,668.2、その他 757.5、コケモモ－トウヒクラス域自然植生 78.4、河辺・湿原・塩沼地・砂丘植生 61.6、ほか 4 区分で 7.2 |

カード (README) の件数、面積、作成年度の範囲と一致した。カードによると、配布側の検証 (`docs/verify_local.json`) は別のエンジンで秋田を選び直し、fid、11 属性、切っていない面の WKB がすべて一致している。

名前にブナ、ミズナラ、ナラ、コナラを含む凡例はカードの表のとおり 11 あり、36,259 個の面になる。主なものはチシマザサ－ブナ群団 (1,190.88 km2)、オオバクロモジ－ミズナラ群集 (1,296.31)、オクチョウジザクラ－コナラ群集 (934.74)、ブナ－ミズナラ群落 (535.11)。

## 気をつけること

- 1 つの面は 1 つの群落で、種の割合ではない。ブナ－ミズナラ群落の面積を、ブナの面積とミズナラの面積に分けられない。凡例どうしは意味が重なるので、11 凡例の面積を足して 1 つの「ブナ・ナラ林」の面積にしない。
- 凡例名の部分一致で「ナラ」を探すと、ミヤマナラ (190100、ミズナラでもコナラでもない) も拾う。凡例コードで選ぶ。
- 作成年度が面ごとに違う (2020 年 68,954 面、2001 年 21,916 面など)。1 時点の植生ではない。年の違う出来事と重ねるときは、作成年度を書く。
- 数値に見える列 (コード、植生自然度、作成年度) は全て文字列。並べ替えや比較の前に cast する。植生自然度の 98、99 は自然度の段階ではない区分 (原典の定義を見る)。
- 県境で切った面の縁は N03 の県境で、調査の境界ではない。`source_area_m2` に切る前の面積がある。
- 123 組の面が細い隙間ほど重なっている (最大約 80 m2)。原典のまま直していない。
- geometry は経緯度 (EPSG:6668)。面積や距離は EPSG:6678 などの平面に移してから測る。GeoParquet は経度、緯度の順。
- 配布元の版の番号は無い。2026-10-28 に取ったものとして扱う。

## 出典の表示

> 出典：「現存植生図2024」（環境省生物多様性センター）（https://www.geospatial.jp/ckan/dataset/biodic_veg2024）、PDL1.0（https://www.digital.go.jp/resources/open_data/public_data_license_v1.0）。環境省生物多様性センターのデータを、yuiseki が秋田県境で切り出し、県境上のポリゴンを切り取り、GeoParquet に変換して作成した加工物であり、環境省が作成した未加工のデータではない。（取得日 2026-10-28）
