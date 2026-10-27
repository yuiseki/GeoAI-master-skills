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

### B1 の保存スコア再現と percentile-rank ensemble

前回未保存だった `count_poisson` の2024年度全セル予測を、同じ入力・静的特徴量・HGB設定・seedで**1回だけ**再現する。既存のB1 `B_env` は保存済みスコアを読むだけ。5指標が前回と一致した場合に限り、両スコアの県内percentile rank（同値は平均順位）を使いE25/E50/E75だけ評価する。結果は[rank ensemble JSON](outputs/b1_rank_ensemble.json)、セル別スコアは[圧縮NPZ](../../artifacts/akita-bear-risk-grid-100m/eval/b1_rank_ensemble_scores.npz)に保存。大きな生成物だが再利用のためこのNPZのみgitignoreを越えて追跡する。2025/2026は使わない。

```sh
A=/Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/akita-bear-risk-grid-100m
uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 python \
  projects/akita-bear-risk-grid-100m/scripts/rank_ensemble_b1.py \
  "$A" \
  artifacts/akita-bear-risk-grid-100m/eval/b1_rank_ensemble_scores.npz \
  projects/akita-bear-risk-grid-100m/outputs/b1_rank_ensemble.json
```

実行環境が異なる場合は `A` を既存のB1入力があるディレクトリへ置き換える。既存の再現出力がある場合、二度目のfitを避けるため上書きせず停止する。B_envの保存スコアはfloat32なのでAUC/APだけ既報と10⁻⁹程度異なり、計画に記録した許容差で照合する。

### B1 の squared-error 回帰器内ターゲット比較

既存の二乗誤差 HGB 回帰器に、2023年度の0/1 (`binary_squared`) と通報件数 (`count_squared`) を同じ `float32`・同じ特徴量・無重みで学習させる。2024年度の二値セルラベルで評価する。Poisson の2結果は入力SHA・特徴量・設定・年度・ライブラリ版を照合した既存JSONから参照し、再学習しない。主比較は `count_squared − binary_squared` の capture@5%。結果は [B1 squared-error ターゲット比較 JSON](outputs/b1_squared_target_isolation.json)。2025/2026年度のラベルは読まない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/squared_target_isolation_b1.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b1_squared_target_isolation.json
```

### B1選択済み count_poisson の B2/B3 頑健性確認

B1で選んだ `count_poisson` を固定し、`B_env` 分類器と `binary_poisson` に対してB2 (2023・2024→2025) とB3 (2023〜2025→2026年4〜9月) で比較する。3モデルとも静的28特徴量・既存HGB設定・全セル・無重みで各分割から再学習する。評価は従来の二値セルラベルで、主比較は `count_poisson − binary_poisson` の capture@5%。既存B2/B3の確認的な主張は変えない。結果と入力のSHA256は [B2/B3 Poisson頑健性JSON](outputs/b2_b3_poisson_robustness.json)。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/poisson_robustness_b2_b3.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_poisson_robustness.json
```

### B_env の false-negative audit

B2/B3の保存済み `B_env` スコアと通報有無ラベルのみを用い、top 5% に入らなかった陽性セルの順位帯と、top 5% セル中心までの直線距離を集計する。100/300/500/1000m以内の割合、距離の中央値・p90と順位×距離のクロス集計は[診断JSON](outputs/b2_b3_false_negative_audit.json)に記録する。再学習や閾値変更はしない。セル中心間の近さだけでは通報座標の誤りは証明できない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy python \
  projects/akita-bear-risk-grid-100m/scripts/false_negative_audit.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_false_negative_audit.json
