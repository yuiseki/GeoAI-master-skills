# hagibis-tokyo-sar-flood-record

令和元年東日本台風 (台風第 19 号、2019-10-12〜13) の東京都の浸水を、雨の止んだ約 7 時間後 (10-13 05:43 JST) の Sentinel-1 で見て、東京都の浸水実績図 (2019 年の 85 面) と A31a (洪水浸水想定区域、想定最大規模) に突き合わせる例。

- 河道 (多摩川の堤防の間) を陽性の対照にして、この撮影と手順で水が見えるかを先に確かめる (B0)。
- 記録された浸水の区域が、浸水しなかったはずの所 (土地被覆で標準化) より多く暗くなるか、半分以上を拾えるか (B1)。市街地では二回反射で明るくなるか (B2)。
- SAR の暗くなった所が A31a の区域に寄るか (B3)。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 部品とテスト: [scripts/flood.py](scripts/flood.py)、[scripts/test_flood.py](scripts/test_flood.py)
- 大きな生成物は `artifacts/_flood/hagibis-tokyo-sar-flood-record/` に置く (RTC の切り出し、ベクタの切り出し、積んだ配列)

## 再実行

```sh
cd projects/_flood/hagibis-tokyo-sar-flood-record
uvx --with numpy --with scipy --with scikit-image --with pytest pytest -q scripts/test_flood.py
E="env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA"
uvx --with duckdb==1.5.5 --with pyproj python scripts/01_fetch_vectors.py
$E uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_sar.py
$E uvx --with rasterio --with numpy --with scipy --with shapely --with pyproj --with scikit-image python -u scripts/02_grid.py
$E uvx --with numpy --with scipy --with scikit-image --with pyproj python -u scripts/03_blocks.py
```

`env -u` は、作者の環境で anaconda の GDAL の変数が rasterio を壊すのを避けるため。浸水実績と A31a は、HF の公開データセットのローカルの作業木 (scripts/common.py のパス) を読む。OSM は作者の Overpass (overpass.yuiseki.net、2025-09-14 の版) を読み、公開の OSM のサーバーは使わない。

## 出典

- Contains modified Copernicus Sentinel data 2019 (Planetary Computer の sentinel-1-rtc、CC BY 4.0)
- 東京都「水害リスク情報システム 浸水実績図データ」(CC BY 4.0、HF yuiseki/tokyo-flood-record-jp)
- 国土交通省 国土数値情報 洪水浸水想定区域データ A31a (FY2025、HF yuiseki/ksj-a31a-flood-greater-tokyo)、行政区域 N03 (2026-01-01)
- ESA WorldCover 2021 (CC BY 4.0)
- © OpenStreetMap contributors (ODbL 1.0)。多摩川の中心線
- 気象庁 過去の気象データ (時間雨量、HF yuiseki/jma-rain-tokyo)
