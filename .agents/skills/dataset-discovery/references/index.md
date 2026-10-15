# データセットの索引

このディレクトリの reference の一覧。データセットを 1 つ足したら、ここにも 1 行足す。各 reference の先頭の frontmatter に、1 行が何を表すか、ID と結合キー、範囲と時点がある。

## データセットと目録

| reference | 中身 | 範囲 | 時点 |
|---|---|---|---|
| [natural-earth](natural-earth.md) | 国、州・省、都市、海岸線、陸海、湖、川、道路など | 全世界、1:10m〜1:110m | 2022-05 で止まっている |
| [worldbank-wdi](worldbank-wdi.md) | 国 × 年の開発指標 約 1,400 | 国、座標なし | 1960〜2025、版ごと |
| [ourairports](ourairports.md) | 空港、ヘリポート、飛行場の点と IATA / ICAO コード | 全世界の点 | 2026-08-31 で凍結 |
| [ucdp-ged](ucdp-ged.md) | 組織的暴力の事件の点と死者数 | 全世界の点 (精度はまちまち) | 1989〜2025、版ごと |
| [unhcr-refugee-stats](unhcr-refugee-stats.md) | 出身国 × 庇護国 × 年の難民などの人数 | 国の組、座標なし | 1951〜2025、版ごと |
| [overture/](overture/README.md) | 目録。行政区域、道路と交差点、POI、建物など | 全世界 | 月ごとの版 |
| [worldpop/](worldpop/README.md) | 目録。人口の格子 (100 m、1 km)、年齢・性別、都市化度 | 全世界、国ごと | 2015〜2030 |
| [planetary-computer/](planetary-computer/README.md) | 目録。衛星画像、標高、土地被覆のラスタ (COG、匿名の SAS 署名が要る) | 全世界 | コレクションごと |
| [mlit-nlftp/](mlit-nlftp/README.md) | 目録。国土数値情報 (鉄道、医療機関、浸水想定、将来推計人口など) | 日本 | 年ごと |
| [tokyo-ckan/](tokyo-ckan/README.md) | 目録。東京都と区市町村のオープンデータ (施設一覧、統計表) | 東京都 | データセットごと |
| [fao-ferspas/](fao-ferspas/README.md) | 目録。FAO の農業・食料・気候のラスタ (COG) | 全世界 | コレクションごと |
| [jp-admin-2026-09](jp-admin-2026-09.md) | 都道府県と市区町村の面、コード、名前、2020 年の人口と世帯数 (CC BY 4.0) | 日本 | 名前 2026-09、面と人口 2020 |
| [osm-japan-src-2026-08](osm-japan-src-2026-08.md) | OpenStreetMap の日本全国 (点、線、面、道路)。GeoParquet、EPSG:3857 | 日本 | 2026-08-31 で凍結 |
| [mlit-toshi-keikaku-jp](mlit-toshi-keikaku-jp.md) | 都市計画決定GISデータ。用途地域 (容積率、建蔽率)、都市計画道路、公園、地区計画など 25 レイヤー | 日本 (自治体が提供した分) | 令和 7 年度版 |
| [ekidata-jp](ekidata-jp.md) | 鉄道の事業者、路線、駅の点、隣り合う駅 (無料版。新幹線の駅なし) | 日本 | 2026-10-05 取得、版ごと |
| [osm-tokyo23-src-2026-08](osm-tokyo23-src-2026-08.md) | OpenStreetMap の東京 23 区 (点、線、面、道路)。全国版と同じ列で約 30 分の 1 の大きさ。EPSG:3857 | 東京 23 区 | 2026-08-31 で凍結 |
| [gsi-evacuation-sites-jp](gsi-evacuation-sites-jp.md) | 指定緊急避難場所 (災害の種類ごとの指定) と指定避難所の点 | 日本 | 2026-10-06 取得 |
| [estat-census-mesh-2020](estat-census-mesh-2020.md) | 令和 2 年国勢調査の 1 km メッシュの統計 (人口、世帯、年齢、就業、住宅など 12 表) | 日本 | 2020-10-01 |
| [gsi-dem-tiles](gsi-dem-tiles.md) | 国土地理院の標高タイル (ズームとタイル番号で 256 × 256 画素の標高をテキストで返す) | 日本の陸域 | 随時更新、2026-10-14 取得 |
| [nsw-lalonde](nsw-lalonde.md) | 職業訓練の無作為化実験 NSW と観察の対照 (PSID、CPS)。実験の答えが分かっていて、因果の推定量の検算に使う。地理の列は無い | アメリカの人、座標なし | 1974、1975、1978 年の所得 |
| [maddison-project](maddison-project.md) | 国ごとの 1 人あたり実質 GDP と人口の長期の推計 (2018、2020、2023 年版) | 世界の国 | 西暦 1〜2022 年 |
| [worldpop/japan.md](worldpop/japan.md) | 日本の人口の格子の凍結版。100 m と 1 km の総人口、年齢・性別、都市化度 (COG) | 日本 | 2015〜2030、R2025A |

## サービス

データを持たずに、問いを投げて答えを得る自前のサービス。呼び方、制限、つまずきやすい点が [services/](services/README.md) にある。

| reference | できること | 時点 |
|---|---|---|
| [overpass](services/overpass.md) | OSM の地物をタグと範囲で検索、集計する | 2025-09-14 で止まっている |
| [nominatim](services/nominatim.md) | 地名から座標と OSM の ID を引く | 2025-09-14 で止まっている |
| [valhalla](services/valhalla.md) | 経路の距離と所要時間 | 確かめていない |
| [taginfo](services/taginfo.md) | OSM のタグの辞書と使用数 | 2026-01-29 まで |

Natural Earth の国の面が、ほかのデータセットを結ぶ軸になる。どのキーで結べるかは各 reference の「Natural Earth との結合」にある。
