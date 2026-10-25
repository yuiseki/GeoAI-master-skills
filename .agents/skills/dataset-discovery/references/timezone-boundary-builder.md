---
kind: dataset
id: timezone-boundary-builder-2026d
description: Timezone Boundary Builder の2026d固定版。IANAタイムゾーンの地理的境界の GeoJSON。
url: https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2026d
license: 境界データは ODbL 1.0。リポジトリのコードの MIT ライセンスと混同しない
formats:
- GeoJSON ZIP
crs: GeoJSON の経度・緯度 (WGS84)。実読したファイルの座標範囲の検査は未実施
spatial_coverage: 全球。境界の細部は入力元と作図法に依存
temporal_coverage: 2026d 版。現実の時差や夏時間の履歴を内包しない
as_of:
  checked: 2026-10-25
contents:
- tzid と境界 MultiPolygon
tables:
- name: timezones_now
  read: https://github.com/evansiroky/timezone-boundary-builder/releases/download/2026d/timezones-now.geojson.zip
  grain: 2026d で現時点の同じ時間帯をまとめた面。IANA tzid との対応は版に依存
  rows: 65
  id: []
- name: timezones_full
  read: https://github.com/evansiroky/timezone-boundary-builder/releases/download/2026d/timezones.geojson.zip
  grain: タイムゾーン境界の面。未実読
  rows: null
  id: []
---

# Timezone Boundary Builder 2026d

[2026d リリース](https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2026d)の `timezones-now.geojson.zip` を2026-10-25 に実読した。圧縮サイズ25,001,594バイト、展開した `combined-now.json` は81,115,823バイト。GeoJSON FeatureCollection の feature は65件で、`tzid` 属性と MultiPolygon がある。これは「現在同じ時間帯」をまとめた版で、全 IANA タイムゾーンの区分数ではない。完全版 `timezones.geojson.zip` はリリース API 上で51,716,657バイトだが中身は未読。

境界と時刻の変換は別問題。時差や夏時間、歴史上の変更には別途 IANA tzdb を用いる。点を境界に結ぶ際は海上・国境・無所属の点の扱いを決める。ライセンスは[データ用 ODbL 1.0](https://github.com/evansiroky/timezone-boundary-builder/blob/master/DATA_LICENSE)で、派生データベースの再配布には条件がある。コードの MIT を境界に適用しない。
