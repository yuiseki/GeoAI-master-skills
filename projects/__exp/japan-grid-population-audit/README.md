# 日本の格子人口代用の整合性監査

問い: GHSL R2023A E2020 の推計居住人口を国勢調査2020の3次メッシュ人口の代わりに用いると、人口上位の現地調査候補はどれだけ入れ替わるか。東京周辺でその不一致は土地被覆の構成によって偏るか。

これは [2026-10-25 の研究 proposal](../../../evals/curriculum/proposals/2026-10-25-population-grid-priority-audit.md)から始めた研究。記述的な代用時の整合性監査であり、独立した人口予測の精度評価、災害被害、介入効果ではない。国勢調査のメッシュ人口はGHSLの入力人口と独立でない可能性がある。

入力は commit を固定した3データセット: `yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb`、`yuiseki/ghsl-japan-core-2020-30arcsec@4ee767429ee03ea47a9003c547f92c320474e350`、東京補助分析の `yuiseki/esa-worldcover-tokyo-2021-100m@6f006f64483b65b20f06c775b87db7a8d57a6fda`。元の資料とライセンスは `dataset-discovery/references/` の各カードにある。

事前の比較設計は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。`scripts/` の合成テストを通してから実データを処理する。小さい表・図は `outputs/`、大きい中間データは `artifacts/__exp/japan-grid-population-audit/` に置く。`report.md` は結論から読める短い報告、`paper.md` は保存済みの分析出力だけを根拠に日本語で執筆する。

## 再現

2026-10-25 に Python 3.13、DuckDB 2.0.0、NumPy 2.5.4、pyproj 3.8.0 で実行した。各スクリプトの先頭に `uv` の実行コマンドがある。順序は `run_analysis.py --scope pilot`、`run_analysis.py --scope full`、`run_landcover.py`、`diagnostics.py`、`population_sensitivity.py`、`plot_results.py`。最初の3本は固定した Hugging Face リビジョンの実データを読み、後の3本は保存済み成果物から診断・図を作る。図には Matplotlib と日本語フォントを用いる。

```sh
uv run --no-project --with pytest --with numpy --with pyproj python3 -m pytest -q projects/__exp/japan-grid-population-audit/scripts/test_*.py
uv run --no-project --with duckdb --with numpy --with pyproj python3 projects/__exp/japan-grid-population-audit/scripts/run_analysis.py --scope pilot
uv run --no-project --with duckdb --with numpy --with pyproj python3 projects/__exp/japan-grid-population-audit/scripts/run_analysis.py --scope full
uv run --no-project --with duckdb --with numpy --with pyproj python3 projects/__exp/japan-grid-population-audit/scripts/run_landcover.py
uv run --no-project --with numpy --with scipy --with scikit-learn python3 projects/__exp/japan-grid-population-audit/scripts/diagnostics.py
uv run --no-project --with numpy --with pyproj python3 projects/__exp/japan-grid-population-audit/scripts/population_sensitivity.py
uv run --no-project --with matplotlib python3 projects/__exp/japan-grid-population-audit/scripts/plot_results.py
```

追跡可能な小さな出力は `outputs/`、メッシュごとの中間表は Git 管理外の `artifacts/__exp/japan-grid-population-audit/` に置く。`report.md` は短い結果、`paper.md` は保存済みの分析出力だけを根拠にした論文とする。入力の凍結版とローカルの中間表の違いに注意する。
