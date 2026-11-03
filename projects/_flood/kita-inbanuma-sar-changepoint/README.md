# kita-inbanuma-sar-changepoint

SAR 衛星の時系列で変化点を検出する例。令和8年台風第25号で浸水した北印旛沼の周りで、Sentinel-1 の同じ軌道の 2026 年 3〜10 月の撮影 (軌道 39 の 17 枚、軌道 141 の 20 枚) を並べ、画素ごとに「平均の明るさが変わった撮影日」を逐次の尤度比検定 (Conradsen ら 2016 の omnibus test の、強度だけの場合) で決める。浸水した所で浸水の始まった日に変化点が出るか、浸水しなかった農地や台地の林ではどうか、水が引いた日も出るか、隣り合う 2 枚の差と比べて何が得かを確かめる。

前後の 2 枚の差で浸水の範囲を見た兄弟のプロジェクトは [kita-inbanuma-sar-replication](../kita-inbanuma-sar-replication/)。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 手法: [scripts/cp.py](scripts/cp.py)。答えの分かる模擬のテストは [scripts/test_cp.py](scripts/test_cp.py)
- 大きな生成物は `artifacts/_flood/kita-inbanuma-sar-changepoint/` に置く (RTC の切り出し約 1.2 GB、積んだ時系列、変化点の配列)

## 再実行

```sh
cd projects/_flood/kita-inbanuma-sar-changepoint
uvx --with numpy --with scipy --with pytest pytest -q scripts/test_cp.py
E="env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA"
$E uvx --with rasterio --with numpy --with pyproj python scripts/01_fetch.py
$E uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj python scripts/02_grid.py
$E uvx --with numpy --with scipy --with scikit-image python scripts/03_quality.py
$E uvx --with numpy --with scipy python scripts/04_blocks.py
$E uvx --with numpy --with matplotlib python scripts/05_fig.py
```

`env -u` は、作者の環境で anaconda の GDAL の変数が rasterio を壊すのを避けるため。04_blocks.py は 8 GB のメモリに収まる (行を 170 行ずつ処理する)。

## 出典

- Contains modified Copernicus Sentinel data 2026 (Planetary Computer の sentinel-1-rtc、CC BY 4.0)
- 国土地理院「令和8年台風第25号による浸水推定図『北印旛沼』」の輪郭線を加工して作成 (gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fba)
- 国土地理院の標高タイル (DEM5A、DEM10B) を加工して作成
- ESA WorldCover 2021 (CC BY 4.0)
- 手法: K. Conradsen, A. A. Nielsen, H. Skriver (2016). Determining the points of change in time series of polarimetric SAR data. IEEE Transactions on Geoscience and Remote Sensing 54(5), 3007-3024
