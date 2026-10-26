# akita-bear-risk-grid-100m

秋田県の 100 m セルごとに、次の熊の年度 (4 月〜翌 3 月) にクマの出没通報が 1 件以上ある起こりやすさを予測し、地図 (PNG) にする。

- 報告: [report.md](report.md)
- 計画 (確認の数字を見る前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 地図: [outputs/risk-map-akita.png](outputs/risk-map-akita.png)、[outputs/risk-map-zooms.png](outputs/risk-map-zooms.png)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (JSON、CSV) と地図 (PNG)
artifacts/akita-bear-risk-grid-100m/
  grid.json、grid_mask.npz、cells.parquet       100 m 格子 (EPSG:6678)
  worldcover.npz、dem.npz、worldpop.npz、osm.npz  セルごとの特徴量の元
  reports_by_year*.npz                          熊の年度ごとのセルの通報数
  eval/                                         評価の結果とセルごとの予測 (*_scores.npz)
  raw/gsi_dem12/                                取得した標高タイル
  web/                                          依頼外で作りかけた HTML のページ (使わない)
```

## 再現

版: Python 3.12、numpy、scipy、scikit-learn 1.9.1、DuckDB 2.0.0、rasterio、pyproj、shapely (uvx が取る版)。この母艦では、重い実行にメモリと CPU の上限を付け、anaconda の GDAL と PROJ の環境変数を外す。

```sh
cd <リポジトリの直下>
P=projects/akita-bear-risk-grid-100m/scripts; A=artifacts/akita-bear-risk-grid-100m
E="env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK"
L="systemd-run --user --scope -q -p MemoryMax=20G -p MemorySwapMax=0 -p CPUQuota=800% --"
# 1. 格子と特徴量
$E uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj --with pandas --with pyarrow python $P/build_grid.py $A
$E $L uvx --with rasterio --with numpy --with pyproj python $P/feat_worldcover.py $A
$E $L uvx --with numpy --with pyproj python $P/feat_dem.py $A $A/raw/gsi_dem12
$E uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with pyproj python $P/feat_worldpop.py $A
$E $L uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj python $P/feat_osm.py $A
$E uvx --from 'duckdb>=1.5.5' --with numpy --with pyproj python $P/labels.py $A
# 2. 評価 (開発と確認)
R="$E $L uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow python $P/model_eval.py $A"
M="B_pop B_hist B_env M_full M_logit M_full_shufhist"
$R $A/eval/b1_dev_2023_to_2024 --train 2023 --test 2024 --boot 500
$R $A/eval/b2_confirm_2023-2024_to_2025 --train 2023 2024 --test 2025 --models $M --boot 1000
$R $A/eval/b3_confirm_2023-2025_to_2026 --train 2023 2024 2025 --test 2026 --models $M --boot 1000
# 3. 地図 (PNG は projects/.../outputs/ に出る)
$E uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with matplotlib --with shapely --with pyproj --with pillow \
  python $P/render_maps.py $A $A/eval/b3_confirm_2023-2025_to_2026_scores.npz B_env projects/akita-bear-risk-grid-100m/outputs $A/web
# 4. テスト
uvx --with numpy --with scipy --with scikit-learn --with shapely --with affine --with pyproj --with pytest python -m pytest -q $P
```

標高タイルは国土地理院の公開サーバーから取る。`raw/gsi_dem12/` にあれば取り直さない。

## 派生物

`eval/*_scores.npz` と地図は予測で、観測ではない。後段で通報の数として使わない。出典の表示は report.md のデータの節。
