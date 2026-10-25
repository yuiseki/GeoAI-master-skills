---
kind: service
id: nasa-firms
description: NASA FIRMS の衛星による活発な火災・熱異常の検出点を検索する。CSV API は無料 MAP_KEY が必要。
url: https://firms.modaps.eosdis.nasa.gov/api/
protocol: HTTPS の CSV API。別に公開の地域別 KML/KMZ 配信がある
license: NASA Earthdata のデータ利用方針と製品固有の条件。NASA-led mission は制限表示がなければ原則 CC0、非 NASA ソースは提供元の条件を確認。出典表示を推奨
spatial_coverage: 全球と地域別。検出されない場所は火災が無いことを意味しない
temporal_coverage: センサーと NRT・SP の処理系列ごとに異なる。直近の検出は後で改訂され得る
as_of:
  checked: 2026-10-25
operations:
- name: data_availability
  method: GET
  path: /api/data_availability/csv/{MAP_KEY}/{SENSOR}
  params:
  - 無料の個人 MAP_KEY と、ALL または対象センサー
  returns: センサー別の利用可能な日付範囲を CSV で返す。鍵が無いため実応答は未確認
- name: area
  method: GET
  path: /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA_COORDINATES}/{DAY_RANGE}
  params:
  - センサー、bbox または world、1〜5日の期間など。追加の日付は公式仕様を確認
  returns: 検出点の CSV。鍵が無いため列と行は未実測
- name: country
  method: GET
  path: /api/country/csv/{MAP_KEY}/{SOURCE}/{COUNTRY_CODE}/{DAY_RANGE}
  params:
  - 国コード、センサー、期間
  returns: 国ごとの検出点の CSV。鍵が無いため未実測
- name: regional_kml
  method: GET
  path: /usfs/api/kml_fire_footprints/
  params:
  - sensor と region と date_span を指定。公開の地域別 KML bundle から URL を得る
  returns: 直近の検出点の KMZ。米国本土の7日分を実読
---

# NASA FIRMS

[公式 API](https://firms.modaps.eosdis.nasa.gov/api/)は検索用の CSV を提供するが、[無料の MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key)が必要。この環境にはキーが無かったため、`area`、`country`、`data_availability` の CSV 応答は未検証。鍵をカードやコマンドの出力に書かず、実利用時に小さい bbox と1日で列・欠損・時刻を確認する。公式の上限は 10 分間に 5,000 transaction だが、重い検索は複数として数えられる。

代わりに、[公式の地域別 KML bundle](https://firms.modaps.eosdis.nasa.gov/content/active_fire/kmz_bundles/)が指す米国本土・ハワイの Suomi-NPP VIIRS 7日間 KMZ を2026-10-25に認証なしで実読した。取得 URL は以下のとおり。

```text
https://firms.modaps.eosdis.nasa.gov/usfs/api/kml_fire_footprints/?sensor=suomi-npp-viirs-c2&region=USA%20(Conterminous)%20and%20Hawaii&date_span=7d
```

その応答は1,041,014バイト、SHA-256 は `18d2d8080ce90e29870efd418ce3b1d6344f73a1a55d068646579021213ca1ce`。内部 KML は24,408 Placemark で、最初の点の説明には緯度・経度、UTC の検出時刻、センサー、confidence、scan、track、FRP があった。これは時間で変わる KML であり、CSV API の列や全球の件数の確認にはならない。

1 検出点は1件の火災ではない。雲、衛星の通過、センサーの検出限界で欠けが生じる。研究に近実時間性が不要なら、[公式の案内](https://firms.modaps.eosdis.nasa.gov/content/active_fire/)に従い Standard Processing (`*_SP`) を選ぶ。NRT は後で SP に置換されることがある。[NASA の利用方針](https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy)をセンサーの元製品の条件と併せて確認し、FIRMS 全体を一律に CC0 と扱わない。
