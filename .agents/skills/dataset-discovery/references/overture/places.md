---
kind: dataset
id: overture/places
description: 全世界の施設 (POI) の点。名前、基本カテゴリと階層のカテゴリ、ブランド、営業状態、信頼度、電話やウェブサイト、出どころ (データセットとライセンス) を持つ。評価、口コミ、営業時間、価格帯は無い。
url: https://stac.overturemaps.org/
license: 行ごとに出どころのライセンスがある。ロンドンで測った範囲では CDLA-Permissive-2.0、Apache-2.0 (Foursquare)、CC0-1.0 (AllThePlaces)。collection.json の license は other
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全世界。版 2026-10-21.0 で 88,418,121 行
temporal_coverage: 版ごと (月に 1 回ほど)。版 2026-10-21.0 を実測。出どころの更新日は行ごとに違う
as_of:
  release: 2026-10-21.0
contents:
- 施設の点と属性
tables:
- name: place
  read: s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/*.parquet
  grain: 1 つの施設
  rows: 88418121
  id:
  - id
---

# Overture Maps の places

版 2026-10-21.0 を、ロンドンの範囲 (経度 -0.52〜0.34、緯度 51.28〜51.70、bbox 列で絞る) で 2026-11-12 に測った。範囲の行は 756,060。

## 列

| 列 | 型 | 中身と実測 |
|---|---|---|
| id | VARCHAR | 施設の id |
| geometry | GEOMETRY | 点 |
| bbox | STRUCT(xmin, xmax, ymin, ymax) | 範囲で絞るのに使う |
| names | STRUCT | `names."primary"` が主の名前 |
| basic_category | VARCHAR | 基本カテゴリ。範囲で 274 種類。欠けがある (後述) |
| taxonomy | STRUCT("primary", hierarchy VARCHAR[], alternates VARCHAR[]) | 階層。coffee_shop は food_and_drink > non_alcoholic_beverage_venue > coffee_shop、その下に coffee_roastery |
| brand | STRUCT | `brand.names."primary"` がブランド名。ロンドンのコーヒーショップでは Costa Coffee 424、Starbucks 203、Caffè Nero 183、欠け 4,165 (Costa と Costa Coffee の表記の揺れがある) |
| operating_status | VARCHAR | 同じ試しの 756,085 行で open 386,490、permanently_closed 33,692、temporarily_closed 73、欠け 335,830 |
| confidence | DOUBLE | 0〜1。範囲の 10、50、90 パーセンタイルは 0.5、0.77、0.99 |
| sources | STRUCT(property, dataset, license, record_id, update_time, confidence, ...)[] | 出どころ。最初の試しの絞り方 (bbox.xmin と ymin だけで絞った 756,085 行) で数えた件数は Overture 756,085、BrightQuery 750,670、meta 214,838、Microsoft 110,478、Foursquare 67,814、AllThePlaces 19,815 など (1 行に複数) |

## 注意

- basic_category と taxonomy が両方欠けている行がある。カテゴリで絞るとき、欠けを「他のカテゴリ」に数えないと、件数が合わなくなる (ロンドンの範囲で、欠けを考えずに数えると 36,901 行がどの理由にも入らなかった)。
- 基本カテゴリだけで取ると、階層の下位 (coffee_roastery) が落ちる。階層のどこかに含むかで取る。
- operating_status の欠けは、営業中の意味ではない。ロンドンのコーヒーショップ 5,333 店では、open 2,257、permanently_closed 253、temporarily_closed 5、欠け 2,818。
- OpenStreetMap の amenity=cafe (2025-09-14 のデータ) と、H3 解像度 8 のセルごとの店数の順位相関は 0.6977。Overture のカフェとコーヒーショップは 10,778 店、OSM は 7,040 件で、Overture にだけ店のあるセルが 29% あった。
- 範囲の全ての行を S3 から読むのに、この環境で 7 分ほどかかった (101 MB)。範囲は 1 回だけ写し、以降は写しを読む。
