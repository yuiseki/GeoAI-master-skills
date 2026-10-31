# akita-bear-human-interface

秋田県の 100 m セルの翌年度のクマ出没通報の順位を当てる環境だけの地図 B_env ([akita-bear-risk-grid-100m](../akita-bear-risk-grid-100m/)) の中身を、熊側の環境 proxy (bear-side)、人側の環境・活動 proxy (human-side)、両者の境目を直接表す proxy (interface) に分け、予測力がどこから来ているか、通報のあったセルが年度ごとにその平面のどちらへ動いたかを調べた。

新しい予測変数を足す研究ではない。特徴量は B_env の静的な 28 個だけで、外部データは足していない。

- 報告: [report.md](report.md)
- 計画 (結果を見る前に固定、後から足した探索は末尾に記録): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 特徴量の役割 (モデルを流す前に固定): [feature_roles.csv](feature_roles.csv)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 次に集めるデータの依頼書: [DATA_REQUEST_BEAR.md](DATA_REQUEST_BEAR.md)、[DATA_REQUEST_HUMAN.md](DATA_REQUEST_HUMAN.md)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (JSON) と図 (PNG)
artifacts/_bear/akita-bear-human-interface/
  scores/    セルごとの予測 (*.npz、派生物で観測ではない)
  labels/    4〜9 月の通報のセルの数と通報の行 (観測を数えたもの)
```

## 再現

版: Python 3.12、numpy 2.5.4、scikit-learn 1.9.1、scipy、pandas、DuckDB 1.5.5 以上 (uvx が取る版)。入力は `artifacts/_bear/akita-bear-risk-grid-100m/` の固定物で、sha256 を照合してから流す。この母艦では、重い段にメモリと CPU の上限を付け、anaconda の GDAL と PROJ の環境変数を外す。コマンドはリポジトリの直下から流す。

```sh
A=artifacts/_bear/akita-bear-risk-grid-100m; W=artifacts/_bear/akita-bear-human-interface
O=projects/_bear/akita-bear-human-interface/outputs; S=projects/_bear/akita-bear-human-interface/scripts
export PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:$S
E="env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK"
L="systemd-run --user --scope -q -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=400% --"
U="uvx --from duckdb>=1.5.5 --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 --with pandas --with pyarrow --with pyproj"
# 1. 4〜9 月のラベル (Hugging Face の固定版を読む)
$E $U python $S/interface_labels.py $A $W/labels $O/labels_check.json
# 2. 役割ごとのモデル (B1 は保存済み B_env の再現の確認つき)
$E $L $U python $S/interface_models.py $A --train 2023 --test 2024 --boot 500 \
  --saved $A/eval/b1_dev_2023_to_2024_scores.npz --check-full --out $O/b1_dev_2023_to_2024.json --scores $W/scores/b1_dev_2023_to_2024.npz
$E $L $U python $S/interface_models.py $A --train 2023 2024 --test 2025 --boot 1000 \
  --saved $A/eval/b2_confirm_2023-2024_to_2025_scores.npz --out $O/b2_confirm_2023-2024_to_2025.json --scores $W/scores/b2_confirm_2023-2024_to_2025.npz
$E $L $U python $S/interface_models.py $A --train 2023 2024 2025 --test 2026 --boot 1000 \
  --saved $A/eval/b3_confirm_2023-2025_to_2026_scores.npz --out $O/b3_confirm_2023-2025_to_2026.json --scores $W/scores/b3_confirm_2023-2025_to_2026.npz
# 3. 年度の比較の共通の軸 (比べる 2 年度を除いた残りの 2 年度で M_B と M_H だけ)
for tr in "2025 2026" "2024 2026" "2024 2025" "2023 2026" "2023 2025"; do
  $E $L $U python $S/interface_models.py $A --train $tr --axes-only --scores $W/scores/axes_$(echo $tr | tr ' ' '-').npz; done
# 4. phase space、年度の移動 (F3 つき)、探索の水準と寄り、reporting process
$E $U python $S/interface_phase_space.py $A $W $O/phase_space.json
$E $U python $S/interface_year_shift.py $A $W $O/year_shift.json
$E $U python $S/interface_shift_posthoc.py $A $W $O/year_shift_posthoc.json
$E $U python $S/interface_reporting.py $A $W $O/reporting_process.json
# 5. 反証と B x H の積の項
$E $L $U python $S/interface_role_perm.py $A $W --train 2023 2024 --test 2025 --out $O/f1_role_perm_b2.json
$E $L $U python $S/interface_role_perm.py $A $W --train 2023 2024 2025 --test 2026 --out $O/f1_role_perm_b3.json
$E $U python $S/interface_block_shuffle.py $A $W $O/f2_block_shuffle.json
for s in "2023 --test 2024 --boot 500 --out $O/interaction_b1.json" "2023 2024 --test 2025 --boot 1000 --out $O/interaction_b2.json" \
         "2023 2024 2025 --test 2026 --boot 1000 --out $O/interaction_b3.json"; do
  $E $L $U python $S/interface_interaction.py $A $W --train $s; done
# 6. 図 (市町村界は Hugging Face の jp-admin を読む)
$E uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow --with shapely --with matplotlib \
  --with pyproj --with scikit-learn==1.9.1 python $S/interface_figures.py $A $W $O
# 7. テスト
uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 --with pandas --with pytest python -m pytest -q $S
```

結果の JSON が既にあれば、各スクリプトは上書きせずに止まる (interface_models.py、interface_role_perm.py、interface_interaction.py)。F1 は 1 分割で 40 回の学習があり、この母艦の混んだ時間で数時間かかった。

## 派生物

`scores/*.npz` と図の軸はモデルの予測で、熊の密度や人の活動の強さの観測ではない。後段で観測として使わない。
