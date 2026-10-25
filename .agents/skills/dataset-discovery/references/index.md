# データセットの索引

このディレクトリの reference の一覧。データセットを 1 つ足したら、ここにも 1 行足す。各 reference の先頭の frontmatter に、1 行が何を表すか、ID と結合キー、範囲と時点がある。

## データセットと目録

| reference | 中身 | 範囲 | 時点 |
|---|---|---|---|
| [natural-earth](huggingface/yuiseki/natural-earth.md) | 国、州・省、都市、海岸線、陸海、湖、川、道路など | 全世界、1:10m〜1:110m | 2022-05 で止まっている |
| [worldbank-wdi](huggingface/yuiseki/worldbank-wdi.md) | 国 × 年の開発指標 約 1,400 | 国、座標なし | 1960〜2025、版ごと |
| [ourairports](huggingface/yuiseki/ourairports.md) | 空港、ヘリポート、飛行場の点と IATA / ICAO コード | 全世界の点 | 2026-08-31 で凍結 |
| [ucdp-ged](huggingface/yuiseki/ucdp-ged.md) | 組織的暴力の事件の点と死者数 | 全世界の点 (精度はまちまち) | 1989〜2025、版ごと |
| [unhcr-refugee-stats](huggingface/yuiseki/unhcr-refugee-stats.md) | 出身国 × 庇護国 × 年の難民などの人数 | 国の組、座標なし | 1951〜2025、版ごと |
| [overture/](overture/README.md) | 目録。行政区域、道路と交差点、POI、建物など | 全世界 | 月ごとの版 |
| [worldpop/](worldpop/README.md) | 目録。人口の格子 (100 m、1 km)、年齢・性別、都市化度 | 全世界、国ごと | 2015〜2030 |
| [ghsl/](ghsl/README.md) | 目録。JRC の居住人口と建物面積の推計格子。30 秒角の日本周辺タイルを実読 | 全世界をタイルに分割 | R2023A、1975〜2030。2025・2030 は投影 |
| [microsoft-building-footprints](microsoft-building-footprints.md) | 画像から推定した建物輪郭。日本の1タイルを実読 | 全世界の収録地域。日本の索引203タイル | 索引は2026-08-13。画像の撮影年は場所による |
| [planetary-computer/](planetary-computer/README.md) | 目録。衛星画像、標高、土地被覆のラスタ (COG、匿名の SAS 署名が要る) | 全世界 | コレクションごと |
| [global-nature-watch/](global-nature-watch/README.md) | 目録。草地、植生攪乱、森林損失要因、森林タイプ。API と許諾はレイヤーごと | 全球を中心にレイヤーごと | 年次図、速報、2020 年基準図 |
| [huggingface/yuiseki/](huggingface/yuiseki/README.md) | 目録。yuiseki の公開一覧のうち地理分析向けに確認した固定版48件。元データのカードとは区別 | 東京周辺、日本、東アジア、韓国、全球など | 個別のデータ時点と commit SHA に固定 |
| [mlit-nlftp/](mlit-nlftp/README.md) | 目録。国土数値情報 (鉄道、医療機関、浸水想定、将来推計人口など) | 日本 | 年ごと |
| [tokyo-ckan/](tokyo-ckan/README.md) | 目録。東京都と区市町村のオープンデータ (施設一覧、統計表) | 東京都 | データセットごと |
| [fao-ferspas/](fao-ferspas/README.md) | 目録。FAO の農業・食料・気候のラスタ (COG) | 全世界 | コレクションごと |
| [jp-admin-2026-09](huggingface/yuiseki/jp-admin-2026-09.md) | 都道府県と市区町村の面、コード、名前、2020 年の人口と世帯数 (CC BY 4.0) | 日本 | 名前 2026-09、面と人口 2020 |
| [osm-japan-src-2026-08](huggingface/yuiseki/osm-japan-src-2026-08.md) | OpenStreetMap の日本全国 (点、線、面、道路)。GeoParquet、EPSG:3857 | 日本 | 2026-08-31 で凍結 |
| [mlit-toshi-keikaku-jp](huggingface/yuiseki/mlit-toshi-keikaku-jp.md) | 都市計画決定GISデータ。用途地域 (容積率、建蔽率)、都市計画道路、公園、地区計画など 25 レイヤー | 日本 (自治体が提供した分) | 令和 7 年度版 |
| [ekidata-jp](huggingface/yuiseki/ekidata-jp.md) | 鉄道の事業者、路線、駅の点、隣り合う駅 (無料版。新幹線の駅なし) | 日本 | 2026-10-05 取得、版ごと |
| [osm-tokyo23-src-2026-08](huggingface/yuiseki/osm-tokyo23-src-2026-08.md) | OpenStreetMap の東京 23 区 (点、線、面、道路)。全国版と同じ列で約 30 分の 1 の大きさ。EPSG:3857 | 東京 23 区 | 2026-08-31 で凍結 |
| [gsi-evacuation-sites-jp](huggingface/yuiseki/gsi-evacuation-sites-jp.md) | 指定緊急避難場所 (災害の種類ごとの指定) と指定避難所の点 | 日本 | 2026-10-06 取得 |
| [estat-census-mesh-2020](huggingface/yuiseki/estat-census-mesh-2020.md) | 令和 2 年国勢調査の 1 km メッシュの統計 (人口、世帯、年齢、就業、住宅など 12 表) | 日本 | 2020-10-01 |
| [gsi-dem-tiles](gsi-dem-tiles.md) | 国土地理院の標高タイル (ズームとタイル番号で 256 × 256 画素の標高をテキストで返す) | 日本の陸域 | 随時更新、2026-10-14 取得 |
| [nsw-lalonde](nsw-lalonde.md) | GeoAI の分析対象ではなく、GeoAI でも使う統計手法を検証するための benchmark。職業訓練の無作為化実験 NSW と観察の対照 (PSID、CPS)。実験の答えが分かっている。地理の列は無い | アメリカの人、座標なし | 1974、1975、1978 年の所得 |
| [card-college-proximity](card-college-proximity.md) | GeoAI の分析対象ではなく、操作変数を検証するための benchmark。Card (1995) の教育、賃金、1966 年の大学への近さ。教科書の答え (0.132) が分かっている | アメリカの人、地域の印だけ | 1966 年と 1976 年 |
| [statsmodels-co2](statsmodels-co2.md) | GeoAI の分析対象ではなく、季節のある時系列の予測を検証するための benchmark。マウナロアの CO2 の週の値。強い季節と上昇の傾向。statsmodels に同梱 | 1 地点 | 1958-03〜2001-12、週 |
| [maddison-project](huggingface/yuiseki/maddison-project.md) | 国ごとの 1 人あたり実質 GDP と人口の長期の推計 (2018、2020、2023 年版) | 世界の国 | 西暦 1〜2022 年 |
| [worldpop/japan.md](worldpop/japan.md) | 日本の人口の格子の凍結版。100 m と 1 km の総人口、年齢・性別、都市化度 (COG) | 日本 | 2015〜2030、R2025A |
| [mapterhorn](mapterhorn.md) | 全世界の標高のラスタタイル (Terrarium の可逆 WebP、PMTiles)。z0〜12 は 1 ファイル、z13 以上は地域ごと。151 の配布元の DEM を合わせたもの | 全世界の陸域 (海は 0) | 版 0.0.13、2026-10-16 取得 |
| [dynamic-world](dynamic-world.md) | Sentinel-2 のシーンごとの 10 m の土地被覆 (9 クラスの確率とラベル)。Earth Engine の中だけ。未実測 | 全世界の陸域 | 2015-06-27 から、ほぼ実時間 |
| [esa-worldcover](esa-worldcover.md) | 全世界の陸域の 10 m の土地被覆の分類図 (11 クラス)。3 度のタイルの COG、EPSG:4326。AWS の公開 S3 から認証なしで読める | 全世界の陸域 (外洋は NoData) | 2020 (v100)、2021 (v200) |
| [ctrees-agb-100m](ctrees-agb-100m.md) | 地上部バイオマス密度と不確実性の 100 m 年次 COG。CC BY 4.0、全球全期間は約 1.90 TB | 全球の植生域 | 2000〜2025 年 |
| [esa-cci-biomass-v7](esa-cci-biomass-v7.md) | 森林の木本地上部バイオマスと不確実性の 100 m 地図。利用無料、再配布は未確認 | 全球 | 2005〜2012、2015〜2024 年 |
| [nasa-gedi-l4a-v3](nasa-gedi-l4a-v3.md) | LiDAR の約 25 m フットプリントでの AGB 密度予測と誤差。現地実測ではない | 南北 51.6 度の軌道上 | 2019〜2025 年の観測 |
| [nasa-gedi-l4b-v2-1](nasa-gedi-l4b-v2-1.md) | GEDI 観測を 1 km 格子にまとめた AGB 密度と標準誤差。約 2.2 GB | 南北約 52 度の有効セル | 2019〜2023 年の観測を統合 |
| [jaxa-japan-biomass](jaxa-japan-biomass.md) | 約 10 m の日本の森林 AGB・炭素蓄積・樹高。登録が必要、再配布は未確認 | 日本の森林 | 2016〜2022 年の入力から作った単時期 |
| [gfw-forest-carbon-net-flux](gfw-forest-carbon-net-flux.md) | 森林の温室効果ガス純フラックス。年別ではなく期間累積。CC BY 4.0 | 全球の森林 | 2001〜2025 年の累積 (v20260327) |
| [gfw-biomass-stock-2000](gfw-biomass-stock-2000.md) | 旧 WHRC 由来の木本 AGB 密度。無料で閲覧できるが個別ライセンスは未確認 | 全球とされる | 2000 年 |
| [usfs-biomass-2008](usfs-biomass-2008.md) | USDA Forest Service の 250 m 森林バイオマス。CONUS の AGB ZIP は約 142 MB | 米国本土、アラスカなど | 2008 年版 |
| [usfs-bigmap-2018](usfs-bigmap-2018.md) | USDA Forest Service FIA BIGMAP の30m森林バイオマス。総量と327樹種 | 米国本土 | 2018年版 |
| [canada-scanfi-v2](canada-scanfi-v2.md) | カナダ 30 m 森林 AGB など。Open Government Licence、2020 年 AGB は約 6.67 GB | カナダ | 1985〜2025 年の 5 年刻み |
| [ksj-l01-land-price](huggingface/yuiseki/ksj-l01-land-price.md) | 地価公示の標準地の点と公示価格 (円/m²)、対前年変動率、地積、用途地域など。年をまたぐには前年の番号で結ぶ | 日本の標準地 (約 2.6 万点) | 2019〜2026 年の各年 1 月 1 日、2026-10-16 取得 |
| [mlit-underpass](huggingface/yuiseki/mlit-underpass.md) | 国土交通省の全国のアンダーパス箇所マップの点 (名前、路線、管理者)。国と地方公共団体の道路だけ | 日本 (3,841 点) | 地図は 2025-03-31、2026-10-17 取得 |
| [npa-traffic-accidents](huggingface/yuiseki/npa-traffic-accidents.md) | 警察庁の人身事故の個票 (本票は事故 1 件 1 行、補充票、高速票)。座標、市区町村、当事者 A と B、死傷 | 日本 (年に約 29〜38 万件) | 2019〜2025 年 |
| [mlit-1km-fromto-2022-01](huggingface/yuiseki/mlit-1km-fromto-2022-01.md) | 1 km メッシュと市区町村ごとの月ごとの滞在人口 (平日と休日、昼と深夜、居住地別) | 日本 | 2019-01〜2021-12 |
| [ksj-n07-bus-route](huggingface/yuiseki/ksj-n07-bus-route.md) | 国土数値情報のバスルートの線と事業者 (系統、本数は無い)。首都圏 4 都県の版もある | 日本 (354,208 本) | 2022-08 ごろの資料、2026-10-23 取得 |
| [ksj-p11-bus-stop](huggingface/yuiseki/ksj-p11-bus-stop.md) | 国土数値情報のバス停の点、事業者、通る系統とバスの区分 (本数は無い)。首都圏 4 都県の版もある | 日本 (278,515 か所) | 2022-08 ごろの資料、2026-10-23 取得 |
| [gebco-2025](gebco-2025.md) | 全球15秒角の海底地形・陸域標高とデータ由来の TID Grid。画素未実読 | 全球 | 2025年版。元測量時点は場所による |
| [jaxa-aw3d30](jaxa-aw3d30.md) | JAXA の約30m DSM。登録が必要。画素未実読 | 全球の陸域 | 主な元画像2006〜2011年、地域ごとに版が異なる |
| [koppen-geiger-2023](koppen-geiger-2023.md) | Köppen-Geiger 気候区分。Figshare v2 固定。ZIP は未実読 | 全球の陸域 | 基準期間・将来シナリオ別 |
| [kontur-population-20231101](kontur-population-20231101.md) | H3 の人口推計。22km版の71,283セルを実読 | 全球 | 2023-11-01版 |
| [plateau/](plateau/README.md) | 目録。都市・年度別の CityGML 3D都市モデル | 日本の公開都市 | 都市・元資料ごと |
| [virtual-shizuoka/](virtual-shizuoka/README.md) | 目録。静岡県の航空レーザー等の公開点群。2025年の1タイルを実読 | 静岡県の公開済み範囲 | 2019〜2025年の年別ディレクトリ |
| [timezone-boundary-builder-2026d](timezone-boundary-builder.md) | IANA タイムゾーンの境界。now版 GeoJSON を実読 | 全球 | 2026d版 |
| [mobility-database/](mobility-database/README.md) | 目録。GTFS と GTFS-RT の供給元、公開 URL、認証、ライセンス URL。CSV 6,686行を実読 | 世界の登録フィード | 2026-10-25 取得 |
| [ibtracs-v04r01](ibtracs-v04r01.md) | NOAA の熱帯低気圧の経路。last3years CSV 24,554観測行を実読 | 全球の熱帯低気圧 | v04r01、継続更新 |
| [hydrosheds/](hydrosheds/README.md) | 目録。階層流域と河川網。Greenland の v1 流域・河川を実読。原データの再配布制限あり | 全球の対象陸域 | v1 系列 |
| [hydrosheds/hydrobasins-v1](hydrosheds/hydrobasins-v1.md) | Greenland のレベル6・12流域面を実読。下流流域 ID を持つ | Greenland の試料 | v1.c |
| [hydrosheds/hydrorivers-v1](hydrosheds/hydrorivers-v1.md) | Greenland の河川区間を実読。レベル12流域に全行結合 | Greenland の試料 | v1.0 |
| [global-fishing-watch/](global-fishing-watch/README.md) | 目録。非商用の漁業活動推定など。API は token が必要で実データは未取得 | AIS 等の観測できる海域 | 2026-10-21 から latest は v5 |

