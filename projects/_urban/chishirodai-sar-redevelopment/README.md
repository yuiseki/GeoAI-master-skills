# chishirodai-sar-redevelopment

SAR で「このへんで多数の人工物の変化があった」と分かれば、そこだけ新しいオルソ画像を買う (タイルを更新する) 判断ができ、全域を定期的に買い直すより安くつく。その判断に無料の Sentinel-1 が使えるかを、千葉市若葉区千城台東 2 丁目の団地の解体で確かめる例。

- A: 扇形の街区の低層の棟が、地理院の年度別空中写真の 2019 年度と 2024 年度の間に全て消えた。Sentinel-1 の軌道 46 (下り) の 2017〜2026 年の時系列に画素ごとの変化点の検定を当て、解体を拾えるか、その日付が Sentinel-2 から別に決めた日付と合うかを確かめる。
- B: 周り約 6 km 四方のズーム 16 のタイル 120 枚を、2019 年度と 2024 年度の SAR の平均の差で順位付けし、写真の見比べで「多数の人工物の変化」としたタイルを上位で拾えるかを、市街地の割合で決める素朴な順位と比べる。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 正解: [labels/labels.csv](labels/labels.csv) (付け方は [labels/README.md](labels/README.md))、場所の輪郭: [labels/site.geojson](labels/site.geojson)
- 変化点の検定: [scripts/cp.py](scripts/cp.py) (前の例 [kita-inbanuma-sar-changepoint](../../_flood/kita-inbanuma-sar-changepoint/) の写し)。順位と切れ目の部品: [scripts/rank.py](scripts/rank.py)
- 大きな生成物は `artifacts/_urban/chishirodai-sar-redevelopment/` に置く (RTC の切り出し、写真のタイル、Sentinel-2 の切り出し、積んだ時系列)

## 再実行

```sh
cd projects/_urban/chishirodai-sar-redevelopment
uvx --with numpy --with scipy --with pytest pytest -q scripts/test_cp.py scripts/test_rank.py
E="env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA"
uvx --with pillow --with pyproj python scripts/01_fetch_photos.py
python3 scripts/01_fetch_site.py
$E uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_sar.py
$E uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_s2.py
$E uvx --with rasterio --with numpy --with scipy --with shapely --with pyproj --with scikit-image python scripts/02_grid.py
$E uvx --with numpy --with shapely --with pyproj python scripts/03_s2.py
$E uvx --with numpy --with scipy --with pyproj python -u scripts/04_blocks.py
$E uvx --with numpy --with matplotlib --with pyproj python scripts/05_fig.py
```

`env -u` は、作者の環境で anaconda の GDAL の変数が rasterio を壊すのを避けるため。01_fetch_site.py は作者の Overpass (overpass.yuiseki.net、2025-09-14 の版) を読む。公開の OSM のサーバーは使わない。

## 出典

- Contains modified Copernicus Sentinel data 2017-2026 (Planetary Computer の sentinel-1-rtc、sentinel-2-l2a、CC BY 4.0)
- 国土地理院 年度別空中写真 (nendophoto2019、nendophoto2024) を見比べて正解を作成
- ESA WorldCover 2021 (CC BY 4.0)
- © OpenStreetMap contributors (ODbL 1.0)。way 1423054131 の輪郭
- 手法: K. Conradsen, A. A. Nielsen, H. Skriver (2016). Determining the points of change in time series of polarimetric SAR data. IEEE Transactions on Geoscience and Remote Sensing 54(5), 3007-3024
