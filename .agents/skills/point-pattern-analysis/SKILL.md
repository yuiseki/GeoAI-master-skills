---
name: point-pattern-analysis
description: 点 (事件、施設) が、比べる基準の分布 (どこにでも、人の住む所に、など) で無作為に置いた場合と比べて、どの距離で集まっているか、散らばっているかを調べる。点そのものの位置の構造を問うときに使う。
---

# point-pattern-analysis

点が集まっているかどうかは、何と比べるかで決まる。一様な配置と比べると、ほとんどの点は「集まっている」。人は一様に住んでいないので、人に関わる点は人の住む所に集まるのが当たり前だからだ。比べる基準の分布を先に決め、それを書く。

| reference | 中身 |
|---|---|
| [ripley](references/ripley.md) | 距離ごとの点の組の数 (Ripley の K) と、無作為な配置との比べ方 |
| [baselines](references/baselines.md) | 比べる基準の分布の選び方 |

## 手順

1. 問いを書く。「ヘリポートは、人の住む所に沿う以上に集まっているか」。
2. 比べる基準を決める (references/baselines.md)。少なくとも 2 つ (一様と、問いに合った分布) で比べる。
3. 点の位置の精度を確かめる (analysis-unit-design)。精度が粗い点 (行政区の代表点) は、その大きさより短い距離で偽の集まりを作る。
4. `scripts/point_pattern.py` で、距離ごとに観測した点の組の数を、基準から無作為に置いた点の組の数と比べる。
5. 基準の外にある点 (基準の分布で置けない場所の点) の数を書く。
6. 集まっている距離と、その倍率を書く。どこが集まりを作っているかを、点の中身 (名前、種類、地域) で確かめる。

```sh
env -u GDAL_DRIVER_PATH -u GDAL_DATA -u PROJ_DATA -u PROJ_LIB \
  uvx --with numpy --with scipy --with rasterio --with duckdb python scripts/point_pattern.py \
  hf://datasets/yuiseki/ourairports-2026-08/parquet/airports.parquet tmp/jpn_pop_2020_1km.tif \
  --where "iso_country = 'JP' and type = 'heliport'" --baseline values --radii 1 2 5 10 25 50
```

基準のラスタは EPSG:4326 の GeoTIFF。WorldPop の人口 (dataset-discovery の references/worldpop/) がそのまま使える。anaconda の GDAL の環境変数を外す理由も、そこに書いてある。

テストは `env -u GDAL_DRIVER_PATH -u GDAL_DATA -u PROJ_DATA -u PROJ_LIB uvx --with numpy --with scipy --with rasterio --with duckdb --with pytest pytest scripts/test_point_pattern.py`。距離が大円距離であること、基準から置いた点は集まって見えないこと、人口に沿って置いた点は一様な基準と比べると集まって見え、人口の基準と比べると見えないこと、面積の基準が緯度による面積の違いを入れていること、基準の外の点を数えることを確かめている。面積の重みから緯度を外す、自分自身との組を数える、基準の重みを無視する、のそれぞれで落ちることを確かめてある。

## 書き出すもの

- 問いと、比べた基準 (少なくとも 2 つ)
- 点の数、基準の外の点の数、位置の精度の扱い
- 距離ごとの観測、無作為な配置の中央値と 95% の範囲、倍率
- 集まりを作っている場所と点の中身
