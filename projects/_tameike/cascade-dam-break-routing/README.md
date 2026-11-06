# cascade-dam-break-routing: 階段状連鎖ため池群のカスケード決壊水文解析

## 概要

本プロジェクトは、先行する **`projects/_tameike/sar-drought-drawdown-monitoring/`** において抽出された盛夏期急減水ため池（広島県福山市 松永溜池、香川県まんのう町 満濃池）および兵庫県淡路島の連鎖ため池群を対象とし、国土地理院 5m DEM（DEM5A z15）に基づく水文解析（D8 流向追跡・余水吐流出点ブリーチ）を用いて、上流ため池決壊時のカスケード連鎖越流破堤リスクと直下流人口曝露を解析した研究です。

- **問い**: 丘陵地谷筋に階段状に連なるため池群（兵庫県淡路島、香川県讃岐平野、広島県福山市）において、上流ため池が決壊した際の「カスケード連鎖決壊（直下流池への越流・破堤連鎖）」を国土地理院 5m DEM（DEM5A z15）に基づく水文解析でルーティングしたとき、単一ため池の台帳貯水量ランキングと、カスケード連鎖累積貯水エネルギーのランキングはどれだけ乖離するか？また、連鎖流路上に曝露される直下流人口はどこに集中しているか？
- **結論の要約**: 単一池貯水量順位とカスケード累積エネルギー順位は大きく乖離し（Spearman $\rho = 0.367$）、台帳上は小規模な直下流池（前谷下池、二六池、かがつ池）が壊滅的越流破堤リスクを負うことが判明しました。また、直下流 500m 緩衝帯の人口密度は自治体平均の 2.33 倍（合計 9,100 人曝露）に集中しており、10m DEM では 50.0 % の水系結合が誤判定されるため 5m DEM が不可欠であることが実証されました。

## 再実行コマンド

```sh
# 実験パイプラインおよび図表生成の実行
uv run --with duckdb --with numpy --with scipy --with matplotlib python projects/_tameike/cascade-dam-break-routing/scripts/run_cascade_experiments.py

# プロジェクト整合性チェック
python3 .agents/skills/analysis-reporting/scripts/check_project.py projects/_tameike/cascade-dam-break-routing
```

## ディレクトリ構成

- `EXPERIMENT_PLAN.md`: 実験計画書（仮説 C0〜C4、判定規則）
- `EXPERIMENT_TRACKER.md`: 実行記録（B0〜B4 の検証判定）
- `report.md`: 研究報告書
- `scripts/`:
  - `run_cascade_experiments.py`: 水文解析・破堤シミュレーション・図表生成スクリプト
- `outputs/`:
  - `b0_dem_sanity.json` 〜 `b4_dem_resolution.json`: 各実験ブロックの評価結果
  - `sensitivity.json`: 破堤式・バッファ幅・DEM解像度の感度分析結果
  - `figure_sources.txt`: 図表の出典記録
  - `fig1_cascade_networks_map.png` 〜 `fig5_population_exposure_risk.png`: 分析図表（計5枚）
