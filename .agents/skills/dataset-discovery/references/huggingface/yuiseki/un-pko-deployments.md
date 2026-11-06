---
kind: dataset
id: yuiseki/un-pko-deployments
description: 国連の平和維持活動 (PKO) の部隊配置図 (PDF) から、LLM や VLM を使わないソフトウェアで自動的に取り出した部隊配置の点 (2022〜2025 年、計 5,110 行)。部隊の経度・緯度、ミッション名、地図日付、部隊名、兵科、規模記号、配置の判定根拠などを収録する。正確性は一切保証されない。
url: https://huggingface.co/datasets/yuiseki/un-pko-deployments
license: other (derived-from-united-nations-maps)。国連地図の利用条件 (UN Geospatial Information Section) に従う。変換ソフトウェアは Apache-2.0。正確性は一切保証されない免責事項が付く
formats:
- JSON Lines (<year>/points.jsonl)
- GeoJSON (<year>/geojson/<mission>_<date>_<sha12>.geojson)
crs: EPSG:4326 (WGS84、経度と緯度)
spatial_coverage: 国連 PKO ミッション展開地域 (中央アフリカ MINUSCA、南スーダン UNMISS、レバノン UNIFIL、コンゴ民主共和国 MONUSCO、ゴラン高原 UNDOF、キプロス UNFICYP、マリ MINUSMA、コソボ UNMIK の 8 ミッション)
temporal_coverage: 2022〜2025 年 (PDF の作成日)
as_of:
  retrieved: 2026-11-06
  huggingface_revision: 528afe3d928c0d99b846d928d08100546c014785
contents:
- PKO 部隊配置の点 (経度、緯度)
- ミッション名 (mission)、地図作成日 (map_date)
- 派遣国名 (label)、記号内略号 (inner)、兵科 (arm)、部隊規模 (echelon, size_marks)
- 位置同定手法と精度指標 (located_by, panel_local, map_ok, std_px)
- 原本 PDF の SHA-256、抽出ツールコミット、免責事項文字列
tables:
- name: points_2022
  read: hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/2022/points.jsonl
  grain: 1 つの部隊の配置点
  rows: 1229
  id: []
  no_key:
  - name: id
    note: 部隊配置点には一意の ID 列はない。ファイル名と行番号、またはミッション・日付・座標で識別する
  columns: &pko_columns
  - name: file
    type: VARCHAR
    meaning: 対応する GeoJSON ファイル名
  - name: mission
    type: VARCHAR
    meaning: PKO ミッションの略称 (MINUSCA, UNMISS, UNIFIL, MONUSCO, UNDOF, UNFICYP, MINUSMA, UNMIK)
  - name: map_date
    type: VARCHAR
    meaning: 地図 PDF の作成日 (YYYYMMDD。地図が示す状況の時点とは必ずしも一致しない)
  - name: lon
    type: DOUBLE
    meaning: 経度 (WGS84。部隊引き出し線の先端、または基地記号の座標)
  - name: lat
    type: DOUBLE
    meaning: 緯度 (WGS84)
  - name: label
    type: VARCHAR
    meaning: 部隊枠の横に記載されたテキスト (派遣国名など)
  - name: inner
    type: VARCHAR
    meaning: 部隊記号枠内の略号 (HQ, UNMO, FPU など)
  - name: symbol
    type: VARCHAR
    meaning: 記号枠内に描画されたシンボル
  - name: arm
    type: VARCHAR
    meaning: シンボルから判定された兵科 (NATO APP-6 準拠)
  - name: echelon
    type: VARCHAR
    meaning: 部隊規模 (echelon)
  - name: size_marks
    type: VARCHAR[]
    meaning: 部隊規模記号のマーク
  - name: nearest_text
    type: VARCHAR
    meaning: 点に最も近い大文字テキスト (地名の手がかりだが、地名そのものとは限らない)
  - name: stack
    type: BIGINT
    meaning: 重なり順
  - name: located_by
    type: VARCHAR
    meaning: 位置同定の根拠 (leader は引き出し線の先端、adjacent は記号脇の地名点)
  - name: panel_local
    type: BOOLEAN
    meaning: 地図全体ではなく個別のパネル領域で点ごとに検査されたか
  - name: map_ok
    type: BOOLEAN
    meaning: 地図全体が全ての検証関門を通過したか
  - name: std_px
    type: DOUBLE
    meaning: ジャックナイフ法による推定位置のばらつき (ピクセル)
  - name: no_warranty
    type: VARCHAR
    meaning: 免責事項文字列
  - name: based_on
    type: VARCHAR
    meaning: 典拠表示文字列 (Based on United Nations map)
  - name: source_sha256
    type: VARCHAR
    meaning: 原本 PDF ファイルの SHA-256 ハッシュ値
  - name: tool_commit
    type: VARCHAR
    meaning: 抽出ツール (Geo-Ref-skills) のコミット SHA
  - name: disclaimer
    type: VARCHAR
    meaning: 全体免責文
