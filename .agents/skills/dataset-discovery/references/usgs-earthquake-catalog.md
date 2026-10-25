---
kind: service
id: usgs-earthquake-catalog
description: USGS FDSN Event API から地震イベントとマグニチュード、位置、深さを期間・範囲で検索する。
url: https://earthquake.usgs.gov/fdsnws/event/1/
protocol: FDSN Event Web Service (HTTP GET、GeoJSON または CSV など)
license: USGS の米国政府作成データは原則 public domain。出典表示を推奨。第三者由来の個別レコードは確認する
spatial_coverage: 全球。ただし観測網と検知率は地域・時期で異なる
temporal_coverage: 長期履歴を含む可変のカタログ。取得時点で更新・改訂され得る
as_of:
  checked: 2026-10-25
operations:
- name: query
  method: GET
  path: /fdsnws/event/1/query
  params:
  - starttime と endtime、minmagnitude、format、limit、offset など
  returns: イベントの GeoJSON FeatureCollection など
- name: count
  method: GET
  path: /fdsnws/event/1/count
  params:
  - query と同じ期間・範囲条件
  returns: 該当イベント数
- name: version
  method: GET
  path: /fdsnws/event/1/version
  returns: サービスの版
---

# USGS Earthquake Catalog API

[公式 API](https://earthquake.usgs.gov/fdsnws/event/1/)を認証なしで小さく照会できる。2026-10-25 に `starttime=2020-01-01&endtime=2020-01-08&minmagnitude=5` の count は35、同条件の `format=geojson&limit=5` は5件だった。version は `2.8.2`。GeoJSON の座標は経度、緯度、深さの順で、深さは km、時刻は Unix ミリ秒。イベント ID、取得時刻、条件、サービス版を一緒に保存する。

例: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2020-01-01&endtime=2020-01-08&minmagnitude=5&limit=5`

件数を比べる前に検知率、マグニチュード型、深さ・震央の精度、後からの改訂を確認する。同じ URL でも後日同じ結果になる保証はない。長期間・全球の無制限取得は避け、期間と件数を区切る。[USGS の著作権 FAQ](https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted)を参照する。
