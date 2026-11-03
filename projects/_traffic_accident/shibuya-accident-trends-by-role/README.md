# shibuya-accident-trends-by-role

渋谷区の 2019〜2025 年の人身事故を、4 つの立場 (区の交通安全担当、学校と PTA、道路安全診断、住民) の報告にまとめた記述の分析です。台東区の分析 ([taito-accident-trends-by-role](../taito-accident-trends-by-role/README.md)) と同じ読み方と区画で数え、渋谷区では首都高速の事故を除いた地点の読みを並べました。共通のデータ、方法、関門は [report.md](report.md)、立場ごとの報告は [reports/](reports/) にあります。

大きな中間ファイル (東京の本票、町丁と道路と学校、事故の点) は `artifacts/_traffic_accident/shibuya-accident-trends-by-role/` に置き、Git に入れません。東京の本票と 23 区の面は、ある場合は取り直さずに使い、行数と年の数を検査します。

Python は anaconda の numpy と pandas が混ざらないように `env -u PYTHONPATH` を付けて流します。

```sh
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/shibuya-accident-trends-by-role/scripts/prepare.py
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/shibuya-accident-trends-by-role/scripts/analyze.py
env -u PYTHONPATH uvx --with numpy --with 'duckdb>=1.5.5' --with shapely --with matplotlib python .agents/skills/analysis-visualize/scripts/classify_map.py \
  artifacts/_traffic_accident/shibuya-accident-trends-by-role/town_counts.parquet KEY_CODE per_road_km_year --kind rate --unit "件/道路 km/年" \
  --method quantile --classes 5 --compare equal jenks --crs EPSG:4612 --source "..." --no-labels --title "..." \
  --context "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet" \
  --context-name name --context-where "code5 between '13101' and '13123'" --context-crs EPSG:4612 \
  --context-source "jp-admin-2026-09@e6c87b1" --highlight projects/_traffic_accident/shibuya-accident-trends-by-role/tmp/town-highlights.csv \
  --expect-units 80 --png projects/_traffic_accident/shibuya-accident-trends-by-role/outputs/town-rate-quantile.png \
  | tee projects/_traffic_accident/shibuya-accident-trends-by-role/tmp/town-rate-quantile.stdout.txt
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/_traffic_accident/shibuya-accident-trends-by-role/scripts/plot.py
python3 projects/_traffic_accident/shibuya-accident-trends-by-role/scripts/summarize.py
```

`tmp/town-highlights.csv` は `outputs/towns.csv` の `per_road_km_year` の上位 5 町丁 (列 id、group、rank)。classify_map.py は階級と区切りの比べを決める役で、報告に貼る町丁の地図は、その区切りで `plot.py` が地名と道路を重ねて描く (`town-rate.png`)。classify_map.py は区切り方を変えたときの入れ替わりを標準出力にだけ書くので、`tmp/town-rate-quantile.stdout.txt` に残し、`plot.py` がそこから読んで `town-rate.json` に写します。

区は `scripts/prepare.py` と `scripts/analyze.py` の `CITY = "113"` で決まり、23 区の中の順位、区の面、町丁の数の検査はそこから引きます。町丁の検査値 (80 町丁、243,883 人) は 1 回目に数えた値です。

テストは `env -u PYTHONPATH uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest -p no:cacheprovider projects/_traffic_accident/shibuya-accident-trends-by-role/scripts/test_analyze.py`。
