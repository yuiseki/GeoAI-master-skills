---
kind: catalog
id: services
description: yuiseki が自前で動かしている読み取り専用のサービス。OSM の検索 (Overpass)、地名検索 (Nominatim)、経路検索 (Valhalla)、タグ辞書 (taginfo)、東京 23 区の地理グラフ (GeoSPARQL)。
url: https://github.com/yuiseki/Geo-Voyager
access: Geo-Voyager のゲートウェイを通すと /services/<id>/<サービスのパス> で呼べる。直接呼ぶなら、各サービスの url にそのパスを付ける
license: 各サービスの frontmatter を見る (OSM 由来のものは ODbL-1.0)
spatial_coverage: サービスごと
temporal_coverage: サービスごと。OSM 系のデータは 2025-09-14 で止まっている (実測)
as_of: {geo_voyager: v0.1.0, measured: 2026-10-13}
contents: [Overpass, Nominatim, Valhalla, taginfo, GeoSPARQL]
children: [overpass.md, nominatim.md, valhalla.md, taginfo.md, yuisekin-geosparql.md]
gateway:
  source: geo_voyager/service_gateway.py と services.py (Geo-Voyager v0.1.0)
  allowed_requests:
    overpass: ["POST /api/interpreter", "GET /api/interpreter", "GET /api/status"]
    nominatim: ["GET /search", "GET /reverse", "GET /lookup", "GET /status", "GET /details"]
    valhalla: ["POST /route", "POST /locate", "GET /route", "GET /locate", "GET /status"]
    taginfo: ["GET /api/4/*"]
    sparql: ["GET /geo/sparql", "POST /geo/sparql", "GET /geo/query", "POST /geo/query"]
  limits: {max_request_bytes: 65536, max_response_bytes: 4194304, timeout_seconds: 15}
  post_content_types:
    overpass: [text/plain, application/x-www-form-urlencoded]
    nominatim: [text/plain, application/x-www-form-urlencoded]
    valhalla: [application/json]
    sparql: [application/sparql-query, application/x-www-form-urlencoded]
  forbidden_query_keys: [url, endpoint, target, base_url, update]
  redirects: forbidden
---

# 自前のサービス

分析の途中で、地名から場所を引く、OSM のタグで数える、経路の長さを測る、といった問いを、データを持たずに投げて答えを得るためのサービス。データセットの reference と同じ形式の frontmatter で、できること (`operations`)、制限 (`limits`)、気をつけること (`gotchas`) を書いてある。

| サービス | できること | url |
|---|---|---|
| [overpass](overpass.md) | OSM の地物を、タグと範囲で検索、集計する | `https://overpass.yuiseki.net` |
| [nominatim](nominatim.md) | 地名から座標と OSM の ID を引く、座標から住所を引く | `https://nominatim.yuiseki.net` |
| [valhalla](valhalla.md) | 2 点以上の経路の距離と所要時間 | `https://valhalla.yuiseki.net` |
| [taginfo](taginfo.md) | OSM のタグの辞書。値の部分一致、使用数 | `https://taginfo.yuiseki.net` |
| [yuisekin-geosparql](yuisekin-geosparql.md) | 東京 23 区の区の名前と OSM の relation ID を SPARQL で引く | `http://geosparql:3030` (実行環境の内側の名前) |

## 共通の注意

- OSM 系 (Overpass、Nominatim、taginfo) は同じ時点ではない。Overpass と Nominatim は 2025-09-14 で止まっていて、taginfo は 2026-01-29 まで。同じ問いを別のサービスで確かめるときは、時点の差を書く。
- 公開されている OSM のサーバー (overpass-api.de など) ではなく、自前のものを呼ぶ。`osm-japan-src-2026-08` (2026-08-31) とは時点が違い、件数が合わないのは、時点の差による。
- ゲートウェイを通すと、URL の上書き (`url`、`endpoint`、`target`、`base_url`、`update` のキー)、リダイレクト、絶対 URL、パスの `..` が拒まれる。応答は 4 MiB までで、15 秒で切られる。
- データセットの reference と違い、サービスの行数や範囲は変わらない前提で書けない。frontmatter の `as_of` を見る。
