# taxi-destination-porto

ECML/PKDD 2015 のタクシーの行き先の予測 (Porto、UCI 339) で、論文の優勝モデル (de Brébisson ほか 2015) を再現し、単純な基準に対する差が後の時期でも保たれるかを確かめる。軌跡の予測のスキルを書く前の、定番の課題での確かめ。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 原本と中間の配列、学習した重みは `artifacts/_benchmark/taxi-destination-porto/` に置く (リポジトリには入れない)

## 再実行

実データを読む実行は、全て `systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --` で囲む。

```sh
# 原本 (約 509 MB) を artifacts/_benchmark/taxi-destination-porto/raw/uci339.zip に置く
curl -L -o ../../../artifacts/_benchmark/taxi-destination-porto/raw/uci339.zip \
  "https://archive.ics.uci.edu/static/public/339/taxi+service+trajectory+prediction+challenge+ecml+pkdd+2015.zip"
PY="uvx -q --python 3.12 --with numpy --with pandas --with scikit-learn --with matplotlib --with torch==2.12.0"
$PY --with pytest pytest -q scripts/test_porto.py
$PY python scripts/prepare.py
$PY python scripts/run.py split --variant rand
$PY python scripts/run.py split --variant late
$PY python scripts/run.py cluster --variant rand
scripts/train_all.sh            # CPU、約 6 時間。GPU なら GPU=0 scripts/train_all_gpu.sh で約 40 分
$PY python scripts/run.py eval --variant rand
$PY python scripts/run.py eval --variant late
(cd scripts && $PY python diff.py && $PY python figure.py)
```

今回は M2 (rand) を `train_all.sh` の 1 本目として CPU で、残りの 2 本を `GPU=0 scripts/train_rest_gpu.sh` で流した。
