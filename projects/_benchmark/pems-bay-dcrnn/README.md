# pems-bay-dcrnn

PEMS-BAY (ベイエリアの道路の速度) で DCRNN の値を再現し、同じモデルからグラフを外して効きを分ける。空間グラフのニューラルネットワークのスキルを書く前の、定番の課題での確かめ。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 原本、学習した重み、予測は `artifacts/_benchmark/pems-bay-dcrnn/` に置く

## 再実行

```sh
# raw/gdrive/pems-bay.h5 (著者の Google Drive のフォルダから gdown) と、
# DCRNN のリポジトリの data/sensor_graph/distances_bay_2017.csv を raw/ に置く。adj_mx_bay.pkl は読まない
CAP="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
PY="uvx -q --python 3.12 --with numpy --with h5py --with torch==2.14.1"
(cd scripts && $CAP $PY --with pytest pytest -q test_pems.py)
$CAP $PY python scripts/run.py prepare
$CAP $PY python scripts/run.py baselines
GPU=0 scripts/train_all.sh     # K = 2 と K = 0、60 エポックずつ。RTX 3060 で約 5.6 時間
$CAP $PY python scripts/run.py evaluate
$CAP $PY python scripts/run.py compare
$CAP $PY python scripts/run.py explore   # 探索 (主の結果を見た後)
```

GPU のメモリは 1 本 2.5〜3 GB。2 本を同じ 12 GB の GPU に (常駐のサービスと) 同時に載せるとメモリ不足になった。
