# sen1floods11-s1-segmentation

Sen1Floods11 (Sentinel-1 の水の切り出し) で、論文の FCN-ResNet50 と VH の Otsu の値を再現し、同じ手順の上に U-Net を足す。画像の切り出しのスキルを書く前の、定番の課題での確かめ。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)、報告: [report.md](report.md)
- 原本、学習した重み、予測は `artifacts/_benchmark/sen1floods11-s1-segmentation/` に置く。データのライセンスが原本で確かめられないので、画像も図もリポジトリに入れない

## 再実行

```sh
# 分け方の CSV を raw/ に置いてから、4 つの層を取る (約 700 MB)
B=https://storage.googleapis.com/sen1floods11/v1.1
R=../../../artifacts/_benchmark/sen1floods11-s1-segmentation/raw
for s in train valid test bolivia; do curl -s -o $R/flood_${s}_data.csv $B/splits/flood_handlabeled/flood_${s}_data.csv; done
# 各チップの S1Hand、LabelHand、JRCWaterHand、S1OtsuLabelHand を $B/data/flood_events/HandLabeled/<層>/<チップ>_<層>.tif から

PY="uv run -q --no-project --python 3.12 --with numpy --with rasterio --with torch==2.14.1 --with torchvision --with segmentation-models-pytorch"
(cd scripts && $PY --with pytest pytest -q test_s1f11.py test_models.py)
$PY python scripts/run.py otsu
GPU=0 scripts/train_all.sh       # FCN と U-Net、種 1〜3。RTX 3060 で約 70 分
$PY python scripts/run.py summary
(cd scripts && $PY python compare.py)
```

実データを読む実行は、全て `systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --` で囲む。
