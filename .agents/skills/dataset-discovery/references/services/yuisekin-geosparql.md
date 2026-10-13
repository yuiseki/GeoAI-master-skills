---
kind: service
id: yuisekin-geosparql
description: YuisekinGeoSPARQL の、固定した地理グラフ (SPARQL)。東京 23 区の 23 の区 (gs:Ward) の日本語名と、OSM の relation の URI (gs:osmRelation) を持つ。
url: http://geosparql:3030
protocol: sparql
license: 不明 (グラフの元の OSM は ODbL-1.0)
spatial_coverage: 東京 23 区
temporal_coverage: グラフを固定した日付は確かめていない
as_of: {source: Geo-Voyager v0.1.0 の services.py。この環境から到達できる URL は確かめていない}
operations:
  - name: select
    method: [GET, POST]
    path: /geo/sparql
    params: ["GET は query", "POST は application/sparql-query か application/x-www-form-urlencoded"]
    returns: SELECT の JSON の root は dict。行の配列は payload['results']['bindings']。各変数は dict で、文字列は row['<変数>']['value']
  - {name: query, method: [GET, POST], path: /geo/query, returns: 同じ SPARQL の窓口}
limits: {http_timeout_seconds: 15}
gotchas:
  - "url の http://geosparql:3030 は、Geo-Voyager の実行環境の内側の名前で、外からは引けない (公開の名前は確かめていない)。この情報は Geo-Voyager v0.1.0 の記述で、ここでは実機で確かめていない。"
  - "OSM の relation の ID は gs:osmRelation (geo:osmRelation ではない) から取る。値は OSM の relation の URI で、末尾が正の数値の ID。URI をそのまま SELECT し、末尾の数字を取り、数字だけにする。gs:osmId は負の値を含むので、relation の ID と同一視しない。"
  - "必須のパターン: ?ward gs:osmRelation ?relation。SELECT ?label ?relation にし、?ward の URI ではなく ?relation の値を使う。"
  - "rdfs:label は日本語 (@ja) と英語 (@en) が同じ個体にある。日本語の一覧は FILTER(LANG(?label) = 'ja') で 1 個体 1 行にし、ORDER BY ?label で順序を固定する。言語タグなしの文字列とは一致しない。"
  - "名前の検索は、ラベルの変数を rdfs:label で束縛してから FILTER(STR(?label) = '対象の名前') で、言語タグを除いた文字列同士を比べる。個体の URI は推測せず、ラベルから検索して取る。"
  - "各クエリに PREFIX を明示する。サーバーに暗黙の prefix は登録されていない。名前空間は geo が http://www.opengis.net/ont/geosparql#、gs が https://yuiseki.net/geosparql/schema#、rdfs が http://www.w3.org/2000/01/rdf-schema#。"
  - "REPLACE や複雑な正規表現は使わない。"
---

# yuisekin-geosparql

東京 23 区の区を、名前から OSM の relation の ID に結ぶための小さなグラフ。`overpass` の area の ID (relation の ID に 3600000000 を足す) を、名前から得る経路に使う。

```sparql
PREFIX gs: <https://yuiseki.net/geosparql/schema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label ?relation WHERE {
  ?ward a gs:Ward ; rdfs:label ?label ; gs:osmRelation ?relation .
  FILTER(LANG(?label) = "ja")
} ORDER BY ?label
```

## 気をつけること

- 上のクエリは Geo-Voyager の記述から組み立てたもので、実機で流してはいない。
- 23 区の外は入っていない。ほかの市区町村の relation の ID は `nominatim` で引く。
