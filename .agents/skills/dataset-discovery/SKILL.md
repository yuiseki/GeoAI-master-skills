---
name: dataset-discovery
description: 分析に使えるデータセットを選び、そのレイヤーの列、粒度、時空間範囲、注意点を実測して書き出す。地理空間分析を始めるとき、どのデータで問いに答えられるかを決める前に使う。
---

# dataset-discovery

問いに答えるために使うデータセットとレイヤーを決め、その中身を実測する。
説明文やカードを読んだだけで済ませない。行数、列、ジオメトリ、範囲は自分で読んで数える。

## 手順

1. 問いから、必要な分析の単位 (国、州、都市の点、格子など) と時空間範囲を書き出す。
2. 下の索引から候補のデータセットを選び、その reference を読む。reference には読み方、粒度、主なレイヤー、既知の注意点がある。
3. 使うレイヤーを `scripts/profile_layer.py` で実測する。

   ```sh
   uvx --from 'duckdb>=1.5.5' python scripts/profile_layer.py <parquet のパスか URL>
   ```

   行数、列ごとの型と NULL の数、CRS、ジオメトリ型の内訳、範囲、`ST_IsValid` が偽の件数を出す。
4. 複数のデータセットを結ぶなら、結合キーで実際に結んで一致する件数と一致しない値を数える。結合キーの NULL、重複、`-99` のような欠損の符号も数える。空間結合なら両方の CRS 名を確かめる。
5. 下の「書き出すもの」を残す。reference と実測が食い違ったら、実測を書き、食い違いも書く。

索引に無いデータセットが要る場合は、使う前に reference を 1 つ書き足す。多数のデータセットを束ねた目録 (STAC など) は、1 目録 1 ディレクトリにして、目録の引き方を `README.md` に、データセットやテーマごとの中身を別のファイルに書く。

## 索引

| reference | 中身 | 範囲 | 時点 |
|---|---|---|---|
| [natural-earth](references/natural-earth.md) | 国、州・省、都市、海岸線、陸海、湖、川、道路など | 全世界、1:10m〜1:110m | 2022-05 で止まっている |
| [worldbank-wdi](references/worldbank-wdi.md) | 国 × 年の開発指標 約 1,400 | 国、座標なし | 1960〜2025、版ごと |
| [ourairports](references/ourairports.md) | 空港、ヘリポート、飛行場の点と IATA / ICAO コード | 全世界の点 | 2026-08-31 で凍結 |
| [ucdp-ged](references/ucdp-ged.md) | 組織的暴力の事件の点と死者数 | 全世界の点 (精度はまちまち) | 1989〜2025、版ごと |
| [unhcr-refugee-stats](references/unhcr-refugee-stats.md) | 出身国 × 庇護国 × 年の難民などの人数 | 国の組、座標なし | 1951〜2025、版ごと |
| [overture/](references/overture/README.md) | 目録。行政区域、道路と交差点、POI、建物など | 全世界 | 月ごとの版 |
| [worldpop/](references/worldpop/README.md) | 目録。人口の格子 (100 m、1 km)、年齢・性別、都市化度 | 全世界、国ごと | 2015〜2030 |
| [planetary-computer/](references/planetary-computer/README.md) | 目録。衛星画像、標高、土地被覆のラスタ (COG、匿名の SAS 署名が要る) | 全世界 | コレクションごと |
| [mlit-nlftp/](references/mlit-nlftp/README.md) | 目録。国土数値情報 (鉄道、医療機関、浸水想定、将来推計人口など) | 日本 | 年ごと |
| [tokyo-ckan/](references/tokyo-ckan/README.md) | 目録。東京都と区市町村のオープンデータ (施設一覧、統計表) | 東京都 | データセットごと |
| [fao-ferspas/](references/fao-ferspas/README.md) | 目録。FAO の農業・食料・気候のラスタ (COG) | 全世界 | コレクションごと |
| [jp-admin-2026-09](references/jp-admin-2026-09.md) | 都道府県と市区町村の面、コード、名前、2020 年の人口と世帯数 (CC BY 4.0) | 日本 | 名前 2026-09、面と人口 2020 |
| [osm-japan-src-2026-08](references/osm-japan-src-2026-08.md) | OpenStreetMap の日本全国 (点、線、面、道路)。GeoParquet、EPSG:3857 | 日本 | 2026-08-31 で凍結 |
| [mlit-toshi-keikaku-jp](references/mlit-toshi-keikaku-jp.md) | 都市計画決定GISデータ。用途地域 (容積率、建蔽率)、都市計画道路、公園、地区計画など 25 レイヤー | 日本 (自治体が提供した分) | 令和 7 年度版 |
| [ekidata-jp](references/ekidata-jp.md) | 鉄道の事業者、路線、駅の点、隣り合う駅 (無料版。新幹線の駅なし) | 日本 | 2026-10-05 取得、版ごと |
| [worldpop/japan.md](references/worldpop/japan.md) | 日本の人口の格子の凍結版。100 m と 1 km の総人口、年齢・性別、都市化度 (COG) | 日本 | 2015〜2030、R2025A |

Natural Earth の国の面が、ほかのデータセットを結ぶ軸になる。どのキーで結べるかは各 reference の「Natural Earth との結合」にある。

## 書き出すもの

レイヤーごとに次を書く。

- データセット名、レイヤー名、読んだ URL か パス
- 行数と、分析の単位 (1 行が何を表すか)
- 空間範囲と座標系、時点 (いつの状態か)
- 点なら位置の精度。精度を表す列があれば、値ごとの件数と、値ごとに正しく入る単位 (国、行政区、格子)
- 使う列と、その NULL や欠損の符号の数
- 結合キーと、それが一意かどうか
- 無効ジオメトリの数と、どう扱うか
- ライセンスと表示の要否
