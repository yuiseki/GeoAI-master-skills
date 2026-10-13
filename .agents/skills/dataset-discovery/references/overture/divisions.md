---
kind: dataset
id: overture/divisions
description: 国から町丁目までの行政区域の、点、面、境界線。国の中の細かい階層 (日本なら都道府県、市区町村、町丁目) がある。
url: https://stac.overturemaps.org/
license: ODbL-1.0
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全世界。日本は都道府県 47、市区町村 1,742 など
temporal_coverage: 版 2026-09-23.1 を実測。版ごとに行が足され、消され、直される
as_of:
  release: 2026-09-23.1
contents:
- 行政区域の点と属性
- 行政区域の面
- 行政区域どうしの境界線
tables:
- name: division
  read: s3://overturemaps-us-west-2/release/2026-09-23.1/theme=divisions/type=division/*.parquet
  grain: 1 つの行政区域の代表点と属性 (名前、階層、親、人口、Wikidata)
  rows: 4688229
  id:
  - id
  join_keys:
  - column: country
    type: VARCHAR
    meaning: ISO の 2 文字の国コード (係争地は X で始まる独自のコード)
    unique: false
    joins:
    - natural-earth:ne_10m_admin_0_countries.ISO_A2_EH
    note: subtype が country の 219 件のうち 199 件が一致する
  - column: region
    type: VARCHAR
    meaning: ISO 3166-2 の地域コード (日本の都道府県なら JP-47 など)
    unique: false
    joins: []
  no_key:
  - name: code5
    note: 日本の市区町村コードは持たない。jp-admin-2026-09 とは、名前ではなく空間結合で結ぶ
  - name: osm_id
    note: OpenStreetMap の ID の列は無い
  columns:
  - name: subtype
    type: VARCHAR
    meaning: 階層。country、region、county (日本では市区町村)、locality、neighborhood など
  - name: names."primary"
    type: VARCHAR
    meaning: 名前。言語が階層で違う (日本の都道府県は日本語、市区町村はローマ字だった)
  - name: population
    type: INTEGER
    meaning: 人口。日本の locality 8
    042 件のうち 1: null
    748 件にだけある: null
- name: division_area
  read: s3://overturemaps-us-west-2/release/2026-09-23.1/theme=divisions/type=division_area/*.parquet
  grain: 1 つの行政区域の面。country と region は、陸の面と海の面 (領海) に分かれる
  rows: 1080667
  id:
  - id
  join_keys:
  - column: division_id
    type: VARCHAR
    meaning: division.id を指す
    unique: false
    joins:
    - division.id
    note: 面の名前や親は division から結ぶ
  columns:
  - name: is_land
    type: BOOLEAN
    meaning: 陸の面なら true、領海の面なら false。点を面に入れるときは絞る
- name: division_boundary
  read: s3://overturemaps-us-west-2/release/2026-09-23.1/theme=divisions/type=division_boundary/*.parquet
  grain: 2 つの行政区域の境界線
  rows: 87530
  id:
  - id
---

# Overture: divisions

国から町丁目までの行政区域。Natural Earth には無い、国の中の細かい階層 (日本なら都道府県、市区町村、町丁目) がある。分析の単位や、集計の単位を変える MAUP の比較に使う。

## 3 つの種類

版 2026-09-23.1 (2026-10-10 実測)。

| 種類 | 1 行 | 行数 | ファイル |
|---|---|---:|---:|
| `division` | 1 つの行政区域の代表点と属性 (名前、階層、親、人口、Wikidata) | 4,688,229 | 1 |
| `division_area` | 1 つの行政区域の面 | 1,080,667 | 8 |
| `division_boundary` | 2 つの行政区域の境界線 | 87,530 | 1 |

`division_area.division_id` が `division.id` を指す。面の属性 (名前、親) は `division` から結ぶ。

## 階層 (subtype)

全世界の `division` の行数: locality 3,501,039、neighborhood 728,226、microhood 237,753、macrohood 156,594、county 38,933、localadmin 21,483、region 3,929、country 219、dependency 53。

日本 (`country = 'JP'`) の内訳:

| subtype | admin_level | division (点) | division_area (面) | 中身 |
|---|---:|---:|---:|---|
| country | 0 | 1 | 2 | 日本 |
| region | 1 | 47 | 86 | 都道府県。`region` 列は `JP-47` のような ISO 3166-2 |
| county | 2 | 1,742 | 1,742 | 市区町村 (会津若松、五泉、東金など) |
| locality | なし | 8,042 | 2,134 | 地名の点。面があるのは一部 |
| macrohood | なし | 378 | 183 | |
| neighborhood | なし | 131,649 | 19,703 | 町丁目など。面があるのは 15% |
| microhood | なし | 79,172 | 3,353 | |

- 点 (`division`) の数と面 (`division_area`) の数が違う。locality 以下は、点だけで面の無いものが多い。面で集計するなら、面のある階層を選ぶ。
- country と region の面は、陸の面 (`is_land = true`) と海の面 (領海、`is_land = false`) に分かれている。日本の都道府県は 86 面のうち陸が 47。点を面に入れるなら `is_land` で絞らないと、陸と海で二重に入る、または海の面に入る。
- 名前 (`names."primary"`) の言語が階層で違う。日本の都道府県は「沖縄県」と日本語、市区町村は「Toogane」(東金) のようにローマ字だった。名前で結ばず、id か `region` のコードで結ぶ。
- 日本の locality 8,042 件のうち、`population` があるのは 1,748、`wikidata` があるのは 2,275。

## Natural Earth との結合

`subtype = 'country'` の `country` 列 (2 文字) を Natural Earth の `ISO_A2_EH` と結ぶと、219 件のうち 199 件が一致する。一致しない 20 件は全て `X` で始まる Overture 独自のコードで、係争地を国と同じ階層に置いたもの: 歯舞 (XA)、竹島についての日本の主張の範囲 (XB)、尖閣諸島 (XD)、ガザ (XG)、ゴラン高原 (XH)、択捉 (XI)、色丹 (XO)、国後 (XU)、西沙諸島 (XP)、南沙諸島 (XR)、ヨルダン川西岸 (XW) など。国境の見方 (Natural Earth は既定で de facto) の違いと合わせて、どちらに入れたかを書く。
