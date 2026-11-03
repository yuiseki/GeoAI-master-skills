# shinjuku-accident-trends-by-role

新宿区の 2019〜2025 年の人身事故を、4 つの立場 (区の交通安全担当、学校と PTA、道路安全診断、住民) の報告にまとめた記述の分析です。共通のデータ、方法、関門は [report.md](report.md)、立場ごとの報告は [reports/](reports/) にあります。

大きな中間ファイル (東京の本票、町丁と道路と学校、事故の点) は `artifacts/_traffic_accident/shinjuku-accident-trends-by-role/` に置き、Git に入れません。

```sh
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/prepare.py
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/analyze.py
env -u PYTHONPATH uvx --with numpy --with 'duckdb>=1.5.5' --with shapely --with matplotlib python .agents/skills/analysis-visualize/scripts/classify_map.py \
  artifacts/_traffic_accident/shinjuku-accident-trends-by-role/town_counts.parquet KEY_CODE per_road_km_year --kind rate --unit "件/道路 km/年" \
  --method quantile --classes 5 --compare equal jenks --crs EPSG:4612 --source "..." --no-labels --title "..." \
  --context "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet" \
  --context-name name --context-where "code5 between '13101' and '13123'" --context-crs EPSG:4612 \
  --context-source "jp-admin-2026-09@e6c87b1" --highlight projects/_traffic_accident/shinjuku-accident-trends-by-role/tmp/town-highlights.csv \
  --expect-units 153 --png projects/_traffic_accident/shinjuku-accident-trends-by-role/outputs/town-rate-quantile.png \
  2>&1 | tee projects/_traffic_accident/shinjuku-accident-trends-by-role/tmp/classify_map.log
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/plot.py
python3 projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/summarize.py
```

`prepare.py` は、`tokyo_honhyo.parquet` と `wards.parquet` が既に artifacts にあれば取り直さずに使い、行数 (205,541) と年の数 (7) と区の数 (23) だけを毎回確かめる。`plot.py` は、classify_map.py の出力 (`tmp/classify_map.log`) から分位と等間隔で色の変わる町丁の割合を読むので、上の `tee` を省かない。重い処理は、メモリと CPU の上限を付けて `systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=300% -- ` の後に流した。

町丁は、国勢調査の境界の 154 行を `KEY_CODE` ごとに 1 つにまとめた 153 町丁 (山吹町が 2 行)。OSM の車道が中に無い神楽坂四丁目は、道路あたりの値を NoData にした。

`tmp/town-highlights.csv` は `outputs/towns.csv` の `per_road_km_year` の上位 5 町丁 (列 id、group、rank)。classify_map.py は階級と区切りの比べを決める役で、報告に貼る町丁の地図は、その区切りで `plot.py` が地名と道路を重ねて描く (`town-rate.png`)。

テストは `env -u PYTHONPATH uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/test_analyze.py`。
