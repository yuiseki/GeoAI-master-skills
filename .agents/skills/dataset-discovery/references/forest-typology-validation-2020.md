---
kind: dataset
id: yuiseki/forest-typology-validation-2020
description: GVFT 2020 の森林タイプ検証標本9,100地点と、専門家合意済み8,190地点を GeoParquet にした版固定データ。
url: https://huggingface.co/datasets/yuiseki/forest-typology-validation-2020
source_url: https://plus.figshare.com/articles/dataset/Global_Validation_of_Forest_Types_GVFT_2020/33093404
license: CC BY 4.0。クレジットとライセンス URL を維持し、改変した場合はその旨を示す
formats:
- GeoParquet
- CSV
crs: EPSG:4326 (WGS84 longitude, latitude)
spatial_coverage: 全球の陸域。実測座標は南緯54.56度から北緯81.23度
temporal_coverage: ForTy v1 の2020年地図に対する検証標本。現地調査の年とは限らない
as_of:
  checked: 2026-10-25
  source_doi: 10.25452/figshare.plus.33093404.v1
  hub_revision: b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c
contents:
- 地点の層化抽出区分、2名の専門家ラベル、合意状況
- ForTy v1 2020 の予測クラスと6クラスのスコア
- 元 Figshare CSV とチェックサム
tables:
- name: all_sites
  read: hf://datasets/yuiseki/forest-typology-validation-2020@b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c/parquet/all-sites.parquet
  grain: 1行が全球に配置した検証標本地点。7層から各1,300点を抽出
  rows: 9100
  id:
  - sampleid
  columns:
  - name: sampleid
    type: BIGINT
    meaning: 標本地点の一意 ID
  - name: geometry
    type: GEOMETRY (OGC:CRS84)
    meaning: lon, lat から作成した WGS84 の点
  - name: strata
    type: BIGINT
    meaning: 層化区分 (1〜7)。クラス1〜6と Potential Forest
  - name: ann1
    type: BIGINT
    meaning: 専門家1のクラス。0は unsure
  - name: ann2
    type: BIGINT
    meaning: 専門家2のクラス。0は unsure
  - name: unsure
    type: BOOLEAN
    meaning: 少なくとも1名が不確かとしたか
  - name: unresolved
    type: BOOLEAN
    meaning: 専門家間で不一致があり未解決か
  - name: pred_v1_2020
    type: BIGINT
    meaning: ForTy v1 2020 の予測クラス
  - name: s1_v1_2020
    type: DOUBLE
    meaning: クラス1 Primary Forest のモデルスコア
  - name: s2_v1_2020
    type: DOUBLE
    meaning: クラス2 Naturally Regenerating Forest のモデルスコア
  - name: s3_v1_2020
    type: DOUBLE
    meaning: クラス3 Planted Forest のモデルスコア
  - name: s4_v1_2020
    type: DOUBLE
    meaning: クラス4 Plantation Forest のモデルスコア
  - name: s5_v1_2020
    type: DOUBLE
    meaning: クラス5 Tree Crops and Agroforestry のモデルスコア
  - name: s6_v1_2020
    type: DOUBLE
    meaning: クラス6 Other Land のモデルスコア
- name: resolved_sites
  read: hf://datasets/yuiseki/forest-typology-validation-2020@b4cf5cec3cb3d2bedbc130a86f626338ae4ac77c/parquet/resolved-sites.parquet
  grain: unsure=false かつ unresolved=false の専門家合意済み地点
  rows: 8190
  id:
  - sampleid
---

# ForTy 2020 全球検証標本

[Figshare Plus の GVFT 2020 v0.6](https://plus.figshare.com/articles/dataset/Global_Validation_of_Forest_Types_GVFT_2020/33093404)にある9,100地点の CSV を、全地点と専門家合意済みサブセットの GeoParquet に変換し、[Hugging Face](https://huggingface.co/datasets/yuiseki/forest-typology-validation-2020)に公開しました。Figshare が示す MD5 と取得CSVが一致します。取得時の版、DOI、MD5、SHA-256は Hub の `raw/2026-10-25/MANIFEST.json` に記録しています。

## 実測内容

- `all-sites.parquet`: 9,100地点、`sampleid` は全件一意、欠損列・null geometry・無効geometryはありません。
- `resolved-sites.parquet`: `unsure=false` かつ `unresolved=false` の8,190地点。原著の精度評価に使われる合意済み標本です。
- 7つの `strata` は各1,300地点です。合意済み件数を面積比の重みとして扱わないでください。
- geometry は DuckDB が `OGC:CRS84` と記録する WGS84 longitude/latitude 順の Point です。`lon` と `lat` 列も保持しています。
- 全標本の実測境界は経度 -179.6005〜179.0301度、緯度 -54.5561〜81.2303度でした。

## 利用上の注意

これは ForTy v1 2020地図を検証するための層化標本で、全陸域を面積比例で抽出した標本ではありません。予測クラスと確信度スコアを、独立した検証ラベルと混同しないでください。`unsure` または `unresolved` の行を正解データとして扱わず、通常の全域精度に単純集計を使わないでください。地点位置は標本中心で、10m未満の位置精度を保証するものではありません。

## 出典とライセンス

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)です。Maxim Neumann, Anton Raichuk, Myroslava Lesiv, Ivelina Georgieva, Maria Shchepashchenko, and Steffen Fritz, “Global Validation of Forest Types (GVFT) 2020,” Figshare Plus, v1, [DOI: 10.25452/figshare.plus.33093404.v1](https://doi.org/10.25452/figshare.plus.33093404.v1) を表示してください。この公開版は CSV に点ジオメトリを加え、GeoParquet に変換しています。

関連研究: [Global forest typology at 10-meter resolution for forest and land-use monitoring](https://doi.org/10.31223/X58R27)。
