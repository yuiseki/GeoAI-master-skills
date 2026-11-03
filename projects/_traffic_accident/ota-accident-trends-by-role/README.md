# ota-accident-trends-by-role

大田区の 2019〜2025 年の人身事故を、4 つの立場 (区の交通安全担当、学校と PTA、道路安全診断、住民) の報告にまとめた記述の分析です。共通のデータ、方法、関門は [report.md](report.md)、立場ごとの報告は [reports/](reports/) にあります。

大きな中間ファイル (東京の本票、町丁と道路と学校、事故の点) は `artifacts/_traffic_accident/ota-accident-trends-by-role/` に置き、Git に入れません。

```sh
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/ota-accident-trends-by-role/scripts/prepare.py
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/ota-accident-trends-by-role/scripts/analyze.py
env -u PYTHONPATH uvx --with numpy --with 'duckdb>=1.5.5' --with shapely --with matplotlib python .agents/skills/analysis-visualize/scripts/classify_map.py \
  artifacts/_traffic_accident/ota-accident-trends-by-role/town_counts.parquet KEY_CODE per_road_km_year --kind rate --unit "件/道路 km/年" \
  --method quantile --classes 5 --compare equal jenks --crs EPSG:4612 \
  --source "警察庁 交通事故オープンデータ 2019-2025 (npa-traffic-accidents@389500a)、国勢調査2020小地域 (estat-boundary-2020@823195c)、道路延長 OSM 2026-08-31 (osm-tokyo23-src@38f7a5f)" \
  --no-labels --title "大田区のどの町丁で、道路の長さに比べて人身事故が多いか (2019〜2025年)" \
  --context "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet" \
  --context-name name --context-where "code5 between '13101' and '13123'" --context-crs EPSG:4612 \
  --context-source "jp-admin-2026-09@e6c87b1" --highlight projects/_traffic_accident/ota-accident-trends-by-role/tmp/town-highlights.csv \
  --expect-units 221 --png projects/_traffic_accident/ota-accident-trends-by-role/outputs/town-rate-quantile.png
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/_traffic_accident/ota-accident-trends-by-role/scripts/plot.py
python3 projects/_traffic_accident/ota-accident-trends-by-role/scripts/summarize.py
```

`env -u PYTHONPATH` は、環境の PYTHONPATH (anaconda) の numpy や pandas が uvx の環境に混ざらないようにするため。`--expect-units` は町丁を KEY_CODE でまとめた後の数 (`prepare.TOWN_UNITS`) で、境界ファイルの行数ではない。背景の区の名前が強調の番号に重なる区では、`--context-where` に自分の区を除く条件 (`and code5 <> '13xxx'`) を足す (品川区)。大田区では背景の区の名前は番号に重ならなかったので足していない。

`tmp/town-highlights.csv` は `outputs/towns.csv` の `per_road_km_year` の上位 5 町丁 (列 id、group、rank)。classify_map.py は階級と区切りの比べを決める役で、報告に貼る町丁の地図は、その区切りで `plot.py` が地名と道路を重ねて描く (`town-rate.png`)。

テストは `env -u PYTHONPATH uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest -p no:cacheprovider projects/_traffic_accident/ota-accident-trends-by-role/scripts/test_analyze.py`。
