# taito-accident-trends-by-role

台東区の 2019〜2025 年の人身事故を、4 つの立場 (区の交通安全担当、学校と PTA、道路安全診断、住民) の報告にまとめた記述の分析です。共通のデータ、方法、関門は [report.md](report.md)、立場ごとの報告は [reports/](reports/) にあります。

大きな中間ファイル (東京の本票、町丁と道路と学校、事故の点) は `artifacts/taito-accident-trends-by-role/` に置き、Git に入れません。

```sh
uvx --from 'duckdb>=1.5.5' python projects/taito-accident-trends-by-role/scripts/prepare.py
uvx --from 'duckdb>=1.5.5' --with numpy python projects/taito-accident-trends-by-role/scripts/analyze.py
uvx --with numpy --with 'duckdb>=1.5.5' --with shapely --with matplotlib python .agents/skills/analysis-visualize/scripts/classify_map.py \
  artifacts/taito-accident-trends-by-role/town_counts.parquet KEY_CODE per_road_km_year --kind rate --unit "件/道路 km/年" \
  --method quantile --classes 5 --compare equal jenks --crs "EPSG:4612 (JGD2000 経度・緯度)" --source "..." --no-labels \
  --png projects/taito-accident-trends-by-role/outputs/town-rate-quantile.png
uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/taito-accident-trends-by-role/scripts/plot.py
python3 projects/taito-accident-trends-by-role/scripts/summarize.py
```

テストは `uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest projects/taito-accident-trends-by-role/scripts/test_analyze.py`。
