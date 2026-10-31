# kita-inbanuma-sar-replication

令和8年台風第25号で堤防が決壊した北印旛沼の浸水を、Sentinel-1 の SAR で検知した note 記事 (Mark.n、2026-09-26 と 2026-10-23) を、公開データと組み直したスクリプトで追試する。

- 段 A: 記事 1 (浸水の範囲の判定と、国土地理院の浸水推定図との比較)。計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。
- 段 B: 記事 2 (水面の高さ、深さ、水が引いた日)。段 A の後に別の計画で扱う。

大きな生成物は `artifacts/_flood/kita-inbanuma-sar-replication/` に置く。

## 再実行

```sh
cd projects/_flood/kita-inbanuma-sar-replication
U="uvx --from duckdb>=1.5.5 --with rasterio --with numpy --with scipy --with shapely --with pyproj --with pillow --with matplotlib"
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA $U python scripts/01_fetch.py
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA $U python scripts/02_grid.py
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA $U python scripts/03_detect.py
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA $U python scripts/04_compare.py
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA $U python scripts/05_fig.py
```

`env -u` は、作者の環境で anaconda の GDAL の変数が rasterio を壊すのを避けるため。テストは `scripts/test_sar.py` の 1 行目のコマンドで流す。

## 出典

- Contains modified Copernicus Sentinel data 2026 (Planetary Computer の sentinel-1-rtc、CC BY 4.0)
- 国土地理院「令和8年台風第25号による浸水推定図『北印旛沼』」の輪郭線を加工して作成 (gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fba)
- 国土地理院の標高タイル (DEM5A、DEM10B) を加工して作成
- ESA WorldCover 2021 (CC BY 4.0)
