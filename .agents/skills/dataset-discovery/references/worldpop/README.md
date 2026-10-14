---
kind: catalog
id: worldpop
description: WorldPop の人口の格子。総人口 (100 m、1 km)、年齢と性別、都市化度。英国サウサンプトン大学が出す。
url: https://stac.worldpop.org/
access: STAC Browser が https://stac.worldpop.org/ で、実体の STAC API は https://api.stac.worldpop.org/。1 か国が 1 コレクション (id は ISO の 3 文字)。ファイルは data.worldpop.org にあり、Range 要求を無視して全体を返す
license: CC-BY-4.0 (コレクションで確かめた)
crs: EPSG:4326
spatial_coverage: 全世界、国ごと (2026-10-10 に 248 コレクション)
temporal_coverage: 2015 から 2030 年。2025 年より後は推計
as_of:
  checked: 2026-10-10
contents:
- 100 m と 1 km の総人口
- 年齢と性別の内訳
- 都市化度
children:
- population.md
- japan.md
---

# WorldPop

全世界の人口の格子。総人口 (100 m と 1 km)、年齢・性別の内訳、都市化度。2015〜2030 年 (2025 年より後は推計)。英国サウサンプトン大学の WorldPop が出す。

| ファイル | プロダクト |
|---|---|
| [population.md](population.md) | 総人口 (100 m、1 km) |
| [japan.md](japan.md) | 日本だけの凍結版。総人口、年齢・性別 (1 km)、都市化度。COG で範囲を読める |

年齢・性別 (Age and Sex Structures) と都市化度 (Degree of Urbanisation) は、日本の分だけ `japan.md` にある。全世界の分はまだ書いていない (TODO.md)。

## 目録の引き方

`https://stac.worldpop.org/` は STAC Browser (画面) で、実体は STAC API `https://api.stac.worldpop.org/`。

- 1 か国が 1 コレクション。コレクションの id は ISO 3 文字 (`JPN`)。2026-10-10 に 248 コレクション。
- コレクションのライセンスは CC-BY-4.0 (`JPN` で確かめた)。
- item の `project` がプロダクト: `Population`、`Age and Sex Structures`、`Degree of Urbanisation`。日本は 80 item で、総人口 32 (16 年 × 100 m と 1 km)、年齢・性別 32、都市化度 16 (2026-10-10)。
- item には `year`、画素の大きさ (`data:pixel_size`)、欠損値 (`data:nodata_value`)、型、座標系、ファイルの大きさ、版 (`Release`、`Version`) がある。
- item の説明 (`description`) は、解像度を取り違えていることがある。日本の 2020 年の 1 km の item の説明は「3 arc (約 100 m)」と書いている (2026-10-14)。解像度は `data:pixel_size` とファイルで確かめる。

```
https://api.stac.worldpop.org/collections/JPN/items?limit=100
```

## 年は `year` で絞る

`datetime` はプロダクトによって意味が違う。総人口と年齢・性別の item は、どの年のものでも `datetime` が 2025-01-01 (公開の年)。都市化度の item は、その年の 1 月 1 日。年で絞るときは `year` を使う (2026-10-10 実測)。

以前の調査の目録 (2026-09-28) には「`datetime` は全件 2025-01-01」、日本は 65 item とあった。2026-10-10 には都市化度が年ごとに 16 item になっていて、その 16 件だけ `datetime` が年と一致する。

## 配布元は Range 要求を無視する

ファイルは `data.worldpop.org` にある。応答に `Accept-Ranges: bytes` を付けるのに、Range 要求 (`curl -r 0-1023`) に 200 でファイル全体を返す (日本の 1 km の 2020 年版、2,195,362 バイトで 2026-10-10 に確かめた)。GDAL の `/vsicurl/` や DuckDB で必要な範囲だけを読むことはできない。丸ごと落としてから読む。

- 1 km 版は 1 か国 2 MB 程度で、丸ごと落として困らない。
- 100 m 版は日本で 1 年約 103 MB。2026-09-28 の HTTPS は 1 本約 50 kB/s と遅かった (以前の調査の記録)。
- 日本の分は、Hugging Face の `yuiseki/worldpop-jp-2026-01` に、元の GeoTIFF と、値を変えずに作った COG (Range で読める) を凍結してある。日本だけを使うならこちらを読む。

## rasterio で読むときの落とし穴

このマシンのシェルは anaconda の `GDAL_DRIVER_PATH`、`GDAL_DATA`、`PROJ_DATA` を export している。rasterio に同梱の GDAL がこれを拾うと、欠損値 (-99999) が None になって人口として足される。読む前に外す。

```sh
env -u GDAL_DRIVER_PATH -u GDAL_DATA -u PROJ_DATA -u PROJ_LIB uvx --with rasterio python -I read.py
```
