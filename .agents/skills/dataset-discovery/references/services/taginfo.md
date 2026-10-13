---
kind: service
id: taginfo
description: 自前の OSM タグの辞書 (taginfo)。値の部分一致の検索、キーの値の一覧、タグの使用数。
url: https://taginfo.yuiseki.net
protocol: taginfo
license: ODbL-1.0 (統計の元の OSM データ)
spatial_coverage: 全世界
temporal_coverage: 統計の期限は 2026-01-29T00:59:50Z まで (応答の data_until で実測)
as_of: {data_until: 2026-01-29T00:59:50Z, measured: 2026-10-13}
operations:
  - name: search_by_value
    method: GET
    path: /api/4/search/by_value
    params: ["query (値の部分一致)", "page (1 から)", "rp (件数)", "sortname=count_all", "sortorder=desc"]
    returns: JSON の root は dict。payload['data'] の各要素が key、value、count_all
  - name: search_by_keyword
    method: GET
    path: /api/4/search/by_keyword
    params: ["query (説明の検索)"]
    returns: キーワードに合うタグ
  - name: key_values
    method: GET
    path: /api/4/key/values
    params: ["key", "page (1 から。必須)", "rp (件数。必須)", "sortname=count", "sortorder=desc"]
    returns: payload['data'] の各要素が value、count、fraction、in_wiki、description。使用数のフィールドは count (count_all ではない)
  - name: tag_stats
    method: GET
    path: /api/4/tag/stats
    params: ["key", "value"]
    returns: payload['data'] の要素のうち type が all のものの count が、そのタグの全体の使用数
  - name: tags_list
    method: GET
    path: /api/4/tags/list
    params: ["key か tags (どちらか必須)"]
    returns: タグの一覧。query 検索には使わない
limits: {http_timeout_seconds: 15}
gotchas:
  - "search/by_value は部分一致。ramen を引くと cuisine=ramen (8,213) のほかに cuisine=noodle;ramen (1,073) なども返る (2026-10-13 実測。使用数は data_until の時点)。1 つのタグの使用数には使わず、tag/stats を使う。"
  - "key/values は page と rp の両方が必須。どちらかが無いと HTTP 412 (number of results too large, use paging) になる。"
  - "使用数の列名が違う。search/by_value は count_all、key/values は count。"
  - "tags/list は key か tags が必須で、検索には使えない。"
---

# taginfo

OSM のタグの辞書。分析では、どのタグで対象を選ぶかを決める (例は ramen を扱う cuisine の値)、タグの使用数で候補の大きさを見積もる、ことに使う。データは Overpass より新しい (2026-01 まで) が、検索の対象の `overpass` は 2025-09 で止まっている。

```sh
curl -sS 'https://taginfo.yuiseki.net/api/4/search/by_value?query=ramen&page=1&rp=2&sortname=count_all&sortorder=desc'
```

## 気をつけること

- 使用数は全世界の値で、日本の数ではない。日本の件数は、`overpass` か `osm-japan-src-2026-08` で数える。
- 同じ意味のタグが複数ある (`cuisine=ramen` と `cuisine=noodle;ramen`)。Overpass で数える前に、どの値を含めるかを決める。
