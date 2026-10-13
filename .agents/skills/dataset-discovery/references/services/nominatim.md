---
kind: service
id: nominatim
description: 自前の地名検索と逆ジオコーディング (Nominatim)。名前から座標と OSM の ID を引く。
url: https://nominatim.yuiseki.net
protocol: nominatim
license: ODbL-1.0
spatial_coverage: 全世界 (日本で実測)
temporal_coverage: データは 2025-09-14T23:59:55Z で止まっている (/status の data_updated で実測。ソフトのバージョン 5.2.0)
as_of: {data: 2025-09-14T23:59:55Z, measured: 2026-10-13}
operations:
  - {name: search, method: GET, path: /search, params: ["q", "limit", "format=jsonv2"], returns: JSON の配列。lat、lon、osm_type、osm_id、boundingbox を持つ}
  - {name: reverse, method: GET, path: /reverse, params: ["lat", "lon", "format=jsonv2"], returns: 座標の最寄りの地物と住所}
  - {name: lookup, method: GET, path: /lookup, params: ["osm_ids", "format=jsonv2"], returns: OSM の ID から地物}
  - {name: details, method: GET, path: /details, returns: 1 つの地物の詳しい情報}
  - {name: status, method: GET, path: /status, returns: 状態とデータの更新日時}
gotchas:
  - "format=jsonv2 を付ける。/search は q と limit を受け取り、JSON の配列を返す。"
  - "boundingbox は [south, north, west, east] の順の文字列の配列。台東区は ['35.6948026', '35.7316244', '139.7622652', '139.8098027'] だった (2026-10-13 実測)。Overpass の bbox の順 (south, west, north, east) とは違う。"
  - "boundingbox は国境や行政界そのものではない。他国を含むことがある。国内の検索に使うなら、osm_type と osm_id で境界の面を取って絞る。"
  - "台東区を q=台東区 で引くと osm_type が relation、osm_id が 1758888 の 1 件が返った (実測)。Overpass の area ID はこの osm_id に 3600000000 を足す。"
---

# Nominatim

名前から場所を引く。分析では、地名で指定された対象の座標、境界の取得の起点、Overpass の範囲 (area) の ID を得るために使う。

```sh
curl -sS 'https://nominatim.yuiseki.net/search?q=%E5%8F%B0%E6%9D%B1%E5%8C%BA&format=jsonv2&limit=2'
```

## 気をつけること

- 結果が複数返るときは、`osm_type` と種類 (`category`、`type`) を見て、使う 1 件を決める。台東区の例では 1 件だった。
- データは 2025-09-14 で止まっている。それ以降に変わった地名は反映されない。