## サービス

データを持たずに、問いを投げて答えを得る自前または外部のサービス。自前のサービスの呼び方、制限、つまずきやすい点は [services/](services/README.md) にある。

| reference | できること | 時点 |
|---|---|---|
| [overpass](services/overpass.md) | OSM の地物をタグと範囲で検索、集計する | 2025-09-14 で止まっている |
| [nominatim](services/nominatim.md) | 地名から座標と OSM の ID を引く | 2025-09-14 で止まっている |
| [valhalla](services/valhalla.md) | 経路の距離と所要時間 | 確かめていない |
| [taginfo](services/taginfo.md) | OSM のタグの辞書と使用数 | 2026-01-29 まで |
| [usgs-earthquake-catalog](usgs-earthquake-catalog.md) | USGS FDSN Event API で地震イベントを検索する。取得結果は更新される | 2026-10-25 に照会 |
| [nasa-gibs](nasa-gibs.md) | NASA GIBS の表示用衛星画像などを WMTS・WMS で取得する。元製品と許諾はレイヤーごと | 2026-10-25 に目録と1タイルを実読 |
| [nasa-firms](nasa-firms.md) | 衛星の火災・熱異常の検出点。公開 KMZ を実読。CSV API は無料 MAP_KEY が必要 | 2026-10-25 に米国の7日間 KMZ を実読 |

Natural Earth の国の面が、ほかのデータセットを結ぶ軸になる。どのキーで結べるかは各 reference の「Natural Earth との結合」にある。
