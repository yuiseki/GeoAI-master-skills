# tokyo23-flood-record-vs-a31a

東京 23 区の 100 m セルごとに、標高、河川、土地被覆、雨から浸水が記録されやすい場所の地図を学び、後の期間の浸水の記録を、国土数値情報の洪水浸水想定区域 (A31a) と同じ面積でどれだけ捉えるかを比べる。

- 報告: [report.md](report.md)
- 計画 (流す前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 図: [outputs/fig1_model_rank.png](outputs/fig1_model_rank.png)、[fig2_agreement.png](outputs/fig2_agreement.png)、[fig3_test_cells.png](outputs/fig3_test_cells.png)、[fig4_intervals.png](outputs/fig4_intervals.png)

```
scripts/     コード
outputs/     報告が引く結果 (JSON) と図 (PNG)
artifacts/_flood/tokyo23-flood-record-vs-a31a/
  raw/                          版を固定して取った入力と DEM5A のタイル
  grid_100/、grid_250/、grid_500/、grid_250_off125/
                                cells.parquet (セルと特徴量)、flood_cell_year.parquet (セル × 年の陽性)、audit.json
  maps_main.parquet             本解析のセルごとの得点と順位 (派生物、観測ではない)
  maps/                         図のためのセルの四角と区の境界 (EPSG:6677)
```

maps_main.parquet と図の得点は、03_static.py が 1974〜1996 年の記録で学んだモデルの予測で、観測ではない。後段で浸水の観測として使わない。

## 再現

版: Python 3.12、DuckDB 1.5.5 以上、numpy、scipy、scikit-learn、shapely、pyproj、matplotlib (uvx が取る版)。この母艦では、重い実行にメモリと CPU の上限を付ける。

```sh
cd projects/_flood/tokyo23-flood-record-vs-a31a
L="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
U="uvx --from duckdb>=1.5.5 --with numpy --with scipy --with scikit-learn --with shapely --with pyproj --with pyarrow"
# 1. 入力 (版を固定) と格子
$U python scripts/01_fetch.py
for g in "100" "250" "500" "250 125"; do $L $U python scripts/02_grid.py $g; done
# 2. B1、B2、B4 (本解析) と頑健性、B4b、B3
$L $U python scripts/03_static.py --out outputs/b1_main.json --maps-out ../../../artifacts/_flood/tokyo23-flood-record-vs-a31a/maps_main.parquet
bash scripts/06_robustness.sh
$L $U python scripts/05_history.py --out outputs/b4b.json
$L $U python scripts/04_rain_panel.py --out outputs/b3_main.json     # 長くかかる、約 1 GB
# 3. 残差と特徴量の効き方、図
$L $U python scripts/09_checks.py --out outputs/checks.json
$U python scripts/07_maps.py && bash scripts/08_draw.sh
uvx --with numpy --with matplotlib python scripts/10_intervals.py
```
