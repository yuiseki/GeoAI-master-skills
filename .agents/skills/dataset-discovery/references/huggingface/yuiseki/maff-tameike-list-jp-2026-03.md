---
kind: dataset
id: yuiseki/maff-tameike-list-jp-2026-03
description: 農林水産省が公表した「農業用ため池一覧(令和8年3月末時点)」を Parquet にしたもの。ため池防災支援システムに登録された農業用ため池 161,846 件 (47 都道府県) の、名称、所在地、座標、堤高、堤頂長、総貯水量、満水面積が入っている。
url: https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03
license: PDL1.0 (HF の表示は other / pdl-1.0)。元データは農林水産省ウェブサイトの利用規約 (PDL1.0 準拠)。出典の表示と加工した旨の明記が要る
formats:
- Parquet (parquet/maff_tameike_ichiran_20260331.parquet)
- Excel (raw/data/tameike_ichiranR8.xlsx)
crs: EPSG:4326 (十進法の経度と緯度。geometry 列は無く、lat と lon の数値列を持つ)
spatial_coverage: 日本全国 47 都道府県 (161,846 件)。兵庫県 24,019、広島県 20,383、香川県 12,187、山口県 10,050、岡山県 9,148 件など西日本に多い
temporal_coverage: 令和8年3月末時点 (2026-03-31)。2026-11-06 取得
as_of:
  list_date: 2026-03-31
  retrieved: 2026-11-06
  huggingface_revision: ee87755e53cf5b049b31bc307aca56ad950771cc
contents:
- 農業用ため池の名称、所在地 (都道府県、市区町村、町域名・番地)
- 出典の度分秒および十進法の座標 (緯度、経度) と座標判定結果
- 堤高 (m)、堤頂長 (m)、総貯水量 (千m3)、満水面積 (km2)
tables:
- name: maff_tameike_ichiran_20260331
  read: hf://datasets/yuiseki/maff-tameike-list-jp-2026-03@ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet
  grain: 1 つの農業用ため池 (出典の Excel の 1 行)
  rows: 161846
  id:
  - source_row
  join_keys:
  - column: prefecture
    type: VARCHAR
    meaning: 都道府県名。jp-admin-2026-09 の prefectures.pref_name と結ぶ
    unique: false
    joins:
    - jp-admin-2026-09:prefectures.pref_name
  no_key:
  - name: id
    note: 出典に一意のため池コードは無い。source_row (1〜161,846) を行番号として使う。完全に同じ行が 16 種類 (33 行分の重複) ある
  - name: municipality
    note: 市区町村コードは持たない。市区町村名のみ。jp-admin-2026-09 の市区町村面との空間結合、または都道府県名と市区町村名の組み合わせで結ぶ
  columns:
  - name: name
    type: VARCHAR
    meaning: ため池の名称 (出典のまま)
  - name: prefecture
    type: VARCHAR
    meaning: 都道府県名 (47 都道府県)
  - name: municipality
    type: VARCHAR
    meaning: 市区町村名 (政令市は行政区を含む場合がある)
  - name: address
    type: VARCHAR
    meaning: 町域名、番地 (1 件のみ空文字または NULL)
  - name: lat_deg
    type: DOUBLE
    meaning: 出典の緯度の度
  - name: lat_min
    type: DOUBLE
    meaning: 出典の緯度の分
  - name: lat_sec
    type: DOUBLE
    meaning: 出典の緯度の秒
  - name: lon_deg
    type: DOUBLE
    meaning: 出典の経度の度
  - name: lon_min
    type: DOUBLE
    meaning: 出典の経度の分
  - name: lon_sec
    type: DOUBLE
    meaning: 出典の経度の秒
  - name: dam_height_m
    type: DOUBLE
    meaning: 堤高 (m)
  - name: crest_length_m
    type: DOUBLE
    meaning: 堤頂長 (m)
  - name: storage_thousand_m3
    type: DOUBLE
    meaning: 総貯水量 (千m3)
  - name: surface_area_km2
    type: DOUBLE
    meaning: 満水面積 (km2)。12,197 件が NULL
  - name: source_row
    type: BIGINT
    meaning: 出典の Excel の行番号 (1 行目は見出しのため 2〜161,847)
  - name: lat
    type: DOUBLE
    meaning: 判定・修正済みの十進法の緯度 (度)。異常値や仮値の 115 件は NULL
  - name: lon
    type: DOUBLE
    meaning: 判定・修正済みの十進法の経度 (度)。異常値や仮値の 115 件は NULL
  - name: lat_original
    type: DOUBLE
    meaning: 出典の度分秒をそのまま十進法に換算した緯度 (NULL なし)
  - name: lon_original
    type: DOUBLE
    meaning: 出典の度分秒をそのまま十進法に換算した経度 (NULL なし)
  - name: coord_status
    type: VARCHAR
    meaning: 座標の判定結果 (ok, ok_carry, placeholder, fixed_lon_plus100, suspect_city_outlier)
