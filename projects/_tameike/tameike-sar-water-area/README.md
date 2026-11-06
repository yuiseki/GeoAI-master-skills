# tameike-sar-water-area: Sentinel-1 で測るため池の水面の割合と Sentinel-2 の比較

3 つの範囲 (`tameike-cascade-pairs` と同じ香川、福山、淡路) のため池で、DEM5A の水面の穴を池の輪郭にし、2024 年の Sentinel-1 RTC (VV) と Sentinel-2 L2A (NDWI) で池の中の水面の割合を測って、どの大きさの池まで合い、増減を追えるかを調べる。前のプロジェクト `sar-drought-drawdown-monitoring` (取り下げ) のやり直し。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (流す前にコミット)
- 記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)

## 再実行

```sh
cd projects/_tameike/tameike-sar-water-area
UV="uvx --python 3.12 --with numpy --with scipy --with rasterio --with pyproj --with duckdb --with pyflwdir"
CAP="env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=12G -p MemorySwapMax=0 -p CPUQuota=400% --"
systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- uvx --python 3.12 --with numpy --with scipy --with pytest pytest -q scripts/test_water_stats.py
$CAP $UV python scripts/build_masks.py      # 池の輪郭 (DEM5A のタイルは tameike-cascade-pairs のものを使う)
$CAP $UV python scripts/fetch_scenes.py     # 2024 年の S1、S2 を範囲の格子に読む (8 本並列。artifacts/ に保存)
$CAP $UV python scripts/analyze.py          # 約 5 分、最大メモリ約 7 GB
$CAP env SHIFT_NEAR_PONDS=1 $UV python scripts/analyze.py   # 探索: 池の近くだけでずれを測る
uvx --python 3.12 --with matplotlib python scripts/figure.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

池と撮影ごとの値の表 (26 MB) は `artifacts/_tameike/tameike-sar-water-area/pond_dates.csv` に置く。
