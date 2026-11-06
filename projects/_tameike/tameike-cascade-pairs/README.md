# tameike-cascade-pairs: ため池の上下流の組と、上流の貯水量を足した順位

3 つの範囲 (香川県の満濃池から下流、広島県福山市の松永周辺、兵庫県淡路市の北部) のため池で、国土地理院の 5 m DEM の上で、ある池の流れが別の池を通る組を数え、上流の池の貯水量を足した量で並べると、台帳の貯水量の順からどれだけ変わるかを調べる。前のプロジェクト `cascade-dam-break-routing` (取り下げ) のやり直し。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (流す前にコミット)
- 記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)

## 再実行

```sh
cd projects/_tameike/tameike-cascade-pairs
# テスト (答えの分かる合成の地形)
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with pytest pytest -q scripts/test_cascade_pairs.py
# 3 つの範囲 (1 つ約 100 秒、最大メモリ約 1.1 GB。タイルは artifacts/_tameike/tameike-cascade-pairs/ に保存)
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with duckdb python scripts/run_boxes.py
python3 scripts/summarize.py && python3 scripts/coord_precision.py
# 目視の図
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with duckdb --with matplotlib python scripts/figure_checks.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

`outputs/fig_check_verdicts.csv` は、図を見て手で書いた判定 (計算の出力ではない)。
