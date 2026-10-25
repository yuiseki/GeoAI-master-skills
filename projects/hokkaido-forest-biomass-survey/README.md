# 東北海道の森林AGBモデル変化と現地照合候補

[研究提案](../../evals/curriculum/proposals/2026-10-26-hokkaido-forest-biomass-survey.md)を探索的に実行した project。主張は**固定版モデル推定に基づく現地確認の候補**までであり、森林減少・原因・炭素排出量の実測ではない。

- [計画](EXPERIMENT_PLAN.md): 既存pilot後に、全件面積交差の前に主比較を固定。純粋な事前登録ではない。
- [実行記録](EXPERIMENT_TRACKER.md): 成功・失敗・実装変更を記録。
- [短い報告](report.md) / [日本語論文](paper.md)
- [主結果](outputs/summary.json)、[面ごとの結果](outputs/cell_metrics.csv)、[共通画素監査](outputs/common_pixel_summary.json)、[候補位置図](outputs/candidate-map.png)

## 再実行

リポジトリ直下から、公開のHF固定版に接続できる環境で実行する。画像データの2ファイルは `artifacts/hokkaido-forest-biomass-survey/source/` に置き、SHA256を確認する。`artifacts/` の原データはコミットしない。

```sh
uvx --with pytest --with duckdb --with shapely --with numpy --with rasterio --with matplotlib pytest -q projects/hokkaido-forest-biomass-survey/scripts/test_*.py
uvx --with duckdb --with shapely python projects/hokkaido-forest-biomass-survey/scripts/analyze.py
uvx --with numpy --with rasterio python projects/hokkaido-forest-biomass-survey/scripts/common_pixels.py
uvx --with matplotlib python projects/hokkaido-forest-biomass-survey/scripts/plot.py
python3 .agents/skills/research-paper-writing/scripts/check_paper.py projects/hokkaido-forest-biomass-survey/paper.md
```

2026-10-26にDuckDB 2.0.0、Shapely 2.2.0、NumPy 2.5.4、rasterio 1.5.2、Matplotlib 3.11.2を使用。`uvx --with` は再実行時に同じ版を保証しないため、厳密な再現にはその版を明示して実行する。解析コードは固定版URLと元ラスタのSHA256を持つ。差の符号・面積率・候補枠は[計画](EXPERIMENT_PLAN.md)を参照。
