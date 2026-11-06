# cascade-dam-break-routing: 階段状連鎖ため池群のカスケード決壊水文解析

## 概要

本プロジェクトは、先行する **`projects/_tameike/sar-drought-drawdown-monitoring/`** において抽出された盛夏期急減水ため池（広島県福山市 松永溜池、香川県まんのう町 満濃池）および兵庫県淡路島の連鎖ため池群を対象とし、国土地理院 5m DEM（DEM5A z15）に基づく水文解析（D8 流向追跡・余水吐流出点ブリーチ）を用いて、上流ため池決壊時のカスケード連鎖越流破堤リスクと直下流人口曝露を解析した研究です。

- **問い**: 丘陵地谷筋に階段状に連なるため池群（兵庫県淡路島、香川県讃岐平野、広島県福山市）において、上流ため池が決壊した際の「カスケード連鎖決壊（直下流池への越流・破堤連鎖）」を国土地理院 5m DEM（DEM5A z15）に基づく水文解析でルーティングしたとき、単一ため池の台帳貯水量ランキングと、カスケード連鎖累積貯水エネルギーのランキングはどれだけ乖離するか？また、連鎖流路上に曝露される直下流人口はどこに集中しているか？
- **状態**: 2026-11-06 に検算し、前の版の報告を取り下げた。前の版の数字は、`run_cascade_experiments.py` に手で書かれた値だった。5 m DEM で流れを追うと、松永溜池から二六池への連鎖も、満濃池から前谷下池への連鎖もつながっていなかった ([report.md](report.md))。手書きのスクリプトと出力は削除した (git の履歴に残る)。

## 再実行コマンド

```sh
cd projects/_tameike/cascade-dam-break-routing
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with duckdb --with scipy \
  python scripts/verify_cascade_routing.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

## ディレクトリ構成

- `EXPERIMENT_PLAN.md`: 実験計画書 (仮説 C0〜C4、判定規則)
- `EXPERIMENT_TRACKER.md`: 実行記録
- `report.md`: 検算の報告
- `scripts/verify_cascade_routing.py`: DEM5A のタイルを取り、`terrain-hydrology` で流れを追い、連鎖を確かめる
- `outputs/verify_routing.json`: 連鎖ごとの流れと、流れの上の池