---

# 農業用ため池一覧 令和8年3月末時点 (maff-tameike-list-jp-2026-03)

農林水産省が公表した「農業用ため池一覧(令和8年3月末時点)」を Parquet に変換したデータセット。ため池防災支援システムに登録された日本全国 47 都道府県の農業用ため池 161,846 件の名称、所在地、座標、堤高、堤頂長、総貯水量、満水面積を収録する。

分析では、農村地域の農業水利施設の空間分布、決壊や溢水のリスク評価、浸水想定区域や土砂災害警戒区域との重ね合わせ、下流集落や避難施設への到達性評価などに使う。

## どこから読むか

Hugging Face の `yuiseki/maff-tameike-list-jp-2026-03`。

```
hf://datasets/yuiseki/maff-tameike-list-jp-2026-03@ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet
```

- データセットカード: <https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03>
- 出典: 農林水産省「農業用ため池一覧(令和8年3月末時点)」(<https://www.maff.go.jp/j/nousin/bousai/bousai_saigai/b_tameike/ichiran.html>) (2026-11-06 取得)
- 利用規約: 公共データ利用規約 (第1.0版、PDL1.0)。出典の表示と加工した旨の明記が必要
- 出典の記載例: 「農業用ため池一覧(令和8年3月末時点)」(農林水産省) (https://www.maff.go.jp/j/nousin/bousai/bousai_saigai/b_tameike/ichiran.html) を加工して作成

## 座標の判定と修正

出典の Excel には測地系の明記がなく、度分秒が別々の列に分かれて入っている。十進法への換算と品質検証を行い、結果が `coord_status` 列に記録されている。

| coord_status | 行数 | 説明 |
|---|---|---|
| ok | 161,518 | 異常なし |
| ok_carry | 212 | 分または秒が 60 で繰り上がりとして換算 |
| suspect_city_outlier | 63 | 市町村内の中央値から 50 km 超離れており、修正案が無いため lat と lon は NULL |
| placeholder | 52 | 整数度のみで分秒が 0 の仮値と思われる行 (石川県 52 件)。lat と lon は NULL |
| fixed_lon_plus100 | 1 | 経度の度に 100 を足して修正 (長野県飯山市の相好。出典の 38 度台から 138 度台へ修正) |

出典の度分秒をそのまま換算した値は `lat_original` と `lon_original` に保持され、修正・欠損判定後の値が `lat` と `lon` に格納されている。

## 注意点

- Parquet ファイルにジオメトリ列 (`geometry`) は格納されていない。空間集計や可視化で点ジオメトリを扱う場合は、DuckDB の `ST_Point(lon, lat)` などで生成する。
- 完全に同一内容の重複行が 16 種類 (計 33 行) 存在する。出典のまま残されており、行番号 `source_row` で区別できる。
- 満水面積 `surface_area_km2` は 12,197 件で未入力 (NULL) となっている。
- 住所 `address` は 1 件で未入力となっている。

## DuckDB で読む

```sql
select
  name,
  prefecture,
  municipality,
  dam_height_m,
  storage_thousand_m3,
  lat,
  lon,
  coord_status
from 'hf://datasets/yuiseki/maff-tameike-list-jp-2026-03@ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet'
where coord_status = 'ok';
```
