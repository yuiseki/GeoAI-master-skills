# bunkyo-accident-trends-by-role

文京区の 2019〜2025 年の人身事故を、4 つの立場 (区の交通安全担当、学校と PTA、道路安全診断、住民) の報告にまとめた記述の分析です。台東区の分析 ([taito-accident-trends-by-role](../taito-accident-trends-by-role/)) と同じ読み方、区画、判断の規則で流しました。共通のデータ、方法、関門は [report.md](report.md)、立場ごとの報告は [reports/](reports/) にあります。

大きな中間ファイル (東京の本票、町丁と道路と学校、事故の点) は `artifacts/_traffic_accident/bunkyo-accident-trends-by-role/` に置き、Git に入れません。東京の本票 (`tokyo_honhyo.parquet`) と 23 区の面 (`wards.parquet`) は、同じ SQL と同じピンで取ったものが置いてあれば取り直さず、行数 (205,541) と年の数 (7) と区の数 (23) を検査して使います。

```sh
uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/prepare.py
uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/analyze.py
uvx --with numpy --with 'duckdb>=1.5.5' --with shapely --with matplotlib python .agents/skills/analysis-visualize/scripts/classify_map.py \
  artifacts/_traffic_accident/bunkyo-accident-trends-by-role/town_counts.parquet KEY_CODE per_road_km_year --kind rate --unit "件/道路 km/年" \
  --method quantile --classes 5 --compare equal jenks --crs EPSG:4612 --source "..." --no-labels --title "..." \
  --context "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet" \
  --context-name name --context-where "code5 between '13101' and '13123'" --context-crs EPSG:4612 \
  --context-source "jp-admin-2026-09@e6c87b1" --highlight projects/_traffic_accident/bunkyo-accident-trends-by-role/tmp/town-highlights.csv \
  --expect-units 68 --png projects/_traffic_accident/bunkyo-accident-trends-by-role/outputs/town-rate-quantile.png \
  | tee projects/_traffic_accident/bunkyo-accident-trends-by-role/tmp/town-rate-quantile.stdout.txt
uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/plot.py
python3 projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/summarize.py
```

母艦で流すときは、Python の前に `env -u PYTHONPATH` を付け、重い処理を `systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=300% --` で囲みました。

`tmp/town-highlights.csv` は `outputs/towns.csv` の `per_road_km_year` の上位 5 町丁 (列 id、group、rank)。classify_map.py は階級と区切りの比べを決める役で、報告に貼る町丁の地図は、その区切りで `plot.py` が地名と道路を重ねて描く (`town-rate.png`)。classify_map.py は区切り方を変えたときの入れ替わりを標準出力にだけ書くので、`tmp/town-rate-quantile.stdout.txt` に残し、`plot.py` がそこから読んで `town-rate.json` に写します。

区に固有の値は、`prepare.py` の `CITY` (105)、`TOWN_COUNT` (68)、`TOWN_POPULATION` (240,069)、`analyze.py` の `CITY`、`plot.py` の `LANDMARKS`、拡大図の範囲 (`ZOOM_SELECT`)、番号の位置の調整 (`RANK_OFFSET_MAIN`) にまとめてあります。

テストは `uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/test_analyze.py`。
