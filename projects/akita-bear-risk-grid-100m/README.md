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
# 3. 地図 (PNG は projects/.../outputs/ に出る。背景の市町村界と OSM の地名は Hugging Face から読む)
$E uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with matplotlib --with shapely --with pyproj \
  python $P/render_maps_v2.py $A $A/eval/b3_confirm_2023-2025_to_2026_scores.npz B_env projects/akita-bear-risk-grid-100m/outputs
# 4. 地図でない図 (モデルごとの当たり、森の縁と建物ごとの通報の割合)
uvx --with numpy --with pandas --with matplotlib python $P/plot_figures.py projects/akita-bear-risk-grid-100m/outputs
# 5. テスト
uvx --with numpy --with scipy --with scikit-learn --with pandas --with matplotlib --with shapely --with affine --with pyproj --with pytest python -m pytest -q $P
```

標高タイルは国土地理院の公開サーバーから取る。`raw/gsi_dem12/` にあれば取り直さない。

### B1 の陽性 sample weight 追加探索

既存の `artifacts/akita-bear-risk-grid-100m/` がある環境で、2023 年度→2024 年度の `B_env` だけを実行する。無重みの既存 baseline が 0.534 に再現されない場合、候補は流さない。この環境では全件に `sample_weight=1` を渡した結果が無重みと異なったため、両方を対照として残した。結果は [B1 の追加探索 JSON](outputs/b1_positive_weight_sweep.json) に保存する。入力6ファイルのSHA256もそこに記録した。2025/2026年度は評価しない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/weight_sweep_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_positive_weight_sweep.json
```

### B1 の hard negative mining 追加探索

既存 `B_env` の無重み baseline が capture@5% = 0.5341823056 を再現した後、2023 年度の陰性セルを baseline の学習内スコアで選ぶ。陽性全件と、hard / それ以外からの random 陰性を 1:1 で使う3設定だけを再学習し、2024 年度全セルで評価する。`sample_weight` は渡さず、2025/2026 年度のラベルは読み込まない。結果と入力6ファイルの SHA256 は [B1 hard negative mining JSON](outputs/b1_hard_negative_mining.json)。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/hard_negative_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_hard_negative_mining.json
```

### B1 の soft spatial label 追加探索

2023 年度の通報セルを1、近隣100/200/300 mまでのセルに0.5/0.25/0.125を付ける。2024年度は元の0/1ラベルで評価する。HGB分類器は小数ラベルを受け付けないため、同じHGBパラメータの回帰器を使い、0/1ラベルの回帰器を対照にしてラベル変更だけの差を読む。既存分類器の baseline も残すが、両者の単純差を「ラベルだけの効果」とは呼ばない。結果と入力6ファイルの SHA256 は [B1 soft spatial label JSON](outputs/b1_soft_spatial_label.json)。2025/2026年度のラベルは読み込まない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/soft_spatial_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_soft_spatial_label.json
```

### B1 の通報件数ターゲット追加探索

2023年度の全セルの通報件数を `HistGradientBoostingRegressor(loss="poisson")` に学習させ、2024年度の元の二値セルラベルで既存 `B_env` 分類器と比較する。特徴量・HGBハイパーパラメータは同じで、重みは渡さない。ただしモデルクラスと損失も変わるため、差をターゲットだけの純粋な効果とは解釈しない。2025/2026年度のラベルは読まない。結果と入力6ファイルのSHA256は [B1 件数ターゲット JSON](outputs/b1_count_target_poisson.json)。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/count_target_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_count_target_poisson.json
```

### B1 の Poisson 回帰器内ターゲット比較

同じ `HistGradientBoostingRegressor(loss="poisson")`、静的特徴量、学習セル、無重み設定で、2023年度の0/1ターゲット (`binary_poisson`) と通報件数 (`count_poisson`) だけを替える。既存 `B_env` 分類器も参照用に再実行する。2024年度の二値セルラベルで評価し、主比較は `count_poisson − binary_poisson` の capture@5%。結果と入力6ファイルの SHA256 は [B1 Poisson ターゲット比較 JSON](outputs/b1_poisson_target_isolation.json)。2025/2026年度のラベルは読まない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/poisson_target_isolation_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_poisson_target_isolation.json
```

### B1 の squared-error 回帰器内ターゲット比較

既存の二乗誤差 HGB 回帰器に、2023年度の0/1 (`binary_squared`) と通報件数 (`count_squared`) を同じ `float32`・同じ特徴量・無重みで学習させる。2024年度の二値セルラベルで評価する。Poisson の2結果は入力SHA・特徴量・設定・年度・ライブラリ版を照合した既存JSONから参照し、再学習しない。主比較は `count_squared − binary_squared` の capture@5%。結果は [B1 squared-error ターゲット比較 JSON](outputs/b1_squared_target_isolation.json)。2025/2026年度のラベルは読まない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/squared_target_isolation_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_squared_target_isolation.json
```

## 派生物

`eval/*_scores.npz` と地図は予測で、観測ではない。後段で通報の数として使わない。出典の表示は report.md のデータの節。
