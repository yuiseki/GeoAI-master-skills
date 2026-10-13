---
kind: service
id: overpass
description: OSM の読み取り専用の検索 (Overpass API)。タグと範囲で地物を選び、数える、取り出す。
url: https://overpass.yuiseki.net
protocol: overpass
license: ODbL-1.0 (応答の osm3s に出典が付く)
spatial_coverage: 全世界 (planet から構築した既存のデータベース)
temporal_coverage: データは 2025-09-14T23:59:55Z で止まっている (/api/timestamp と応答の timestamp_osm_base で実測)
as_of: {data: 2025-09-14T23:59:55Z, measured: 2026-10-13}
operations:
  - name: query
    method: [GET, POST]
    path: /api/interpreter
    params: ["GET は data に Overpass QL", "POST は text/plain の body に QL"]
    returns: JSON を受け取るには QL の先頭に [out:json]; が必須。結果は JSON の elements
  - name: status
    method: GET
    path: /api/status
    returns: 接続の情報、スロット数、実行中のクエリ (テキスト)
gotchas:
  - "先頭の [out:json] を忘れると XML が返る (実測)。"
  - "件数は out count; で取る。返りは JSON で、data['elements'][0]['tags']['total'] が件数 (文字列の整数)。台東区の amenity=cafe は 2025-09-14 のデータで total が 368 (nodes 357、ways 11、relations 0) だった (2026-10-13 実測)。"
  - "範囲は area で指定する。relation を使うなら area の ID は relation の ID に 3600000000 を足した整数 (Nominatim の osm_type が relation の osm_id)。台東区は relation 1758888、area は 3601758888 (実測)。(area:<id>) と書く。文字列の連結や乗算ではない。"
  - "数値の area ID はコロンで書く (area:3601758888)。ドットは名前つきの集合 (area.name) を指し、数値の ID と書くと、意図と違う集合を指す。"
  - "タグの比較は = で、== ではない。bbox は south,west,north,east の順。国境のような範囲の検索には、bbox ではなく area を使う。"
  - "area が存在することを先に確かめる (area(<id>);out ids;)。存在しない area は、0 件ではなくエラーにする。"
  - "クエリには [timeout:12] のように秒数を付ける (実測の例はすべて 12)。応答に remark があれば、失敗として扱う。"
  - "nwr は、ノード、ウェイ、リレーションをまとめて選ぶ。ノードだけなら node、ウェイだけなら way を書く。"
---

# Overpass

OSM の地物を、タグと範囲で選んで数える、取り出す。分析では、POI の数や密度の特徴量、特定のタグの地物の位置、行政区域ごとの集計に使う。データを丸ごと読むより軽いが、時点が `osm-japan-src-2026-08` (2026-08-31) より古い。

## 数える

```
[out:json][timeout:12];
nwr["amenity"="cafe"](area:3601758888);
out count;
```

```sh
curl -sS -G 'https://overpass.yuiseki.net/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:12];nwr["amenity"="cafe"](area:3601758888);out count;'
```

## 気をつけること

- 範囲を area で指すのは、行政区域のような面を使うため。area の ID は、`nominatim` で名前から `osm_type` と `osm_id` を引き、relation なら 3600000000 を足す。
- クエリが重いときは、範囲を狭める。
- 件数を `osm-japan-src-2026-08` と比べるなら、時点の差 (約 11 か月) を結論に書く。
