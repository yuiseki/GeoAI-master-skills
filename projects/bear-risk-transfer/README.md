# bear-risk-transfer

秋田県の 100 m セルで学習したクマ出没通報のリスクのモデル (環境だけのモデル) を、岐阜県、京都府、石川県、長岡市へそのまま当てはめ、どれだけ目撃のあるセルを絞れるかを測る。

- 報告: [report.md](report.md)
- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 前提: 秋田の格子、特徴量、評価の結果 (`artifacts/akita-bear-risk-grid-100m/`、作業場所 `projects/akita-bear-risk-grid-100m/`)

## 再現

```sh
cd <リポジトリの直下>
P=projects/bear-risk-transfer/scripts; A=artifacts/bear-risk-transfer
for r in "gifu 21 EPSG:6675" "kyoto 26 EPSG:6674" "ishikawa 17 EPSG:6675"; do $P/build_region.sh $r; done
$P/build_region.sh nagaoka 15 EPSG:6676 15202
for r in gifu kyoto ishikawa nagaoka; do env -u PROJ_DATA uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyproj python $P/labels_region.py $r $A/$r; done
uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow python $P/transfer_eval.py \
  artifacts/akita-bear-risk-grid-100m artifacts/akita-bear-risk-grid-100m/eval/b3_confirm_2023-2025_to_2026_scores.npz $A $A/gifu $A/kyoto $A/ishikawa $A/nagaoka
$P/score_all.sh gifu kyoto ishikawa nagaoka
# 探索 (結果を見た後)
uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow python $P/explore.py artifacts/akita-bear-risk-grid-100m $A $A/gifu:2019:2020 $A/kyoto:2013:2014 $A/ishikawa:2021:2022
uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow python $P/explore_nobldg.py artifacts/akita-bear-risk-grid-100m $A gifu kyoto ishikawa
uvx --with matplotlib --with numpy --with pandas python $P/plot.py projects/bear-risk-transfer/outputs
# テスト
uvx --with numpy --with scipy --with scikit-learn --with pandas --with shapely --with affine --with pyproj --with pytest python -m pytest -q $P
```

この母艦では、anaconda の GDAL と PROJ の環境変数を外し (`env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK`)、重い実行にメモリと CPU の上限を付けた。採点は `.agents/skills/grid-risk-mapping/scripts/score_risk_map.py`。