- name: points_2023
  read: hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/2023/points.jsonl
  grain: 1 つの部隊の配置点
  rows: 1071
  id: []
  columns: *pko_columns
- name: points_2024
  read: hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/2024/points.jsonl
  grain: 1 つの部隊の配置点
  rows: 1556
  id: []
  columns: *pko_columns
- name: points_2025
  read: hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/2025/points.jsonl
  grain: 1 つの部隊の配置点
  rows: 1254
  id: []
  columns: *pko_columns
---

# 国連 PKO 部隊配置点データ (un-pko-deployments)

国連の平和維持活動 (PKO) の部隊配置図 (PDF) から、LLM や VLM を介さずに規則ベースの画像解析ソフトウェアで自動抽出した部隊配置の点データセット。2022 年から 2025 年までの 4 年間分、計 5,110 件の部隊位置と属性を収録する。

正確性は一切保証されない。位置、部隊名、規模、兵科は誤っている可能性があり、国連の公式製品ではなく、国連が承認したものでもない。

分析では、紛争地における平和維持部隊の地理的展開パターン、組織的暴力事件 (UCDP GED など) や難民移動との空間的距離、紛争予防・抑止の空間分析の探索的検討に用いる。

## どこから読むか

Hugging Face の `yuiseki/un-pko-deployments`。

```
hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/<year>/points.jsonl
```

- データセットカード: <https://huggingface.co/datasets/yuiseki/un-pko-deployments>
- 原資料: 国連地理空間情報セクション (United Nations Geospatial Information Section) の部隊配置図 (PKO deployment maps)
- 利用条件: 国連地図の利用規約 (<https://www.un.org/geospatial/en/mandates/public>)。国連の地図参照番号は規約に従い全ファイルから除外されている。抽出ソフトウェアは Apache-2.0 (<https://github.com/yuiseki/Geo-Ref-skills>)
- 免責: ABSOLUTELY NO WARRANTY (各行に `no_warranty` および `disclaimer` 列が付与されている)

## 収録件数とミッション

年別の内訳:

| 年 (config) | 地図数 | 地図上の部隊総数 | 座標が特定された部隊数 (収録行数) |
|---|---|---|---|
| 2022 | 28 | 1,987 | 1,229 |
| 2023 | 17 | 1,214 | 1,071 |
| 2024 | 27 | 1,751 | 1,556 |
| 2025 | 21 | 1,322 | 1,254 |
| 合計 | 93 | 6,274 | 5,110 |

対象ミッション (4 年間の合計件数):
- MINUSCA (中央アフリカ): 1,128 件
- UNMISS (南スーダン): 1,055 件
- UNIFIL (レバノン): 1,004 件
- MONUSCO (コンゴ民主共和国): 889 件
- UNDOF (ゴラン高原): 605 件
- UNFICYP (キプロス): 223 件
- MINUSMA (マリ): 166 件
- UNMIK (コソボ): 40 件

## 注意点と限界

- 点の座標は、地図上で部隊記号の引き出し線が指し示す位置 (基地や町を示す記号の場所) であり、実際の駐屯地の位置とは必ずしも一致しない (例: MONUSCO の地図ではキンシャサの記号がブラザヴィルとの干渉を避けて東へ約 0.35 度ずらして描画されている)。
- 位置を自動同定できなかった部隊 (検証関門を通過しなかった部隊) は推測補完せず除外されている。
- 同一内容の地図を含む複数の PDF が存在する場合がある (例: UNMISS の 2025-05-09 版など)。ハッシュ値ごとに別レコードとして保持されている。
- 地図日付 `map_date` は PDF の作成日であり、部隊配置の現況時点とはタイムラグが存在しうる。

## DuckDB で読む

```sql
select
  mission,
  map_date,
  label,
  inner,
  arm,
  echelon,
  lon,
  lat,
  located_by
from read_json_auto('hf://datasets/yuiseki/un-pko-deployments@528afe3d928c0d99b846d928d08100546c014785/2024/points.jsonl')
where map_ok = true;
```
