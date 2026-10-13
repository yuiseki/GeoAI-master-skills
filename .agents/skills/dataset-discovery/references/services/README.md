---
kind: catalog
id: services
description: yuiseki が自前で動かしている読み取り専用のサービス。OSM の検索 (Overpass)、地名検索 (Nominatim)、経路検索 (Valhalla)、タグ辞書 (taginfo)。
url: https://overpass.yuiseki.net
access: 各サービスの url にパスを付けて、HTTP で直接呼ぶ。認証は要らない
license: 各サービスの frontmatter を見る (OSM 由来のものは ODbL-1.0)
spatial_coverage: サービスごと
temporal_coverage: サービスごと。Overpass と Nominatim のデータは 2025-09-14 で止まっている (実測)
as_of:
  measured: 2026-10-13
contents:
- Overpass
- Nominatim
- Valhalla
- taginfo
children:
- overpass.md
- nominatim.md
- valhalla.md
- taginfo.md
---

# 自前のサービス

分析の途中で、地名から場所を引く、OSM のタグで数える、経路の長さを測る、といった問いを、データを持たずに投げて答えを得るためのサービス。データセットの reference と同じ形式の frontmatter で、できること (`operations`)、気をつけること (`gotchas`) を書いてある。

| サービス | できること | url |
|---|---|---|
| [overpass](overpass.md) | OSM の地物を、タグと範囲で検索、集計する | `https://overpass.yuiseki.net` |
| [nominatim](nominatim.md) | 地名から座標と OSM の ID を引く、座標から住所を引く | `https://nominatim.yuiseki.net` |
| [valhalla](valhalla.md) | 2 点以上の経路の距離と所要時間 | `https://valhalla.yuiseki.net` |
| [taginfo](taginfo.md) | OSM のタグの辞書。値の部分一致、使用数 | `https://taginfo.yuiseki.net` |

## 共通の注意

- OSM 系 (Overpass、Nominatim、taginfo) は同じ時点ではない。Overpass と Nominatim は 2025-09-14 で止まっていて、taginfo は 2026-01-29 まで。同じ問いを別のサービスで確かめるときは、時点の差を書く。
- 公開されている OSM のサーバー (overpass-api.de など) ではなく、自前のものを呼ぶ。`osm-japan-src-2026-08` (2026-08-31) とは時点が違い、件数が合わないのは、時点の差による。
- データセットの reference と違い、サービスの行数や範囲は変わらない前提で書けない。frontmatter の `as_of` を見る。