```

### B_env の固定5%面積 seed 膨張診断

保存済み B2/B3 `B_env` の高スコアセルを seed とし、100/300/500m の円内にある県内セルを選ぶ。選択領域の union が県内セルの5%を超える次の seed で停止するため、面積を増やして capture を上げる評価ではない。通常の exact-cell capture@5% も保存済みスコアで再現する。結果の捕捉率、実選択セル割合、seed 数と入力SHA256は[結果JSON](outputs/b2_b3_fixed_area_dilation.json)。これは選択規則の比較であり、通報座標誤差の寄与を直接推定しない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy python \
  projects/akita-bear-risk-grid-100m/scripts/fixed_area_dilation.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_fixed_area_dilation.json
```

### B_env の捕捉・取り逃し陽性の特徴量差

保存済みB2/B3の `B_env` スコアで陽性セルをtop 5%内外に分け、既存の静的28特徴量の各群のQ1・中央値・Q3・IQR、captured−missedの差、KS統計量、Cliff's deltaと欠損数を記録する。NaNは0で埋めず、有限値だけで分布を比較する。両年度で同方向の特徴量は、弱い年度のCliff効果の絶対値で並べる。結果は[特徴量監査JSON](outputs/b2_b3_positive_feature_audit.json)。スコアを作った特徴量で群を定義しているため、この差は因果的な失敗要因や特徴量重要度の推定ではない。

```sh
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with numpy --with scipy python \
  projects/akita-bear-risk-grid-100m/scripts/positive_feature_audit.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_positive_feature_audit.json
```

### B_env の5特徴量別 top-5% 捕捉率

前回の診断で選んだ道路・建物距離、農地割合、周辺建物数の5特徴量について、県内全セルの有限値から固定した20/40/60/80%点でB2/B3を共通に層別する。陽性数、捕捉数、層内recall、県内全陽性に占める割合は[層別診断JSON](outputs/b2_b3_feature_stratified_capture.json)に記録する。同値は低い側に置くため、ゼロが多い`crop`と`bldg_500`では名目上のQ2/Q3が空になる。これは前回のB2/B3結果を受けて選んだ探索的診断で、原因や独立の汎化を証明しない。

```sh
uvx --with numpy --with scipy python \
  projects/akita-bear-risk-grid-100m/scripts/feature_stratified_capture.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_feature_stratified_capture.json
```

### crop Q5 内部の保存済み B_env 順位性能

前回固定した `crop` Q5 境界（有効画素の農地割合が `0.025974025949835777` 超）を使い、Q5/非Q5の陽性率・AUC・AP・層内capture@5/10/20%と、全県top-5%の層別配分を[内部順位診断JSON](outputs/b2_b3_crop_q5_internal_audit.json)に残す。層内順位は既存の全県順位を抜き出すだけで、同点処理や予測スコアは変えない。層内の5%と全県の5%は別の面積予算であり、この監査は予算再配分の効果を測ったものではない。

```sh
uvx --with numpy --with scipy --with scikit-learn python \
  projects/akita-bear-risk-grid-100m/scripts/crop_q5_internal_audit.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_crop_q5_internal_audit.json
```

### crop Q5 / 非Q5の固定5%予算配分 oracle

保存済みB2/B3 `B_env` の層内順位を保ち、県内セルの5%を超えない整数予算 `floor(0.05×県内セル数)` をQ5と非Q5へ全通り配分する。全配分のcapture曲線、現状の配分、事後最適と差は[予算配分oracle JSON](outputs/b2_b3_crop_q5_budget_oracle.json)。端セルを端数で数える元のcapture@5%も別に再現する。oracleは当該年度の正解を見て選ぶ診断上限であり、将来の評価済みモデルや運用可能な予算配分とは扱わない。

```sh
uvx --with numpy --with scipy python \
  projects/akita-bear-risk-grid-100m/scripts/crop_q5_budget_oracle.py \
  artifacts/akita-bear-risk-grid-100m \
  projects/akita-bear-risk-grid-100m/outputs/b2_b3_crop_q5_budget_oracle.json
```

## 派生物

`eval/*_scores.npz` と地図は予測で、観測ではない。後段で通報の数として使わない。出典の表示は report.md のデータの節。
