---
kind: catalog
id: huggingface-yuiseki
description: yuiseki の Hugging Face 公開データのうち、地理分析に使える固定版を探すための目録。
url: https://huggingface.co/yuiseki/datasets
access: 公開リポジトリは匿名で閲覧・ダウンロードできる。個別カードの read は確認した commit SHA に固定する
license: 一律のライセンスはない。各リポジトリの表示と元データの条件を個別カードで区別する
crs: データセットごとに異なる
spatial_coverage: データセットごとに異なる
temporal_coverage: データセットごとに異なる
as_of:
  checked: 2026-10-26
contents:
- yuiseki が Hugging Face に凍結した GeoParquet と原資料・変換コードへの入口
---

# yuiseki の Hugging Face 地理データ

2026-10-26 に[公開一覧](https://huggingface.co/yuiseki/datasets)と Hugging Face Hub API の `GET /api/datasets?author=yuiseki&limit=1000&full=true` を照合し、公開87件を確認した。全件が地理データとは限らないため、以下は GeoAI での用途と実ファイルの確認ができた固定版71件に絞る。先にカード化したデータは[親索引](../../index.md)にも残す。カードの `read` に記した SHA は移動しない版を指す。後続の更新を調べるときは API の `sha` と `siblings` を再確認する。

| カード | 内容 | 元データとの関係 |
|---|---|---|
| [esa-worldcover-tokyo-2021-100m](esa-worldcover-tokyo-2021-100m.md) | 10 m 分類を 100 m セルに集計 | [ESA WorldCover](../../esa-worldcover.md)の派生 |
| [ghsl-japan-core-2020-30arcsec](ghsl-japan-core-2020-30arcsec.md) | 人口・建物面積の 30 秒角セル | GHSL の変換 |
| [forty-hokkaido-east-2020](forty-hokkaido-east-2020.md) | 東北海道の森林タイプ面 | ForTy の地域切り出し |
| [koppen-geiger-east-asia-1991-2020](koppen-geiger-east-asia-1991-2020.md) | 東アジアの気候区分面 | [全球版](../../koppen-geiger-2023.md)とは版・範囲が違う |
| [kontur-population-2023-11-01-22km](kontur-population-2023-11-01-22km.md) | H3 r4 人口推計 | [HDX 版](../../kontur-population-20231101.md)の変換 |
| [microsoft-building-footprints-kanto-2026-08-13](microsoft-building-footprints-kanto-2026-08-13.md) | 関東周辺の建物輪郭 | [元データ](../../microsoft-building-footprints.md)の2タイル |
| [usgs-comcat-2025-m45](usgs-comcat-2025-m45.md) | 2025 年の M4.5 以上の地震 | [更新型 API](../../usgs-earthquake-catalog.md)の抽出 |
| [forest-typology-validation-2020](forest-typology-validation-2020.md) | 森林タイプ検証標本 | 分類図ではなく評価用標本 |
| [timezone-boundary-builder-2026d](timezone-boundary-builder-2026d.md) | 3 種のタイムゾーン境界 | [元データ](../../timezone-boundary-builder.md)の変換 |
| [ibtracs-v04r01](ibtracs-v04r01.md) | 1980 年以降の熱帯低気圧経路 | [NOAA の元データ](../../ibtracs-v04r01.md)の変換 |
| [ctrees-agb-hokkaido-east-100m](ctrees-agb-hokkaido-east-100m.md) | 東北海道の2010年・2025年のAGB集計 | [CTrees 全球版](../../ctrees-agb-100m.md)の切り出し・集計 |
| [gebco-2026-hokkaido-east-15as](gebco-2026-hokkaido-east-15as.md) | 東北海道沖の15秒角標高 | GEBCO 2026 の切り出し。既存の[2025年版](../../gebco-2025.md)とは別 |
| [worldpop-kor-population-2015-2030-1km-r2025a](worldpop-kor-population-2015-2030-1km-r2025a.md) | 韓国の2015〜2030年の年次人口推計 | WorldPop R2025A の変換 |

| [natural-earth](natural-earth.md) | 国、州・省、都市、海岸線、陸海、湖、川、道路などの小縮尺ベクター | Natural Earth v5.1.2 の変換 |
| [worldbank-wdi](worldbank-wdi.md) | 国・年・約1,400指標の世界開発指標 | World Bank WDI。CC BYでない指標は除外 |
| [ourairports](ourairports.md) | 空港、滑走路、無線施設などの全世界表 | OurAirports の 2026-08-31 凍結版 |
| [ucdp-ged](ucdp-ged.md) | 1989年以降の組織的暴力事件 | UCDP GED v26.1 |
| [unhcr-refugee-stats](unhcr-refugee-stats.md) | 出身国・庇護国・年ごとの難民等の統計 | UNHCR の 2026-10-04 取得版 |
| [jp-admin-2026-09](jp-admin-2026-09.md) | 日本の都道府県・市区町村の境界と人口 | e-Stat、国土地理院等の加工 |
| [osm-japan-src-2026-08](osm-japan-src-2026-08.md) | OpenStreetMap 日本全国スナップショット | ODbL 1.0。2026-08-31 planet から抽出 |
| [mlit-toshi-keikaku-jp](mlit-toshi-keikaku-jp.md) | 都市計画決定 GIS の全国 GeoParquet | 国土交通省、PDL 1.0 |
| [ekidata-jp](ekidata-jp.md) | 鉄道事業者、路線、駅、隣接駅 | 駅データ.jp 無料版の取得版 |
| [osm-tokyo23-src-2026-08](osm-tokyo23-src-2026-08.md) | OpenStreetMap 東京23区スナップショット | ODbL 1.0。2026-08-31 planet から抽出 |
| [gsi-evacuation-sites-jp](gsi-evacuation-sites-jp.md) | 指定緊急避難場所と指定避難所 | 国土地理院。PDL 1.0 相当 |
| [estat-census-mesh-2020](estat-census-mesh-2020.md) | 2020年国勢調査 1 km メッシュ12表 | e-Stat。CC BY 4.0 |
| [maddison-project](maddison-project.md) | 国ごとの長期 GDP・人口推計 | Maddison Project Database 2018/2020/2023 |
| [mlit-underpass](mlit-underpass.md) | 全国の道路アンダーパス箇所 | 国土交通省。PDL 1.0 |
| [npa-traffic-accidents](npa-traffic-accidents.md) | 2019〜2025年の人身事故統計票 | 警察庁。PDL 1.0 |
| [mlit-1km-fromto-2022-01](mlit-1km-fromto-2022-01.md) | 1 kmメッシュ・市区町村別の月次滞在人口 | 国土交通省 全国の人流オープンデータ |
| [ksj-n07-bus-route](ksj-n07-bus-route.md) | 全国のバスルート線 | 国土数値情報 N07、CC BY 4.0 相当 |
| [ksj-p11-bus-stop](ksj-p11-bus-stop.md) | 全国のバス停と事業者・系統 | 国土数値情報 P11、CC BY 4.0 相当 |
| [ksj-l01-land-price](ksj-l01-land-price.md) | 2019〜2026年の地価公示標準地 | 国土数値情報 L01、年ごとの許諾確認が必要 |
| [geonames](geonames.md) | CC BY 4.0 の世界地名辞書、別名、行政階層 | GeoNames 2026-10-01 の固定スナップショット |

| [wikidata-gazetteer](wikidata-gazetteer.md) | Wikidata の12百万地理項目と多言語名称 (CC0) | Wikidata 2026-08-31 ダンプ |
| [wikipedia-geotagged](wikipedia-geotagged.md) | 座標タグ付き英語・日本語 Wikipedia 記事 (CC BY-SA 4.0) | Wikipedia 2026-09-01 ダンプ |
| [wikivoyage-geotagged](wikivoyage-geotagged.md) | 座標タグ付き英語 Wikivoyage 記事 (CC BY-SA 4.0) | Wikivoyage 2026-09-01 ダンプ |
| [opencellid](opencellid.md) | 世界の携帯電話セル推定位置 (CC BY-SA 4.0) | OpenCelliD 2026-10-06 スナップショット |
| [abr-src-2026-09](abr-src-2026-09.md) | 日本の住所ベースレジストリの町字名と代表点 (CC BY 4.0) | デジタル庁アドレス・ベース・レジストリ |
| [estat-boundary-2020](estat-boundary-2020.md) | 2020年国勢調査の小地域境界と人口・世帯 (CC BY 4.0) | e-Stat 令和2年国勢調査 |
| [estat-census-mesh-250m-2020](estat-census-mesh-250m-2020.md) | 2020年国勢調査の250mメッシュ12表 (CC BY 4.0) | e-Stat 令和2年国勢調査 |
| [estat-census-mesh-500m-2020](estat-census-mesh-500m-2020.md) | 2020年国勢調査の500mメッシュ12表 (CC BY 4.0) | e-Stat 令和2年国勢調査 |
| [gsi-global-map-jp](gsi-global-map-jp.md) | 地球地図日本の行政界・道路・河川など複数版 | 国土地理院 地球地図日本 |
| [nfgis-2024](nfgis-2024.md) | 林野庁 国有林GIS 2024、複数の平面直角座標系 | 林野庁の2024年度版データ |

| [meta-move-dist](meta-move-dist.md) | Meta の地域別移動距離分布、2026年日次集計 (CC BY 4.0) | Data for Good at Meta / HDX |
| [meta-range-maps-2022-05](meta-range-maps-2022-05.md) | Meta のCOVID-19期の地域別移動指標、2020〜2022年 (CC BY 4.0) | Data for Good at Meta / HDX |
| [geo-triples-japan](geo-triples-japan.md) | 日本の空間関係 triple と言語評価データ (ODbL 1.0) | OSM / Natural Earth 由来の GeoAI benchmark |
| [geo-triples-jp-gov](geo-triples-jp-gov.md) | 日本の自治体公開資料に基づく空間関係 benchmark (CC BY 4.0) | 自治体等の公開資料 |
| [osm-wikidata-brand-jp](osm-wikidata-brand-jp.md) | OSMとWikidataの日本ブランド対応表 (ODbL 1.0 / CC0) | OpenStreetMap と Wikidata |
| [osm-tag-corpus](osm-tag-corpus.md) | OpenStreetMapタグの多言語説明コーパス (ODbL 1.0) | OpenStreetMap タグ資料 |
| [osm-tokyo23-questions](osm-tokyo23-questions.md) | 東京23区のOSM空間質問215件 (ODbL 1.0) | OpenStreetMap 2026-08 スナップショット |
| [osm-tokyo23-qa-2026-08](osm-tokyo23-qa-2026-08.md) | 東京23区のOSM質問応答比較 (ODbL 1.0) | OpenStreetMap 2026-08 スナップショット |
| [un-wpp](un-wpp.md) | 国連WPP2024の1950〜2100年人口推計と人口学的表 (CC BY 3.0 IGO) | UN DESA Population Division WPP2024 |

| [text2geoql](text2geoql.md) | 自然言語からOverpass QLを生成するGeoAI学習ペア (ODbL 1.0) | OpenStreetMap由来の合成クエリ |
| [env-redlist-jp](env-redlist-jp.md) | 日本の絶滅危惧種リスト第5次、公開分類群 (CC BY 4.0) | 環境省 いきものログ |

Hugging Face のカードに表示されたライセンスだけで、元データの再配布条件を確定したとは扱わない。特に `license: other` のカードは元の許諾文を読んでから二次配布する。行数は Parquet のメタデータを読んだ値で、全行の値・形状・一意性を検証したという意味ではない。元の ForTy と GHSL のカードは[親索引](../../index.md)から辿る。

| [gsi-dem-fuji-z14-100m-2026-10-25](gsi-dem-fuji-z14-100m-2026-10-25.md) | 国土地理院 DEM10B から作成した富士山周辺の100 m標高セル。 | PDL 1.0 相当。国土地理院を出典表示し、派生データであることを明記する |

| [gpw-grasslands-hokkaido-east-2018-2020-250m](gpw-grasslands-hokkaido-east-2018-2020-250m.md) | Global Pasture Watch 草地分類の東北海道 2018〜2020年版。 | CC BY 4.0。Parente et al. と Zenodo の元データを出典表示 |

| [worldpop-idn-population-2015-2030-1km-r2025a](worldpop-idn-population-2015-2030-1km-r2025a.md) | WorldPop R2025A のインドネシア年次人口推計 1 km 格子。 | ODbL 1.0 の派生データ。WorldPop 元データの条件も併記し、派生データベースの Share-Alike と帰属表示を守る |

| [agera5-japan-monthly-temperature-1979-2026](agera5-japan-monthly-temperature-1979-2026.md) | AgERA5 日本周辺の月平均最高・最低気温の格子。 | CC BY 4.0。Copernicus Climate Change Service / ECMWF と FAO GIS catalogue を出典表示 |

| [pwt](pwt.md) | Penn World Table 11.0 の国・年別マクロ経済指標。 | CC BY 4.0。Feenstra, Inklaar, Timmer (2015) と PWT 11.0 の DOI を引用 |

| [undp-hdr](undp-hdr.md) | UNDP Human Development Report 2025 の複合指標と時系列。 | CC BY 3.0 IGO。UNDP HDR 2025 を出典表示し IGO の条件に従う |

| [gsj-reports](gsj-reports.md) | 産業技術総合研究所 地質調査総合センターの公開報告ページ抽出テキスト。 | CC BY 4.0。第三者資料の引用表示を本文から保持 |

| [nilim-disaster-reports](nilim-disaster-reports.md) | 国土技術政策総合研究所の災害調査報告から権利確認できた本文。 | CC BY 4.0。本文中の第三者図表・引用の表示も維持 |

| [moni1000-reports](moni1000-reports.md) | 環境省モニタリングサイト1000の公開調査報告テキスト。 | 政府標準利用規約（第1.0版）。出典表示と第三者権利の条件を守る |

| [mlit-river-basin-overviews](mlit-river-basin-overviews.md) | 国土交通省の一級水系・河川流域概要の公開本文。 | 政府標準利用規約（第1.0版）。引用される第三者資料の権利は別途尊重 |

| [estat-jumin-idou](estat-jumin-idou.md) | e-Stat 住民基本台帳人口移動報告の統計表スナップショット。 | 政府標準利用規約（第1.0版）に適合。e-Stat API取得時に必要な出典表示を維持 |

| [edgar-ghg-countries](edgar-ghg-countries.md) | EDGAR 2026 の国別・部門別温室効果ガス排出量ファイル。 | CC BY 4.0 対象ガスのみ。化石起源 CO2（NC-ND）は含めず、出典と対象範囲を明記 |

| [faostat](faostat.md) | FAOSTAT の農業・食料・土地利用・気候等の統計スナップショット。 | CC BY 4.0。FAO を出典表示し、個別ドメインの注記も保持 |

| [ilostat](ilostat.md) | ILOSTAT の労働市場・雇用統計の指標ファイルと辞書。 | CC BY 4.0。ILOSTAT を出典表示し、指標定義・分類辞書を併用 |

| [geo-triples-tokyo23](geo-triples-tokyo23.md) | 東京23区・地理関係 triple、英日テキスト、評価質問からなる GeoAI ベンチマーク。 | ODbL 1.0。OpenStreetMap contributors を表示し、派生データベースにも Share-Alike を適用 |

| [gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2](gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2.md) | GFW Forest Flux Model v1.3.2 の東北海道 2001〜2023年累積純炭素フラックス。 | CC0 1.0。無帰属でも再利用可能だが、Gibbs et al. と Dataverse DOI の引用を推奨 |

| [egov-laws-jp](egov-laws-jp.md) | e-Gov 法令検索の法令改正履歴と XML・テキストを収録する日本語コーパス。 | CC BY 4.0。法律本文は著作権法第13条により著作物でなく、デジタル庁の付加情報は PDL 1.0 |
